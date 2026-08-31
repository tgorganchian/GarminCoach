import tempfile
import unittest
from pathlib import Path

from garmin_coach.paths import project_paths
from garmin_coach.readiness import is_ready, readiness


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
