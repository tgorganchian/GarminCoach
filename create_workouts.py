"""Creates and schedules the adapted plan's structured workouts in Garmin Connect.

Usage:
    python create_workouts.py            # creates any missing workouts and schedules them
    python create_workouts.py --delete   # deletes previously created "Coach ..." workouts

Login: same saved tokens as sync.py (GARMIN_TOKEN_DIR in .env).
Workouts are named with a "Coach" prefix to tell them apart from Runna's.
If a workout with the same name already exists, it's skipped (idempotent).
"""

import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from garminconnect import Garmin

load_dotenv(Path(__file__).resolve().parent / ".env")

GARMIN_TOKEN_DIR = os.getenv("GARMIN_TOKEN_DIR")

WORKOUT_PREFIX = "Coach"

# ─── Helpers to build the workout-service JSON ───────────────────────────

RUNNING = {"sportTypeId": 1, "sportTypeKey": "running"}
KM_UNIT = {"unitId": 2, "unitKey": "kilometer", "factor": 100000.0}

STEP_TYPES = {
    "warmup": {"stepTypeId": 1, "stepTypeKey": "warmup"},
    "cooldown": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
    "interval": {"stepTypeId": 3, "stepTypeKey": "interval"},
    "recovery": {"stepTypeId": 4, "stepTypeKey": "recovery"},
    "rest": {"stepTypeId": 5, "stepTypeKey": "rest"},
    "repeat": {"stepTypeId": 6, "stepTypeKey": "repeat"},
}

END_DISTANCE = {"conditionTypeId": 3, "conditionTypeKey": "distance"}
END_TIME = {"conditionTypeId": 2, "conditionTypeKey": "time"}

TARGET_PACE = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
TARGET_NONE = {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}


def pace_to_mps(pace_str: str) -> float:
    """'5:05' (min/km) -> speed in m/s."""
    m, s = pace_str.split(":")
    return 1000.0 / (int(m) * 60 + int(s))


_step_order = 0


def step(kind, dist_m=None, time_s=None, fast=None, slow=None, desc=None, child=None):
    """An executable step. fast/slow = pace band 'M:SS' (fast = faster bound)."""
    global _step_order
    _step_order += 1
    s = {
        "type": "ExecutableStepDTO",
        "stepId": None,
        "stepOrder": _step_order,
        "stepType": STEP_TYPES[kind],
        "endConditionCompare": None,
        "preferredEndConditionUnit": KM_UNIT if dist_m else None,
    }
    if child is not None:
        s["childStepId"] = child
    if dist_m:
        s["endCondition"] = END_DISTANCE
        s["endConditionValue"] = float(dist_m)
    else:
        s["endCondition"] = END_TIME
        s["endConditionValue"] = float(time_s)
    if fast and slow:
        s["targetType"] = TARGET_PACE
        # Same as Runna: targetValueOne = higher speed (faster pace)
        s["targetValueOne"] = pace_to_mps(fast)
        s["targetValueTwo"] = pace_to_mps(slow)
    else:
        s["targetType"] = TARGET_NONE
        s["targetValueOne"] = None
        s["targetValueTwo"] = None
    if desc:
        s["description"] = desc
    return s


def repeat(iterations, child_steps):
    global _step_order
    _step_order += 1
    return {
        "type": "RepeatGroupDTO",
        "stepId": None,
        "stepOrder": _step_order,
        "stepType": STEP_TYPES["repeat"],
        "childStepId": 1,
        "numberOfIterations": iterations,
        "smartRepeat": False,
        "workoutSteps": child_steps,
    }


def workout(name, steps, description=None):
    return {
        "workoutName": name,
        "description": description,
        "sportType": RUNNING,
        "workoutSegments": [
            {"segmentOrder": 1, "sportType": RUNNING, "workoutSteps": steps}
        ],
    }


def reset_order():
    global _step_order
    _step_order = 0


# ─── Workout plan (workout_plan.py, local, gitignored) ─────────────────

def _load_build_workouts():
    """Loads build_workouts() from workout_plan.py, next to this script, and
    injects the step/repeat/workout/reset_order DSL so it can be used without
    importing anything. See workout_plan.example.py for the expected format."""
    path = Path(__file__).resolve().parent / "workout_plan.py"
    if not path.exists():
        raise SystemExit(
            "Missing workout_plan.py next to this script.\n"
            "Copy workout_plan.example.py -> workout_plan.py and write your plan "
            "(never committed, already in .gitignore)."
        )
    spec = importlib.util.spec_from_file_location("workout_plan", path)
    module = importlib.util.module_from_spec(spec)
    module.step = step
    module.repeat = repeat
    module.workout = workout
    module.reset_order = reset_order
    module.WORKOUT_PREFIX = WORKOUT_PREFIX
    spec.loader.exec_module(module)
    return module.build_workouts


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to Garmin...")
    g = Garmin()
    g.login(tokenstore=GARMIN_TOKEN_DIR)
    print("Login OK")

    existing = {w["workoutName"]: w["workoutId"] for w in g.get_workouts(0, 100)}

    if "--delete" in sys.argv:
        deleted = 0
        for name, wid in existing.items():
            if name.startswith(WORKOUT_PREFIX + " "):
                g.delete_workout(wid)
                print(f"Deleted: {name} ({wid})")
                deleted += 1
        print(f"{deleted} workouts deleted.")
        return

    for wk, date_str in _load_build_workouts()():
        name = wk["workoutName"]
        if name in existing:
            print(f"Already exists, skipped: {name}")
            continue
        created = g.upload_workout(wk)
        wid = created.get("workoutId")
        g.schedule_workout(wid, date_str)
        print(f"Created and scheduled {date_str}: {name} (id {wid})")

    print("\nDone! Check Garmin Connect > Training & Planning > Workouts / Calendar.")
    print("On the watch: scheduled workouts appear under Training > Calendar after syncing.")


if __name__ == "__main__":
    main()
