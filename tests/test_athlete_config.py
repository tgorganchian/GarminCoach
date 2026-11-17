import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from garmin_coach.athlete import AthleteConfig, AthleteConfigError, load_athlete_config, parse_athlete_config
from garmin_coach.paths import project_paths


class AthleteConfigTests(unittest.TestCase):
    def test_a_missing_file_switches_every_optional_analysis_off(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(AthleteConfig(), load_athlete_config(project_paths(Path(directory))))

    def test_values_are_normalised_for_the_analyses(self):
        config = parse_athlete_config({"quality_keywords": ["Tempo", "5K"], "gear_change_date": "2026-03-01", "weather_timezone": ""})

        self.assertEqual(("tempo", "5k"), config.quality_keywords)
        self.assertEqual(datetime(2026, 3, 1), config.gear_change_date)
        self.assertEqual("auto", config.weather_timezone)

    def test_a_value_the_sync_cannot_use_names_its_setting(self):
        zones = [("Z1", 0, 120), ("Z2", 120, 145), ("Z3", 145, 300)]
        cases = {
            "HR_ZONES": {"hr_zones": [("Z1", 120, 100)]},
            "EASY_ZONE_MAX must be lower": {"hr_zones": zones, "easy_zone_max": 2, "hard_zone_min": 2},
            "HARD_ZONE_MIN": {"hr_zones": zones, "hard_zone_min": 4},
            "GEAR_CHANGE_DATE": {"gear_change_date": "March 1st"},
            r"RACE_CALENDAR\[0\] needs goal": {"race_calendar": [{"name": "10K", "date": "2026-05-01", "distance_km": 10}]},
            "LONG_RUN_KM": {"long_run_km": "18"},
        }
        for message, settings in cases.items():
            with self.subTest(message=message), self.assertRaisesRegex(AthleteConfigError, message):
                parse_athlete_config(settings)


if __name__ == "__main__":
    unittest.main()
