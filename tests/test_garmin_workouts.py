import copy
import unittest
from datetime import date

from garmin_workouts import Action, GarminGateway, execute_apply, fingerprint, reconcile, render_session
from garmin_coach.manifest import managed_coverage_days
from garmin_coach.plan import PlanSession, Step, TrainingPlan


class FakeGarmin:
    """In-memory adapter that can fail on its Nth remote write."""

    def __init__(self, fail_on_write=None):
        self.fail_on_write = fail_on_write
        self.writes = 0
        self.next_id = 100
        self.workouts = {}
        self.calendar = {}

    def _write(self):
        self.writes += 1
        if self.writes == self.fail_on_write:
            raise RuntimeError("Garmin returned 429")
        self.next_id += 1
        return self.next_id

    def verify_owned(self, action):
        pass

    def create(self, payload):
        workout_id = self._write()
        self.workouts[workout_id] = payload["workoutName"]
        return workout_id

    def schedule(self, workout_id, on_date):
        scheduled_id = self._write()
        self.calendar[scheduled_id] = (workout_id, on_date)
        return scheduled_id

    def update(self, workout_id, payload):
        self._write()
        self.workouts[workout_id] = payload["workoutName"]

    def unschedule(self, scheduled_id):
        self._write()
        del self.calendar[scheduled_id]


def _apply(plan, manifest, gateway, start=date(2026, 4, 1)):
    """Preview and apply like the CLI; return the manifest as last saved to disk."""
    saved = [copy.deepcopy(manifest)]
    try:
        execute_apply(plan, reconcile(plan, manifest, start, 14), manifest, gateway, save=lambda m: saved.append(copy.deepcopy(m)))
    except RuntimeError:
        pass
    return saved[-1]


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


class InterruptedApplyTests(unittest.TestCase):
    def setUp(self):
        steps = (Step("warmup", time_s=600),)
        self.first = PlanSession("s1", date(2026, 4, 8), "Easy", steps)
        self.second = PlanSession("s2", date(2026, 4, 10), "Easy", steps)
        self.plan = TrainingPlan(1, "plan-1", "active", (self.first, self.second))

    def test_a_failed_write_leaves_every_created_workout_owned(self):
        garmin = FakeGarmin(fail_on_write=3)  # s1 created and scheduled, then creating s2 fails
        manifest = _apply(self.plan, {"version": 1, "entries": {}}, garmin)

        self.assertEqual(set(garmin.workouts), {entry["remote_workout_id"] for entry in manifest["entries"].values()})
        kinds = {action.session_id: action.kind for action in reconcile(self.plan, manifest, date(2026, 4, 1), 14)}
        self.assertEqual({"s1": "unchanged", "s2": "create"}, kinds)

    def test_a_create_interrupted_before_scheduling_resumes_without_a_duplicate(self):
        garmin = FakeGarmin(fail_on_write=2)  # s1 uploaded, scheduling it fails
        manifest = _apply(self.plan, {"version": 1, "entries": {}}, garmin)

        self.assertEqual("reschedule", reconcile(self.plan, manifest, date(2026, 4, 1), 14)[0].kind)
        garmin.fail_on_write = None
        manifest = _apply(self.plan, manifest, garmin)

        self.assertEqual(2, len(garmin.workouts))
        self.assertEqual({"2026-04-08", "2026-04-10"}, {on_date for _, on_date in garmin.calendar.values()})
        self.assertEqual({"2026-04-08", "2026-04-10"}, {entry["date"] for entry in manifest["entries"].values()})

    def test_moving_a_session_moves_its_owned_workout(self):
        garmin = FakeGarmin()
        manifest = _apply(self.plan, {"version": 1, "entries": {}}, garmin)
        moved = TrainingPlan(1, "plan-1", "active", (PlanSession("s1", date(2026, 4, 9), "Easy", self.first.steps), self.second))

        manifest = _apply(moved, manifest, garmin)

        self.assertEqual(2, len(garmin.workouts))
        self.assertEqual({"2026-04-09", "2026-04-10"}, {on_date for _, on_date in garmin.calendar.values()})
        self.assertEqual("unchanged", reconcile(moved, manifest, date(2026, 4, 1), 14)[0].kind)
