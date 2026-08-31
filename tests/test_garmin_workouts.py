import unittest
from datetime import date

from garmin_workouts import Action, GarminGateway, fingerprint, managed_coverage_days, reconcile, render_session
from garmin_coach.plan import PlanSession, Step, TrainingPlan


class GarminWorkoutTests(unittest.TestCase):
    def setUp(self):
        self.session = PlanSession("session-1", date(2026, 4, 8), "Intervals", (Step("warmup", distance_m=1000), Step("cooldown", time_s=600)))
        self.plan = TrainingPlan(1, "plan-1", "active", (self.session,))

    def test_rendering_is_deterministic(self):
        payload = render_session(self.session)
        self.assertIn("[session-1]", payload["workoutName"])
        self.assertEqual(fingerprint(payload), fingerprint(render_session(self.session)))

    def test_reconciliation_covers_create_update_reschedule_and_unschedule(self):
        payload = render_session(self.session)
        manifest = {"version": 1, "entries": {}}
        self.assertEqual("create", reconcile(self.plan, manifest, date(2026, 4, 1), 14)[0].kind)
        manifest["entries"]["session-1"] = {"remote_workout_id": 1, "scheduled_workout_id": 2, "date": "2026-04-08", "name": payload["workoutName"], "fingerprint": "old"}
        self.assertEqual("update", reconcile(self.plan, manifest, date(2026, 4, 1), 14)[0].kind)
        manifest["entries"]["session-1"]["fingerprint"] = fingerprint(payload)
        manifest["entries"]["session-1"]["date"] = "2026-04-07"
        self.assertEqual("reschedule", reconcile(self.plan, manifest, date(2026, 4, 1), 14)[0].kind)
        inactive = TrainingPlan(1, "none", "none", ())
        self.assertEqual("unschedule", reconcile(inactive, manifest, date(2026, 4, 1), 14)[0].kind)

    def test_minimum_horizon_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "14"):
            reconcile(self.plan, {"version": 1, "entries": {}}, date(2026, 4, 1), 13)

    def test_managed_coverage_uses_only_future_manifest_entries(self):
        manifest = {"entries": {"old": {"date": "2026-03-30"}, "next": {"date": "2026-04-14"}}}
        self.assertEqual(14, managed_coverage_days(manifest, date(2026, 4, 1)))

    def test_manifest_owned_remote_state_is_checked_before_mutation(self):
        class Client:
            def get_workout_by_id(self, _):
                return {"workoutName": "original"}

            def get_scheduled_workout_by_id(self, _):
                return {"workoutId": 10, "date": "2026-04-08"}

        gateway = object.__new__(GarminGateway)
        gateway.client = Client()
        action = Action("update", "session-1", "2026-04-08", "renamed", "hash", 10, 20, "original", "2026-04-08")
        gateway.verify_owned(action)
        gateway.client.get_scheduled_workout_by_id = lambda _: {"workoutId": 10, "date": "2026-04-09"}
        with self.assertRaisesRegex(RuntimeError, "schedule changed"):
            gateway.verify_owned(action)
