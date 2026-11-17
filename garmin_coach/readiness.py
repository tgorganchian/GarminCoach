"""Report local GarminCoach readiness without reading secrets back to stdout."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any, Iterable

from garmin_coach.activities import ActivityStore
from garmin_coach.athlete import AthleteConfigError, load_athlete_config
from garmin_coach.manifest import load_manifest, managed_coverage_days
from garmin_coach.paths import ProjectPaths, project_paths
from garmin_coach.plan import PlanValidationError, parse_training_plan

PURPOSES = ("sync", "coaching", "plan", "render")


@dataclass(frozen=True)
class Requirement:
    name: str
    required_for: tuple[str, ...]
    state: str
    remediation: str
    path: str | None = None


def readiness(paths: ProjectPaths | None = None) -> list[Requirement]:
    paths = paths or project_paths()
    return [
        Requirement("env-file", ("sync",), "ready" if paths.env_file.exists() else "missing", "Create .env from the generic template and enter credentials yourself.", str(paths.env_file)),
        Requirement("garmin-credentials", ("sync",), _credentials_state(paths.settings), "Set GARMIN_EMAIL and GARMIN_PASSWORD directly in .env.", str(paths.env_file)),
        _config_requirement(paths),
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


def workspace_status(paths: ProjectPaths | None = None, today: date | None = None) -> dict[str, Any]:
    """The decisions the running-coach router reads from `setup_status.py --json`."""
    paths = paths or project_paths()
    items = readiness(paths)
    latest = ActivityStore(paths.activities_csv, paths.laps_csv).latest_date()
    return {
        "ready_for": {purpose: is_ready(items, purpose) for purpose in PURPOSES},
        "workout_coverage_days": _coverage_days(paths, items, today or date.today()),
        "latest_activity": latest.date().isoformat() if latest else None,
        "requirements": [asdict(item) for item in items],
    }


def _coverage_days(paths: ProjectPaths, items: list[Requirement], today: date) -> int | None:
    """Days of future Garmin workouts the manifest owns; None without an active plan."""
    if not is_ready(items, "render"):
        return None
    try:
        return managed_coverage_days(load_manifest(paths.workout_manifest), today)
    except (OSError, ValueError):
        return None  # an unreadable manifest is reported by garmin_workouts.py preview itself


def _credentials_state(settings: Mapping[str, str]) -> str:
    return "ready" if settings.get("GARMIN_EMAIL") and settings.get("GARMIN_PASSWORD") else "missing"


def _config_requirement(paths: ProjectPaths) -> Requirement:
    remediation = "Complete athlete_config.py with zones, records, calendar, classifiers, and weather fallback."
    state = "ready" if paths.athlete_config.exists() else "missing"
    if state == "ready":
        try:
            load_athlete_config(paths)
        except AthleteConfigError as exc:
            state, remediation = "invalid", f"Fix athlete_config.py: {exc}"
    return Requirement("athlete-config", ("sync",), state, remediation, str(paths.athlete_config))


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
    if args.json:
        print(json.dumps(workspace_status(), indent=2))
    else:
        for item in readiness():
            scope = ", ".join(item.required_for) or "optional"
            print(f"{item.name}: {item.state} ({scope}) — {item.remediation}")
    return 0
