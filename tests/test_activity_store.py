import csv
import tempfile
import unittest
from pathlib import Path

from garmin_coach.activities import ACTIVITY_FIELDS, ActivityStore


def _garmin(activity_id, title, day="2026-11-16", km=10.0, start="07:00:00"):
    return {"activityId": activity_id, "startTimeLocal": f"{day} {start}", "activityName": title,
            "distance": km * 1000, "duration": km * 300}


class ActivityStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.activities = root / "data" / "activities.csv"
        self.laps = root / "data" / "activity_laps.csv"

    def tearDown(self):
        self.directory.cleanup()

    def _store(self):
        return ActivityStore(self.activities, self.laps)

    def test_a_run_renamed_in_garmin_is_refreshed_not_duplicated(self):
        store = self._store()
        store.merge([_garmin(111, "Morning Run")])
        store.rows[0]["feeling"] = "Strong"
        store.save()

        store = self._store()
        new_rows = store.merge([_garmin(111, "Tempo 10k")])

        self.assertEqual([], new_rows)
        self.assertEqual(1, len(store.rows))
        self.assertEqual("Tempo 10k", store.rows[0]["title"])
        self.assertEqual("Strong", store.rows[0]["feeling"])

    def test_a_double_day_with_the_default_title_keeps_both_runs(self):
        store = self._store()
        store.merge([_garmin(1, "City Running")])
        store.save()

        store = self._store()
        new_rows = store.merge([_garmin(1, "City Running"), _garmin(2, "City Running", km=6.0, start="19:00:00")])

        self.assertEqual(["2"], [str(row["activity_id"]) for row in new_rows])
        self.assertEqual(16.0, sum(float(row["distance_km"]) for row in store.rows))

    def test_a_row_saved_without_an_id_is_adopted_by_its_garmin_activity(self):
        self.activities.parent.mkdir(parents=True)
        with open(self.activities, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ACTIVITY_FIELDS)
            writer.writeheader()
            writer.writerow({"date": "2026-11-16", "title": "City Running", "distance_km": "10.0", "feeling": "Normal"})

        store = self._store()
        new_rows = store.merge([_garmin(1, "City Running"), _garmin(2, "City Running", km=6.0, start="19:00:00")])

        self.assertEqual(1, len(new_rows))
        self.assertEqual(["1", "2"], sorted(str(row["activity_id"]) for row in store.rows))
        self.assertEqual("Normal", next(row for row in store.rows if str(row["activity_id"]) == "1")["feeling"])

    def test_duplicates_left_by_older_syncs_collapse_on_load(self):
        store = self._store()
        store.rows = [
            {"activity_id": "111", "date": "2026-11-16", "title": "Morning Run", "distance_km": "10.0"},
            {"activity_id": "111", "date": "2026-11-16", "title": "Tempo 10k", "distance_km": "10.0"},
        ]
        store.save()

        self.assertEqual(["Tempo 10k"], [row["title"] for row in self._store().rows])

    def test_saving_creates_configured_folders_and_leaves_no_partial_file(self):
        store = self._store()
        store.merge([_garmin(1, "Easy")])
        store.laps.append({"activity_id": "1", "lap_index": "0", "distance_km": "1.0"})
        store.save()

        reloaded = self._store()
        self.assertEqual(1, len(reloaded.rows))
        self.assertEqual(1, len(reloaded.laps))
        self.assertEqual(["activities.csv", "activity_laps.csv"], sorted(p.name for p in self.activities.parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
