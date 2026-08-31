"""Validated PLAN-DATA model shared by compliance and Garmin rendering."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any


class PlanValidationError(ValueError):
    """A user-facing validation error with the location inside PLAN-DATA."""


_PLAN_BLOCK = re.compile(r"```plan-data\s*\n(.*?)\n```", re.DOTALL)
_STEP_KINDS = {"warmup", "cooldown", "interval", "recovery", "repeat"}
_PACE = re.compile(r"^\d{1,2}:[0-5]\d/km$")


@dataclass(frozen=True)
class Target:
    kind: str
    minimum: str | int | None = None
    maximum: str | int | None = None


@dataclass(frozen=True)
class Step:
    kind: str
    distance_m: int | None = None
    time_s: int | None = None
    target: Target | None = None
    count: int | None = None
    steps: tuple["Step", ...] = ()

    def total_distance_m(self) -> int | None:
        if self.distance_m is not None:
            return self.distance_m
        if self.kind != "repeat":
            return 0
        distances = [step.total_distance_m() for step in self.steps]
        return None if any(value is None for value in distances) else self.count * sum(distances)


@dataclass(frozen=True)
class PlanSession:
    id: str
    date: date
    name: str
    steps: tuple[Step, ...]

    @property
    def planned_distance_m(self) -> int | None:
        distances = [step.total_distance_m() for step in self.steps]
        return None if any(value is None for value in distances) else sum(distances)


@dataclass(frozen=True)
class TrainingPlan:
    version: int
    id: str
    status: str
    sessions: tuple[PlanSession, ...]

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def sessions_in_window(self, start: date, days: int) -> tuple[PlanSession, ...]:
        end = start + timedelta(days=days - 1)
        return tuple(session for session in self.sessions if start <= session.date <= end)

    def sessions_by_week(self) -> dict[date, tuple[PlanSession, ...]]:
        weeks: dict[date, list[PlanSession]] = {}
        for session in self.sessions:
            monday = session.date - timedelta(days=session.date.weekday())
            weeks.setdefault(monday, []).append(session)
        return {week: tuple(sorted(items, key=lambda item: item.date)) for week, items in weeks.items()}


def parse_training_plan(path: str | Path) -> TrainingPlan:
    path = Path(path)
    if not path.exists():
        raise PlanValidationError(f"{path}: training plan is missing")
    blocks = _PLAN_BLOCK.findall(path.read_text(encoding="utf-8"))
    if len(blocks) != 1:
        raise PlanValidationError(f"{path}: expected exactly one ```plan-data block, found {len(blocks)}")
    try:
        raw = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise PlanValidationError(f"{path}: invalid PLAN-DATA JSON at line {exc.lineno}: {exc.msg}") from exc
    return _parse_plan(raw, str(path))


def no_active_plan() -> TrainingPlan:
    return TrainingPlan(version=1, id="no-active-plan", status="none", sessions=())


def _parse_plan(raw: Any, location: str) -> TrainingPlan:
    if not isinstance(raw, dict):
        _error(location, "must be an object")
    if raw.get("version") != 1:
        _error(location, "version must be 1")
    plan = raw.get("plan")
    if not isinstance(plan, dict):
        _error(location, "plan must be an object")
    plan_id = _string(plan.get("id"), f"{location}.plan.id")
    status = plan.get("status")
    if status not in {"active", "none"}:
        _error(f"{location}.plan.status", 'must be "active" or "none"')
    raw_sessions = raw.get("sessions")
    if not isinstance(raw_sessions, list):
        _error(location, "sessions must be an array")
    if status == "none" and raw_sessions:
        _error(location, 'a status of "none" requires an empty sessions array')
    sessions = tuple(_parse_session(value, f"{location}.sessions[{index}]") for index, value in enumerate(raw_sessions))
    ids = [session.id for session in sessions]
    if len(ids) != len(set(ids)):
        _error(location, "session IDs must be unique")
    return TrainingPlan(version=1, id=plan_id, status=status, sessions=tuple(sorted(sessions, key=lambda item: item.date)))


def _parse_session(raw: Any, location: str) -> PlanSession:
    if not isinstance(raw, dict):
        _error(location, "must be an object")
    session_id = _string(raw.get("id"), f"{location}.id")
    name = _string(raw.get("name"), f"{location}.name")
    try:
        session_date = date.fromisoformat(_string(raw.get("date"), f"{location}.date"))
    except ValueError as exc:
        raise PlanValidationError(f"{location}.date: must use YYYY-MM-DD") from exc
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        _error(location, "steps must be a non-empty array")
    return PlanSession(session_id, session_date, name, tuple(_parse_step(step, f"{location}.steps[{index}]") for index, step in enumerate(raw_steps)))


def _parse_step(raw: Any, location: str) -> Step:
    if not isinstance(raw, dict):
        _error(location, "must be an object")
    kind = raw.get("kind")
    if kind not in _STEP_KINDS:
        _error(f"{location}.kind", f"must be one of {', '.join(sorted(_STEP_KINDS))}")
    if kind == "repeat":
        count = _positive_int(raw.get("count"), f"{location}.count")
        children = raw.get("steps")
        if not isinstance(children, list) or not children:
            _error(location, "repeat steps must be a non-empty array")
        return Step(kind=kind, count=count, steps=tuple(_parse_step(step, f"{location}.steps[{index}]") for index, step in enumerate(children)))
    distance_m = raw.get("distance_m")
    time_s = raw.get("time_s")
    if (distance_m is None) == (time_s is None):
        _error(location, "must define exactly one of distance_m or time_s")
    target = _parse_target(raw.get("target"), f"{location}.target") if "target" in raw else None
    return Step(
        kind=kind,
        distance_m=_positive_int(distance_m, f"{location}.distance_m") if distance_m is not None else None,
        time_s=_positive_int(time_s, f"{location}.time_s") if time_s is not None else None,
        target=target,
    )


def _parse_target(raw: Any, location: str) -> Target:
    if not isinstance(raw, dict):
        _error(location, "must be an object")
    kind = raw.get("kind")
    if kind not in {"pace", "heart_rate"}:
        _error(f"{location}.kind", 'must be "pace" or "heart_rate"')
    minimum, maximum = raw.get("min"), raw.get("max")
    if minimum is None or maximum is None:
        _error(location, "requires min and max")
    if kind == "pace":
        if not isinstance(minimum, str) or not isinstance(maximum, str) or not _PACE.fullmatch(minimum) or not _PACE.fullmatch(maximum):
            _error(location, 'pace targets must use M:SS/km')
        if _pace_seconds(minimum) > _pace_seconds(maximum):
            _error(location, "pace target min must be faster than or equal to max")
    elif not isinstance(minimum, int) or not isinstance(maximum, int) or minimum <= 0 or maximum <= 0:
        _error(location, "heart-rate targets must be positive integers")
    elif minimum > maximum:
        _error(location, "heart-rate target min must be less than or equal to max")
    return Target(kind, minimum, maximum)


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _error(location, "must be a non-empty string")
    return value.strip()


def _positive_int(value: Any, location: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _error(location, "must be a positive integer")
    return value


def _pace_seconds(value: str) -> int:
    minutes, seconds = value.removesuffix("/km").split(":")
    return int(minutes) * 60 + int(seconds)


def _error(location: str, message: str) -> None:
    raise PlanValidationError(f"{location}: {message}")
