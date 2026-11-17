import unittest

import sync
from garmin_coach.athlete import parse_athlete_config

# Plain Z1..Zn is the usual way to name zones, and the band a given number
# lands in depends on how many zones there are, not on what it is called.
FIVE_ZONES = [
    ("Z1", 0, 120),
    ("Z2", 120, 145),
    ("Z3", 145, 160),
    ("Z4", 160, 175),
    ("Z5", 175, 300),
]

THREE_ZONES = [
    ("Z1", 0, 145),
    ("Z2", 145, 165),
    ("Z3", 165, 300),
]


def _lap(index, minutes, hr):
    return {"activity_id": "1", "lap_index": index, "duration_min": minutes, "avg_hr": hr}


def _bands(zones, **overrides):
    """The athlete's zone configuration for one assertion."""
    return parse_athlete_config({"hr_zones": zones, **overrides})


class WeeklyIntensitySplitTests(unittest.TestCase):
    def setUp(self):
        self.intervals = {
            "date": sync.datetime(2026, 4, 8),
            "title": "Intervals",
            "distance_km": 10.0,
            "duration_min": 45.0,
            "avg_hr": 165,
            "activity_id": "1",
        }
        # 15' warm-up, 4x(3' hard + 2' float), 10' cooldown = 45' with 12' hard.
        laps = [_lap(0, 15.0, 130)]
        for rep in range(4):
            laps.append(_lap(1 + rep * 2, 3.0, 170))
            laps.append(_lap(2 + rep * 2, 2.0, 135))
        laps.append(_lap(9, 10.0, 128))
        self.laps_by_id = {"1": laps}

    def test_laps_credit_the_easy_running_inside_a_quality_session(self):
        rows = sync.compute_weekly_zone_pct([self.intervals], _bands(FIVE_ZONES), self.laps_by_id)

        self.assertEqual(1, len(rows))
        self.assertEqual(73, rows[0]["easy_pct"])
        self.assertEqual(26, rows[0]["hard_pct"])
        self.assertEqual(100, rows[0]["lap_coverage_pct"])

    def test_activity_without_laps_falls_back_to_average_heart_rate(self):
        easy = {
            "date": sync.datetime(2026, 4, 9),
            "title": "Easy run",
            "distance_km": 9.0,
            "duration_min": 60.0,
            "avg_hr": 130,
            "activity_id": "2",
        }

        rows = sync.compute_weekly_zone_pct([self.intervals, easy], _bands(FIVE_ZONES), self.laps_by_id)

        # 105 minutes total, 12 of them hard, and only the 45 came from laps.
        self.assertEqual(1, len(rows))
        self.assertEqual(105, rows[0]["total_min"])
        self.assertEqual(88, rows[0]["easy_pct"])
        self.assertEqual(42, rows[0]["lap_coverage_pct"])

    def test_whole_activity_classification_overstates_the_hard_band(self):
        without_laps = sync.compute_weekly_zone_pct([self.intervals], _bands(FIVE_ZONES), None)

        self.assertEqual(0, without_laps[0]["easy_pct"])
        self.assertEqual(100, without_laps[0]["hard_pct"])
        self.assertEqual(0, without_laps[0]["lap_coverage_pct"])

    def test_bands_follow_zone_order_not_zone_names(self):
        renamed = [("Recovery", 0, 120), ("Easy", 120, 145), ("Steady", 145, 160),
                   ("Hard", 160, 175), ("Sprint", 175, 300)]

        rows = sync.compute_weekly_zone_pct([self.intervals], _bands(renamed), self.laps_by_id)

        self.assertEqual(73, rows[0]["easy_pct"])


class ZoneSystemTests(unittest.TestCase):
    def test_three_zone_system_gets_one_zone_per_band(self):
        config = _bands(THREE_ZONES)
        self.assertEqual((1, 2), sync.band_boundaries(config))
        self.assertEqual(
            "Easy = Z1 · Moderate = Z2 · Hard = Z3",
            sync.describe_intensity_bands(config),
        )

    def test_five_zone_system_bands_two_easy_and_two_hard(self):
        config = _bands(FIVE_ZONES)
        self.assertEqual((2, 3), sync.band_boundaries(config))
        self.assertEqual(
            "Easy = Z1, Z2 · Moderate = Z3 · Hard = Z4, Z5",
            sync.describe_intensity_bands(config),
        )

    def test_seven_zone_system_splits_into_thirds(self):
        zones = [(f"Z{n}", n * 20, (n + 1) * 20) for n in range(1, 8)]

        self.assertEqual((3, 4), sync.band_boundaries(_bands(zones)))

    def test_explicit_boundaries_override_the_default_thirds(self):
        config = _bands(FIVE_ZONES, easy_zone_max=1, hard_zone_min=3)
        self.assertEqual((1, 2), sync.band_boundaries(config))
        self.assertEqual(
            "Easy = Z1 · Moderate = Z2 · Hard = Z3, Z4, Z5",
            sync.describe_intensity_bands(config),
        )

    def test_a_raised_easy_ceiling_reclassifies_the_same_session(self):
        laps = [_lap(0, 30.0, 150), _lap(1, 10.0, 170)]
        activity = {
            "date": sync.datetime(2026, 4, 8),
            "title": "Tempo",
            "distance_km": 8.0,
            "duration_min": 40.0,
            "avg_hr": 155,
            "activity_id": "1",
        }

        default = sync.compute_weekly_zone_pct([activity], _bands(FIVE_ZONES), {"1": laps})
        raised = sync.compute_weekly_zone_pct([activity], _bands(FIVE_ZONES, easy_zone_max=3), {"1": laps})

        self.assertEqual(0, default[0]["easy_pct"])
        self.assertEqual(75, default[0]["moderate_pct"])
        self.assertEqual(75, raised[0]["easy_pct"])

    def test_no_configured_zones_produces_no_rows(self):
        config = _bands([])
        self.assertEqual((0, 0), sync.band_boundaries(config))
        self.assertEqual("", sync.describe_intensity_bands(config))
        self.assertEqual([], sync.compute_weekly_zone_pct([], config, None))


if __name__ == "__main__":
    unittest.main()
