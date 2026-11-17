"""Resolve the local GarminCoach workspace without exposing configuration values."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    # .env values under the real environment, read once so every command resolves the same paths.
    # Kept out of repr so credentials never reach a log or traceback.
    settings: Mapping[str, str] = field(default_factory=dict, compare=False, repr=False)

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    @property
    def athlete_config(self) -> Path:
        return self.root / "athlete_config.py"

    @property
    def coaching(self) -> Path:
        return self.root / "coaching"

    @property
    def athlete_profile(self) -> Path:
        return self.coaching / "athlete-profile.md"

    @property
    def coach_log(self) -> Path:
        return self.coaching / "coach-log.md"

    @property
    def training_plan(self) -> Path:
        return self.coaching / "training-plan.md"

    @property
    def training_history(self) -> Path:
        return self.coaching / "training-history.md"

    @property
    def journal(self) -> Path:
        return self._configured("JOURNAL_PATH", self.coaching / "journal")

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def activities_csv(self) -> Path:
        return self._configured("CSV_PATH", self.data / "activities.csv")

    @property
    def laps_csv(self) -> Path:
        return self.activities_csv.parent / "activity_laps.csv"

    @property
    def token_dir(self) -> Path:
        return self._configured("GARMIN_TOKEN_DIR", self.root / "garmin_tokens")

    @property
    def workout_manifest(self) -> Path:
        return self.coaching / "garmin-workouts.manifest.json"

    @property
    def workout_preview(self) -> Path:
        return self.coaching / "garmin-workouts.preview.json"

    @property
    def feedback(self) -> Path:
        return self.root / "feedback"

    def _configured(self, name: str, default: Path) -> Path:
        value = (self.settings.get(name) or "").strip()
        if not value:
            return default
        path = Path(value)
        return path if path.is_absolute() else self.root / path


def project_paths(root: Path | None = None) -> ProjectPaths:
    workspace_root = (root or Path(__file__).resolve().parents[1]).resolve()
    return ProjectPaths(workspace_root, _settings(workspace_root / ".env"))


def _settings(env_file: Path) -> dict[str, str]:
    values = dotenv_values(env_file) if env_file.exists() else {}
    # The real environment wins, as with python-dotenv's default of not overriding it.
    return {**{name: value for name, value in values.items() if value is not None}, **os.environ}
