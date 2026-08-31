"""Resolve the local GarminCoach workspace without exposing configuration values."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

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
        return _configured_path("JOURNAL_PATH", self.coaching / "journal", self.root)

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def activities_csv(self) -> Path:
        return _configured_path("CSV_PATH", self.data / "activities.csv", self.root)

    @property
    def laps_csv(self) -> Path:
        return self.activities_csv.parent / "activity_laps.csv"

    @property
    def token_dir(self) -> Path:
        return _configured_path("GARMIN_TOKEN_DIR", self.root / "garmin_tokens", self.root)

    @property
    def workout_manifest(self) -> Path:
        return self.coaching / "garmin-workouts.manifest.json"

    @property
    def workout_preview(self) -> Path:
        return self.coaching / "garmin-workouts.preview.json"

    @property
    def feedback(self) -> Path:
        return self.root / "feedback"


def _configured_path(name: str, default: Path, root: Path) -> Path:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else root / path


def project_paths(root: Path | None = None) -> ProjectPaths:
    workspace_root = Path(__file__).resolve().parents[1]
    return ProjectPaths((root or workspace_root).resolve())


def load_project_env(paths: ProjectPaths | None = None) -> ProjectPaths:
    paths = paths or project_paths()
    load_dotenv(paths.env_file)
    return paths
