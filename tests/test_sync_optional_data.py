import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import sync


class SyncOptionalDataTests(unittest.TestCase):
    def test_missing_gear_change_date_skips_the_gear_baseline(self):
        activity = {
            "date": sync.datetime(2026, 1, 1),
            "title": "Easy run",
            "avg_hr": 140,
            "avg_pace": "6:30",
        }

        with patch.object(sync, "GEAR_CHANGE_DATE", None):
            self.assertEqual((None, None), sync.compute_easy_hr_baseline([activity], []))

    def test_weather_skips_activities_without_coordinates(self):
        with patch("sync.requests.get") as get:
            weather = sync.fetch_weather_for_location(None, None, ["2026-01-01"])

        self.assertEqual({}, weather)
        get.assert_not_called()

    def test_garmin_gear_is_mapped_to_local_running_activities(self):
        class GearClient:
            def get_user_profile(self):
                return {"userProfilePK": 42}

            def get_gear(self, profile_number):
                self.profile_number = profile_number
                return {"gear": [{"uuid": "shoe-1", "gearName": "Nimbus 26"}]}

            def get_gear_activities(self, gear_uuid, limit):
                self.gear_request = (gear_uuid, limit)
                return [{"activityId": 100}, {"activityId": 999}]

        activities = [
            {"activity_id": "100", "distance_km": 10.5},
            {"activity_id": "200", "distance_km": 5.0},
        ]
        client = GearClient()

        with patch("sync.time.sleep"):
            shoes = sync.fetch_garmin_shoe_mileage(client, activities)

        self.assertEqual(
            [{"name": "Nimbus 26", "activities": 1, "distance_km": 10.5}],
            shoes,
        )
        self.assertEqual(42, client.profile_number)
        self.assertEqual(("shoe-1", 1000), client.gear_request)

    def test_missing_optional_thresholds_disable_their_analyses(self):
        activity = {
            "activity_id": "100",
            "date": sync.datetime(2026, 1, 1),
            "distance_km": 10.5,
            "avg_pace": "6:30",
        }
        laps = {"100": [{"distance_km": 1, "avg_pace_min_km": "4:30"}]}

        with (
            patch.object(sync, "QUALITY_LAP_PACE_THRESHOLD", None),
            patch.object(sync, "MIN_QUALITY_LAP_KM", None),
        ):
            self.assertFalse(sync._has_quality_lap(activity, laps))
        self.assertEqual([], sync.identify_long_runs([activity], threshold_km=None))

    def test_history_generates_with_the_public_optional_defaults(self):
        row = {
            "activity_id": "100",
            "date": "2026-01-01",
            "title": "Easy run",
            "distance_km": "10.5",
            "duration_min": "68",
            "avg_pace_min_km": "6:30",
            "avg_heart_rate": "140",
        }

        with TemporaryDirectory() as directory:
            history = Path(directory) / "training-history.md"
            with (
                patch.object(sync, "TRAINING_HISTORY_PATH", str(history)),
                patch.object(sync, "GEAR_CHANGE_DATE", None),
                patch.object(sync, "LONG_RUN_KM", None),
                patch.object(sync, "QUALITY_LAP_PACE_THRESHOLD", None),
                patch.object(sync, "MIN_QUALITY_LAP_KM", None),
            ):
                sync.generate_training_history([row])

            self.assertTrue(history.exists())
            content = history.read_text(encoding="utf-8")
            self.assertIn("No gear-change date configured", content)
            self.assertIn("long-run threshold not configured", content)

    def test_sync_creates_configured_csv_directories(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "exports" / "activities.csv"
            laps_path = root / "exports" / "activity_laps.csv"
            with (
                patch.object(sync, "CSV_PATH", str(csv_path)),
                patch.object(sync, "LAPS_CSV_PATH", str(laps_path)),
            ):
                sync.ensure_sync_output_directories()

            self.assertTrue(csv_path.parent.is_dir())
            self.assertTrue(laps_path.parent.is_dir())
