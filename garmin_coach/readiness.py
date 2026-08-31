"""Report local GarminCoach readiness without reading secrets back to stdout."""

from __future__ import annotations

import argparse
import json
import py_compile
from dataclasses import asdict, dataclass
from typing import Iterable

from dotenv import dotenv_values

from garmin_coach.paths import ProjectPaths, project_paths
from garmin_coach.plan import PlanValidationError, parse_training_plan


@dataclass(frozen=True)
class Requirement:
    name: str
    required_for: tuple[str, ...]
    state: str
    remediation: str
    path: str | None = None


def readiness(paths: ProjectPaths | None = None) -> list[Requirement]:
    paths = paths or project_paths()
    env = dotenv_values(paths.env_file) if paths.env_file.exists() else {}
    config_state = _config_state(paths)
    return [
        Requirement("env-file", ("sync",), "ready" if paths.env_file.exists() else "missing", "Create .env from the generic template and enter credentials yourself.", str(paths.env_file)),
        Requirement("garmin-credentials", ("sync",), _credentials_state(env), "Set GARMIN_EMAIL and GARMIN_PASSWORD directly in .env.", str(paths.env_file)),
        Requirement("athlete-config", ("sync",), config_state, "Complete athlete_config.py with zones, records, calendar, classifiers, and weather fallback.", str(paths.athlete_config)),
        Requirement("athlete-profile", ("coaching",), _file_state(paths.athlete_profile), "Create coaching/athlete-profile.md from the template after confirmation.", str(paths.athlete_profile)),
        Requirement("coach-log", ("coaching",), _file_state(paths.coach_log), "Create coaching/coach-log.md from the template after confirmation.", str(paths.coach_log)),
        Requirement("journal", ("coaching",), "ready" if paths.journal.is_dir() else "missing", "Create the mandatory local journal directory or configure an alternate local root.", str(paths.journal)),
        _plan_requirement(paths),
        Requirement("obsidian-journal", (), "optional", "Configure an Obsidian folder only if it should be the journal root.", None),
        Requirement("voice-feedback", (), "optional", "Configure optional voice feedback only if you want to collect it.", None),
    ]


def is_ready(requirements: Iterable[Requirement], purpose: str) -> bool:
    allowed = {"ready", "optional"}
    if purpose == "coaching":
        allowed.add("not-active")
    return all(item.state in allowed for item in requirements if purpose in item.required_for)


def _credentials_state(env: dict[str, str | None]) -> str:
    return "ready" if env.get("GARMIN_EMAIL") and env.get("GARMIN_PASSWORD") else "missing"


def _config_state(paths: ProjectPaths) -> str:
    if not paths.athlete_config.exists():
        return "missing"
    try:
        py_compile.compile(str(paths.athlete_config), doraise=True)
    except py_compile.PyCompileError:
        return "invalid"
    return "ready"


def _file_state(path) -> str:
    return "ready" if path.is_file() else "missing"


def _plan_requirement(paths: ProjectPaths) -> Requirement:
    if not paths.training_plan.exists():
        return Requirement("training-plan", ("plan", "render"), "not-active", "Create or approve a plan before rendering Garmin workouts.", str(paths.training_plan))
    try:
        plan = parse_training_plan(paths.training_plan)
    except PlanValidationError:
        return Requirement("training-plan", ("plan", "render"), "invalid", "Fix the single PLAN-DATA block before rendering Garmin workouts.", str(paths.training_plan))
    state = "ready" if plan.is_active else "not-active"
    return Requirement("training-plan", ("plan", "render"), state, "Create or approve a plan before rendering Garmin workouts.", str(paths.training_plan))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit stable machine-readable readiness data")
    args = parser.parse_args()
    items = readiness()
    if args.json:
        print(json.dumps({"requirements": [asdict(item) for item in items]}, indent=2))
    else:
        for item in items:
            scope = ", ".join(item.required_for) or "optional"
            print(f"{item.name}: {item.state} ({scope}) — {item.remediation}")
    return 0
