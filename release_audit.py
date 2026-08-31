"""Fail when public tracked/package files contain local or legacy state."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FORBIDDEN_PATHS = ("docs/superpowers/", "skill/", "create_workouts.py", "workout_plan.example.py")
TEXT_PATTERNS = {
    "local Windows path": re.compile(r"[A-Za-z]:\\Users\\|[A-Za-z]:/Users/"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
CREDENTIAL_PATTERN = re.compile(r"(?m)^(?:GARMIN_EMAIL|GARMIN_PASSWORD|TELEGRAM_API_ID|TELEGRAM_API_HASH)[ \t]*=[ \t]*(?:\"[^\"]+\"|'[^']+'|[^\s#]+)")


def tracked_files() -> list[str]:
    try:
        output = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return package_files()
    return [line.replace("\\", "/") for line in output.splitlines()]


def package_files() -> list[str]:
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    output = subprocess.check_output([npm, "pack", "--dry-run", "--json"], cwd=ROOT, text=True)
    packages = json.loads(output)
    return [item["path"] for item in packages[0]["files"]]


def audit(files: list[str], label: str) -> list[str]:
    existing = [relative for relative in files if (ROOT / relative).exists()]
    failures = [
        f"{label}: forbidden path {path}"
        for path in existing
        if any(path == banned or path.startswith(banned) for banned in FORBIDDEN_PATHS)
        or "/__pycache__/" in f"/{path}"
        or path.endswith(".pyc")
    ]
    for relative in existing:
        path = ROOT / relative
        if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".txt", ".json", ".mjs", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in TEXT_PATTERNS.items():
            if pattern.search(text):
                failures.append(f"{label}: {name} in {relative}")
        if relative.endswith((".env", ".env.example")) and CREDENTIAL_PATTERN.search(text):
            failures.append(f"{label}: filled credential in {relative}")
    return failures


def main() -> int:
    failures = audit(tracked_files(), "tracked") + audit(package_files(), "package")
    if failures:
        print("Public-release audit failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        return 1
    print("Public-release audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
