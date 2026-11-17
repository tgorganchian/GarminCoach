import re
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"


class SkillPointerTests(unittest.TestCase):
    def test_every_skill_named_by_a_skill_exists(self):
        for skill in sorted(SKILLS.glob("*/SKILL.md")):
            for name in sorted(set(re.findall(r"`(running-[a-z-]+)`", skill.read_text(encoding="utf-8")))):
                with self.subTest(skill=skill.parent.name, names=name):
                    self.assertTrue((SKILLS / name / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
