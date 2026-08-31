import tempfile
import unittest
from pathlib import Path

from garmin_coach.plan import PlanValidationError, parse_training_plan


VALID = '''# Plan

```plan-data
{"version": 1, "plan": {"id": "example", "status": "active"}, "sessions": [{"id": "s1", "date": "2026-04-08", "name": "Easy", "steps": [{"kind": "warmup", "distance_m": 1000}, {"kind": "cooldown", "time_s": 600}]}]}
```
'''


class TrainingPlanTests(unittest.TestCase):
    def write_plan(self, contents):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "training-plan.md"
        path.write_text(contents, encoding="utf-8")
        return path

    def test_parses_human_text_and_plan_data(self):
        plan = parse_training_plan(self.write_plan(VALID))
        self.assertTrue(plan.is_active)
        self.assertEqual("s1", plan.sessions[0].id)
        self.assertEqual(1000, plan.sessions[0].planned_distance_m)

    def test_no_active_plan_is_valid(self):
        path = self.write_plan('''```plan-data
{"version": 1, "plan": {"id": "none", "status": "none"}, "sessions": []}
```''')
        self.assertFalse(parse_training_plan(path).is_active)

    def test_public_example_plan_is_valid(self):
        example = Path(__file__).resolve().parents[1] / "examples" / "coaching" / "training-plan.md"
        plan = parse_training_plan(example)
        self.assertTrue(plan.is_active)
        self.assertEqual(6, len(plan.sessions))

    def test_rejects_multiple_blocks_and_invalid_step(self):
        with self.assertRaisesRegex(PlanValidationError, "exactly one"):
            parse_training_plan(self.write_plan(VALID + VALID))
        invalid = VALID.replace('"warmup"', '"stride"')
        with self.assertRaisesRegex(PlanValidationError, "must be one of"):
            parse_training_plan(self.write_plan(invalid))

    def test_rejects_reversed_target_ranges(self):
        reversed_pace = VALID.replace('"kind": "warmup", "distance_m": 1000', '"kind": "interval", "distance_m": 1000, "target": {"kind": "pace", "min": "5:30/km", "max": "5:00/km"}')
        with self.assertRaisesRegex(PlanValidationError, "pace target min"):
            parse_training_plan(self.write_plan(reversed_pace))

    def test_rejects_duplicate_session_ids(self):
        duplicate = '''```plan-data
{"version": 1, "plan": {"id": "example", "status": "active"}, "sessions": [{"id": "s1", "date": "2026-04-08", "name": "Easy", "steps": [{"kind": "warmup", "distance_m": 1000}]}, {"id": "s1", "date": "2026-04-09", "name": "Easy", "steps": [{"kind": "warmup", "distance_m": 1000}]}]}
```'''
        with self.assertRaisesRegex(PlanValidationError, "unique"):
            parse_training_plan(self.write_plan(duplicate))
