"""Load athlete_config.py, the athlete's local data-processing settings, and check its values."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, fields
from datetime import date, datetime
from typing import Any

from garmin_coach.paths import ProjectPaths


class AthleteConfigError(ValueError):
    """athlete_config.py holds a value the sync cannot use; the message names the setting."""


@dataclass(frozen=True)
class AthleteConfig:
    """Each field mirrors the upper-case setting; defaults switch the optional analyses off."""

    hr_zones: tuple[tuple[str, float, float], ...] = ()
    easy_zone_max: int | None = None
    hard_zone_min: int | None = None
    gear_change_date: datetime | None = None
    gear_changes_section: str = ""
    race_calendar: tuple[dict[str, Any], ...] = ()
    long_run_km: float | None = None
    quality_lap_pace_threshold: float | None = None
    min_quality_lap_km: float | None = None
    quality_keywords: tuple[str, ...] = ()
    personal_records: tuple[dict[str, Any], ...] = ()
    weather_lat: float | None = None
    weather_lon: float | None = None
    weather_timezone: str = "auto"


_RACE = {"name": "text", "date": "date", "distance_km": "number", "goal": "text"}
_RECORD = {"label": "text", "date": "text", "distance_m": "number", "time_min": "number"}
_KINDS = {"text": "text", "date": 'a "YYYY-MM-DD" date', "number": "a positive number"}


def load_athlete_config(paths: ProjectPaths) -> AthleteConfig:
    """Run the workspace's athlete_config.py; a missing file leaves every setting at its default."""
    if not paths.athlete_config.exists():
        return AthleteConfig()
    spec = importlib.util.spec_from_file_location("athlete_config", paths.athlete_config)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # the athlete's own file: any failure is a configuration problem
        raise AthleteConfigError(f"athlete_config.py could not be loaded: {exc}") from exc
    settings = {
        item.name: getattr(module, item.name.upper())
        for item in fields(AthleteConfig)
        if hasattr(module, item.name.upper())
    }
    return parse_athlete_config(settings)


def parse_athlete_config(settings: dict[str, Any]) -> AthleteConfig:
    """Check and normalise raw settings keyed by AthleteConfig field name."""
    zones = tuple(_zone(zone) for zone in _items(settings.get("hr_zones"), "HR_ZONES"))
    if any(later[1] < earlier[1] for earlier, later in zip(zones, zones[1:])):
        raise AthleteConfigError("HR_ZONES must run from the lowest zone to the highest")
    easy = _zone_number(settings.get("easy_zone_max"), "EASY_ZONE_MAX", len(zones))
    hard = _zone_number(settings.get("hard_zone_min"), "HARD_ZONE_MIN", len(zones))
    if easy and hard and easy >= hard:
        raise AthleteConfigError("EASY_ZONE_MAX must be lower than HARD_ZONE_MIN")
    return AthleteConfig(
        hr_zones=zones,
        easy_zone_max=easy,
        hard_zone_min=hard,
        gear_change_date=_datetime(settings.get("gear_change_date"), "GEAR_CHANGE_DATE"),
        gear_changes_section=_text(settings.get("gear_changes_section"), "GEAR_CHANGES_SECTION"),
        race_calendar=_entries(settings.get("race_calendar"), "RACE_CALENDAR", _RACE),
        long_run_km=_number(settings.get("long_run_km"), "LONG_RUN_KM", positive=True),
        quality_lap_pace_threshold=_number(settings.get("quality_lap_pace_threshold"), "QUALITY_LAP_PACE_THRESHOLD", positive=True),
        min_quality_lap_km=_number(settings.get("min_quality_lap_km"), "MIN_QUALITY_LAP_KM", positive=True),
        # Titles are compared lower-cased, so a keyword written "Tempo" would otherwise never match.
        quality_keywords=tuple(_text(word, "QUALITY_KEYWORDS").lower() for word in _items(settings.get("quality_keywords"), "QUALITY_KEYWORDS")),
        personal_records=_entries(settings.get("personal_records"), "PERSONAL_RECORDS", _RECORD),
        weather_lat=_number(settings.get("weather_lat"), "WEATHER_LAT"),
        weather_lon=_number(settings.get("weather_lon"), "WEATHER_LON"),
        weather_timezone=_text(settings.get("weather_timezone"), "WEATHER_TIMEZONE") or "auto",
    )


def _items(value: Any, name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise AthleteConfigError(f"{name} must be a list")
    return tuple(value)


def _zone(value: Any) -> tuple[str, float, float]:
    if not (
        isinstance(value, (list, tuple)) and len(value) == 3 and isinstance(value[0], str)
        and _is_number(value[1]) and _is_number(value[2]) and value[1] < value[2]
    ):
        raise AthleteConfigError(f'HR_ZONES entries must look like ("Z2", 120, 145), lower bound first; got {value!r}')
    return value[0], value[1], value[2]


def _zone_number(value: Any, name: str, zone_count: int) -> int | None:
    if value is None:
        return None
    if not (isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= zone_count):
        raise AthleteConfigError(f"{name} must be a zone number from 1 to {zone_count}, the number of HR_ZONES")
    return value


def _datetime(value: Any, name: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str) and _is_iso_date(value):
        return datetime.strptime(value, "%Y-%m-%d")
    raise AthleteConfigError(f'{name} must be a date such as "2026-03-01"')


def _text(value: Any, name: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise AthleteConfigError(f"{name} must be text")
    return value


def _number(value: Any, name: str, positive: bool = False) -> float | None:
    if value is None:
        return None
    if not _is_number(value) or (positive and value <= 0):
        raise AthleteConfigError(f"{name} must be {'a positive' if positive else 'a'} number or None")
    return value


def _entries(value: Any, name: str, required: dict[str, str]) -> tuple[dict[str, Any], ...]:
    entries = _items(value, name)
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise AthleteConfigError(f"{name}[{index}] must be a dict with {', '.join(required)}")
        for key, kind in required.items():
            item = entry.get(key)
            valid = (
                _is_number(item) and item > 0 if kind == "number"
                else isinstance(item, str) and bool(item.strip()) and (kind != "date" or _is_iso_date(item))
            )
            if not valid:
                raise AthleteConfigError(f"{name}[{index}] needs {key} as {_KINDS[kind]}")
    return entries


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
