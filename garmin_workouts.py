"""Preview and apply manifest-owned Garmin workouts from PLAN-DATA."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from garmin_coach.paths import load_project_env, project_paths
from garmin_coach.plan import PlanSession, PlanValidationError, Step, TrainingPlan, parse_training_plan


RUNNING = {"sportTypeId": 1, "sportTypeKey": "running"}
KM_UNIT = {"unitId": 2, "unitKey": "kilometer", "factor": 100000.0}
STEP_TYPES = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval"},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery"},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat"},
}
END_DISTANCE = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
END_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time"}
TARGET_NONE = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}
TARGET_PACE = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
TARGET_HEART_RATE = {"workoutTargetTypeId": 3, "workoutTargetTypeKey": "heart.rate.zone"}


@dataclass(frozen=True)
class Action:
    kind: str
    session_id: str
    date: str
    name: str
    fingerprint: str | None = None
    remote_workout_id: int | None = None
    scheduled_workout_id: int | None = None
    expected_remote_name: str | None = None
    expected_scheduled_date: str | None = None


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def pace_to_mps(value: str) -> float:
    minutes, seconds = value.removesuffix("/km").split(":")
    return 1000.0 / (int(minutes) * 60 + int(seconds))


def render_session(session: PlanSession) -> dict[str, Any]:
    order = [0]
    return {
        "workoutName": workout_name(session),
        "description": f"GarminCoach session {session.id}",
        "sportType": RUNNING,
        "workoutSegments": [{"segmentOrder": 1, "sportType": RUNNING, "workoutSteps": [_render_step(step, order) for step in session.steps]}],
    }


def workout_name(session: PlanSession) -> str:
    return f"GarminCoach {session.date.isoformat()} — {session.name} [{session.id}]"


def _render_step(step: Step, order: list[int], child: int | None = None) -> dict[str, Any]:
    order[0] += 1
    if step.kind == "repeat":
        return {
            "type": "RepeatGroupDTO",
            "stepId": None,
            "stepOrder": order[0],
            "stepType": STEP_TYPES["repeat"],
            "childStepId": 1,
            "numberOfIterations": step.count,
            "smartRepeat": False,
            "workoutSteps": [_render_step(item, order, child=1) for item in step.steps],
        }
    rendered = {
        "type": "ExecutableStepDTO",
        "stepId": None,
        "stepOrder": order[0],
        "stepType": STEP_TYPES[step.kind],
        "endConditionCompare": None,
        "preferredEndConditionUnit": KM_UNIT if step.distance_m else None,
        "endCondition": END_DISTANCE if step.distance_m else END_TIME,
        "endConditionValue": float(step.distance_m or step.time_s),
        "targetType": TARGET_NONE,
        "targetValueOne": None,
        "targetValueTwo": None,
    }
    if child is not None:
        rendered["childStepId"] = child
    if step.target:
        rendered["targetType"] = TARGET_PACE if step.target.kind == "pace" else TARGET_HEART_RATE
        if step.target.kind == "pace":
            rendered["targetValueOne"] = pace_to_mps(str(step.target.minimum))
            rendered["targetValueTwo"] = pace_to_mps(str(step.target.maximum))
        else:
            rendered["targetValueOne"] = step.target.minimum
            rendered["targetValueTwo"] = step.target.maximum
    return rendered


def reconcile(plan: TrainingPlan, manifest: dict[str, Any], start: date, days: int) -> list[Action]:
    if days < 14:
        raise ValueError("Workout coverage must be at least 14 days.")
    sessions = plan.sessions_in_window(start, days) if plan.is_active else ()
    entries = manifest.get("entries", {})
    actions: list[Action] = []
    expected_ids = set()
    for session in sessions:
        expected_ids.add(session.id)
        payload = render_session(session)
        digest = fingerprint(payload)
        existing = entries.get(session.id)
        if not existing:
            actions.append(Action("create", session.id, session.date.isoformat(), payload["workoutName"], digest))
        elif existing["fingerprint"] != digest:
            actions.append(Action("update", session.id, session.date.isoformat(), payload["workoutName"], digest, existing["remote_workout_id"], existing.get("scheduled_workout_id"), existing["name"], existing["date"]))
        elif existing["date"] != session.date.isoformat():
            actions.append(Action("reschedule", session.id, session.date.isoformat(), payload["workoutName"], digest, existing["remote_workout_id"], existing.get("scheduled_workout_id"), existing["name"], existing["date"]))
        else:
            actions.append(Action("unchanged", session.id, session.date.isoformat(), payload["workoutName"], digest, existing["remote_workout_id"], existing.get("scheduled_workout_id"), existing["name"], existing["date"]))
    end = date.fromordinal(start.toordinal() + days - 1).isoformat()
    for session_id, entry in entries.items():
        if session_id not in expected_ids and start.isoformat() <= entry["date"] <= end:
            actions.append(Action("unschedule", session_id, entry["date"], entry["name"], entry["fingerprint"], entry["remote_workout_id"], entry.get("scheduled_workout_id"), entry["name"], entry["date"]))
    return sorted(actions, key=lambda action: (action.date, action.session_id, action.kind))


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "entries": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or not isinstance(value.get("entries"), dict):
        raise ValueError(f"{path}: invalid Garmin workout manifest")
    return value


def managed_coverage_days(manifest: dict[str, Any], start: date) -> int:
    dates = []
    for entry in manifest.get("entries", {}).values():
        try:
            scheduled = date.fromisoformat(entry["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if scheduled >= start:
            dates.append(scheduled)
    return max((scheduled - start).days + 1 for scheduled in dates) if dates else 0


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preview_document(actions: list[Action], start: date, days: int) -> dict[str, Any]:
    action_data = [asdict(action) for action in actions]
    preview_id = fingerprint({"start": start.isoformat(), "days": days, "actions": action_data})
    return {"version": 1, "id": preview_id, "start": start.isoformat(), "days": days, "actions": action_data}


def save_preview(path: Path, preview: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class GarminGateway:
    def __init__(self, token_dir: Path):
        from garminconnect import Garmin

        self.client = Garmin()
        self.client.login(tokenstore=str(token_dir))

    def verify_owned(self, action: Action) -> None:
        remote = self.client.get_workout_by_id(action.remote_workout_id)
        if remote.get("workoutName") != action.expected_remote_name:
            raise RuntimeError(f"Remote workout name changed for {action.session_id}; refusing to modify it.")
        if action.scheduled_workout_id is not None:
            scheduled = self.client.get_scheduled_workout_by_id(action.scheduled_workout_id)
            remote_id = _nested_value(scheduled, ("workoutId", "workout_id"))
            scheduled_date = _nested_value(scheduled, ("date", "scheduleDate", "scheduledDate"))
            if str(remote_id) != str(action.remote_workout_id) or not isinstance(scheduled_date, str) or not scheduled_date.startswith(action.expected_scheduled_date):
                raise RuntimeError(f"Remote workout schedule changed for {action.session_id}; refusing to modify it.")

    def apply(self, action: Action, payload: dict[str, Any] | None) -> tuple[int | None, int | None]:
        if action.kind == "create":
            created = self.client.upload_workout(payload)
            workout_id = int(created["workoutId"])
            scheduled = self.client.schedule_workout(workout_id, action.date)
            return workout_id, _scheduled_id(scheduled)
        self.verify_owned(action)
        if action.kind == "update":
            self.client.update_workout(action.remote_workout_id, payload)
        elif action.kind == "reschedule":
            if action.scheduled_workout_id is None:
                raise RuntimeError(f"{action.session_id} has no known scheduled-workout ID; refusing to reschedule.")
            self.client.unschedule_workout(action.scheduled_workout_id)
            scheduled = self.client.schedule_workout(action.remote_workout_id, action.date)
            return action.remote_workout_id, _scheduled_id(scheduled)
        elif action.kind == "unschedule":
            if action.scheduled_workout_id is None:
                raise RuntimeError(f"{action.session_id} has no known scheduled-workout ID; refusing to unschedule.")
            self.client.unschedule_workout(action.scheduled_workout_id)
            return action.remote_workout_id, None
        return action.remote_workout_id, action.scheduled_workout_id


def _scheduled_id(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    for key in ("scheduledWorkoutId", "scheduledWorkoutID", "id"):
        if value.get(key) is not None:
            return int(value[key])
    return None


def _nested_value(value: Any, names: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
        for child in value.values():
            found = _nested_value(child, names)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _nested_value(child, names)
            if found is not None:
                return found
    return None


def execute_apply(plan: TrainingPlan, actions: list[Action], manifest: dict[str, Any], gateway: GarminGateway) -> dict[str, Any]:
    entries = manifest["entries"]
    sessions = {session.id: session for session in plan.sessions}
    for action in actions:
        if action.kind == "unchanged":
            continue
        payload = render_session(sessions[action.session_id]) if action.kind in {"create", "update"} else None
        remote_id, scheduled_id = gateway.apply(action, payload)
        if action.kind == "update" and entries[action.session_id]["date"] != action.date:
            reschedule = Action("reschedule", action.session_id, action.date, action.name, action.fingerprint, remote_id, scheduled_id or action.scheduled_workout_id, action.name, entries[action.session_id]["date"])
            remote_id, scheduled_id = gateway.apply(reschedule, None)
        if action.kind == "unschedule":
            entries.pop(action.session_id, None)
        else:
            entries[action.session_id] = {
                "remote_workout_id": remote_id,
                "scheduled_workout_id": scheduled_id if scheduled_id is not None else action.scheduled_workout_id,
                "date": action.date,
                "name": action.name,
                "fingerprint": action.fingerprint,
            }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["preview"], default="preview")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--apply", metavar="PREVIEW_ID", help="apply exactly the saved preview after user confirmation")
    args = parser.parse_args()
    if args.days < 14:
        parser.error("--days must be at least 14")
    paths = load_project_env(project_paths())
    try:
        plan = parse_training_plan(paths.training_plan)
    except PlanValidationError as exc:
        raise SystemExit(f"Plan rendering is unavailable: {exc}") from exc
    if not plan.is_active:
        raise SystemExit("No active plan is confirmed. Rendering is unavailable until a plan is approved.")
    manifest = load_manifest(paths.workout_manifest)
    actions = reconcile(plan, manifest, date.today(), args.days)
    preview = preview_document(actions, date.today(), args.days)
    if not args.apply:
        save_preview(paths.workout_preview, preview)
        print(json.dumps(preview, indent=2))
        print(f"Confirm this preview, then run: python garmin_workouts.py --days {args.days} --apply {preview['id']}")
        return 0
    if not paths.workout_preview.exists():
        raise SystemExit("No saved preview exists. Run preview first.")
    saved = json.loads(paths.workout_preview.read_text(encoding="utf-8"))
    if args.apply != saved.get("id") or preview != saved:
        raise SystemExit("Preview changed or does not match --apply. Review a new preview before remote writes.")
    updated = execute_apply(plan, actions, manifest, GarminGateway(paths.token_dir))
    write_manifest(paths.workout_manifest, updated)
    print("Applied the confirmed manifest-owned workout preview.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
