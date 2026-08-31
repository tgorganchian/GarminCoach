import unittest
from datetime import datetime

from sync import compute_plan_compliance
from garmin_coach.plan import PlanSession, Step, TrainingPlan


class SyncPlanIntegrationTests(unittest.TestCase):
    def test_compliance_uses_dated_plan_session_metadata(self):
        session = PlanSession("session-1", datetime(2026, 4, 8).date(), "Intervals", (Step("interval", distance_m=5000),))
        plan = TrainingPlan(1, "plan", "active", (session,))
        activities = [{"date": datetime(2026, 4, 8), "title": "Intervals [session-1]", "distance_km": 5.1, "avg_pace": "5:00", "avg_hr": 160}]
        weeks = compute_plan_compliance(activities, plan)
        self.assertEqual(1, weeks[0]["completed"])
        self.assertAlmostEqual(0.1, weeks[0]["details"][0]["km_diff"])

    def test_no_active_plan_has_no_compliance(self):
        self.assertEqual([], compute_plan_compliance([], TrainingPlan(1, "none", "none", ())))
