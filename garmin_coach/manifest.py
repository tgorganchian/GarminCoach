"""The local manifest of Garmin workouts this workspace created and still owns."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "entries": {}}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("version") != 1 or not isinstance(value.get("entries"), dict):
        raise ValueError(f"{path}: invalid Garmin workout manifest")
    return value


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Swap in one step: a truncated manifest would orphan every workout it owns.
    os.replace(temporary, path)


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
