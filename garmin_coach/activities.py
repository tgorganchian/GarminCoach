"""The activity store: the local CSVs of Garmin activities and their laps."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ACTIVITY_FIELDS = [
    "activity_id", "date", "title",
    "distance_km", "duration_min", "avg_pace_min_km",
    "avg_heart_rate", "max_heart_rate", "elevation_gain_m", "cadence", "calories",
    "stride_length_m", "vo2max",
    "feeling", "perceived_effort",
    "weather_temp_c", "weather_humidity_pct", "weather_lat", "weather_lon",
]
LAP_FIELDS = ["activity_id", "lap_index", "distance_km", "duration_min", "avg_pace_min_km", "avg_hr", "max_hr", "calories"]
# Filled after the Garmin summary arrives; refreshing an activity from Garmin keeps them.
ENRICHED_FIELDS = {"feeling", "perceived_effort", "weather_temp_c", "weather_humidity_pct"}

# Coordinates are rounded to this many decimals before grouping activities
# into a weather-fetch location. 2 decimals (~1km) is already finer than the
# archive API's native grid (~9-11km) — more precision wouldn't add signal,
# it would just fragment nearby runs into separate API calls.
WEATHER_COORD_DECIMALS = 2


class ActivityStore:
    """One row per Garmin activity, keyed by its activity ID, saved without truncation risk."""

    def __init__(self, activities_csv: Path, laps_csv: Path):
        self.activities_csv = Path(activities_csv)
        self.laps_csv = Path(laps_csv)
        self.rows = _unique(_read(self.activities_csv))
        self.laps = _read(self.laps_csv)

    def latest_date(self) -> datetime | None:
        return max((datetime.strptime(row["date"][:10], "%Y-%m-%d") for row in self.rows), default=None)

    def merge(self, garmin_activities: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add unseen Garmin activities and refresh known ones; return only the new rows."""
        known = {_key(row): row for row in self.rows}
        # Rows written before activity IDs were stored can only be matched by date and title.
        legacy = {_legacy_key(row): row for row in self.rows if not _activity_id(row)}
        new_rows = []
        for activity in garmin_activities:
            fresh = row_from_garmin(activity)
            existing = known.get(_key(fresh)) or legacy.pop(_legacy_key(fresh), None)
            if existing is None:
                known[_key(fresh)] = fresh
                new_rows.append(fresh)
            else:
                # A rename or corrected distance replaces the Garmin facts; enrichment stays.
                existing.update({name: value for name, value in fresh.items() if name not in ENRICHED_FIELDS})
        self.rows.extend(new_rows)
        self.rows.sort(key=lambda row: row["date"])
        return new_rows

    def save(self) -> None:
        _write(self.activities_csv, ACTIVITY_FIELDS, self.rows)
        _write(self.laps_csv, LAP_FIELDS, self.laps)


def row_from_garmin(activity: dict[str, Any]) -> dict[str, Any]:
    """Map one Garmin activity summary to an activity row."""
    distance_km = round((activity.get("distance") or 0) / 1000, 2)
    duration_min = round((activity.get("duration") or 0) / 60, 2)
    avg_pace = ""
    if distance_km > 0 and duration_min > 0:
        pace = duration_min / distance_km
        avg_pace = f"{int(pace)}:{int((pace - int(pace)) * 60):02d}"
    lat, lon = activity.get("startLatitude"), activity.get("startLongitude")
    return {
        "activity_id": activity.get("activityId", ""),
        "date": activity.get("startTimeLocal", "")[:10],
        "title": activity.get("activityName", ""),
        "distance_km": distance_km,
        "duration_min": duration_min,
        "avg_pace_min_km": avg_pace,
        "avg_heart_rate": activity.get("averageHR", ""),
        "max_heart_rate": activity.get("maxHR", ""),
        "elevation_gain_m": activity.get("elevationGain", ""),
        "cadence": activity.get("averageRunningCadenceInStepsPerMinute", ""),
        "calories": activity.get("calories", ""),
        "stride_length_m": activity.get("avgStrideLength", ""),
        "vo2max": activity.get("vO2MaxValue", ""),
        "feeling": "",
        "perceived_effort": "",
        "weather_temp_c": "",
        "weather_humidity_pct": "",
        "weather_lat": round(lat, WEATHER_COORD_DECIMALS) if lat is not None else "",
        "weather_lon": round(lon, WEATHER_COORD_DECIMALS) if lon is not None else "",
    }


def _activity_id(row: dict[str, Any]) -> str:
    return str(row.get("activity_id") or "").strip()


def _legacy_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return "legacy", str(row.get("date", ""))[:10], str(row.get("title", ""))


def _key(row: dict[str, Any]) -> tuple[str, ...]:
    activity_id = _activity_id(row)
    return ("id", activity_id) if activity_id else _legacy_key(row)


def _unique(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rows stored twice for one activity (left by older syncs), keeping the latest copy."""
    unique: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in rows:
        unique[_key(row)] = row
    return list(unique.values())


def _read(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    # Swap in one step so a crash mid-write never truncates the athlete's history.
    os.replace(temporary, path)
