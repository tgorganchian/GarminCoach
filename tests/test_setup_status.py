import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from garmin_coach.paths import project_paths
from garmin_coach.readiness import is_ready, readiness, workspace_status


class SetupStatusTests(unittest.TestCase):
    def test_missing_workspace_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            items = readiness(project_paths(Path(directory)))
        states = {item.name: item.state for item in items}
        self.assertEqual("missing", states["env-file"])
        self.assertEqual("missing", states["journal"])
        self.assertFalse(is_ready(items, "sync"))

    def test_no_active_plan_does_not_block_coaching(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coaching = root / "coaching"
            coaching.mkdir()
            (root / ".env").write_text("GARMIN_EMAIL=a\nGARMIN_PASSWORD=b\n", encoding="utf-8")
            (root / "athlete_config.py").write_text("HR_ZONES = []\n", encoding="utf-8")
            (coaching / "athlete-profile.md").write_text("# Profile\n", encoding="utf-8")
            (coaching / "coach-log.md").write_text("# Log\n", encoding="utf-8")
            (coaching / "journal").mkdir()
            (coaching / "training-plan.md").write_text('''```plan-data
{"version": 1, "plan": {"id": "none", "status": "none"}, "sessions": []}
```''', encoding="utf-8")
            items = readiness(project_paths(root))
        states = {item.name: item.state for item in items}
        self.assertEqual("not-active", states["training-plan"])
        self.assertTrue(is_ready(items, "coaching"))
        self.assertFalse(is_ready(items, "render"))

    def test_config_without_gear_does_not_block_sync(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("GARMIN_EMAIL=a\nGARMIN_PASSWORD=b\n", encoding="utf-8")
            (root / "athlete_config.py").write_text("HR_ZONES = []\n", encoding="utf-8")
            items = readiness(project_paths(root))

        self.assertTrue(is_ready(items, "sync"))

    def test_journal_path_from_env_file_is_honoured(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("JOURNAL_PATH=vault/journal\n", encoding="utf-8")
            (root / "vault" / "journal").mkdir(parents=True)
            items = readiness(project_paths(root))

        self.assertEqual("ready", {item.name: item.state for item in items}["journal"])

    def test_an_unusable_athlete_config_names_the_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "athlete_config.py").write_text("HR_ZONES = [('Z1', 0, 120)]\nEASY_ZONE_MAX = 3\n", encoding="utf-8")
            items = readiness(project_paths(root))

        config = next(item for item in items if item.name == "athlete-config")
        self.assertEqual("invalid", config.state)
        self.assertIn("EASY_ZONE_MAX", config.remediation)

    def test_status_carries_the_decisions_the_router_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coaching = root / "coaching"
            coaching.mkdir()
            (coaching / "training-plan.md").write_text('''```plan-data
{"version": 1, "plan": {"id": "p", "status": "active"}, "sessions": [
  {"id": "s1", "date": "2026-04-08", "name": "Easy", "steps": [{"kind": "warmup", "time_s": 600}]}]}
```''', encoding="utf-8")
            (coaching / "garmin-workouts.manifest.json").write_text(json.dumps({"version": 1, "entries": {"s1": {"date": "2026-04-08"}}}), encoding="utf-8")
            (root / "data").mkdir()
            (root / "data" / "activities.csv").write_text("activity_id,date,title\n1,2026-03-30,Easy\n", encoding="utf-8")
            status = workspace_status(project_paths(root), today=date(2026, 4, 1))

        self.assertEqual({"sync": False, "coaching": False, "plan": True, "render": True}, status["ready_for"])
        self.assertEqual(8, status["workout_coverage_days"])
        self.assertEqual("2026-03-30", status["latest_activity"])
