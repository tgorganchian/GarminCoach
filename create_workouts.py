"""Crea y agenda en Garmin Connect los workouts estructurados del plan adaptado.

Uso:
    python create_workouts.py            # crea los workouts que falten y los agenda
    python create_workouts.py --delete   # borra los workouts "Coach ..." previamente creados

Login: mismos tokens guardados que sync.py (GARMIN_TOKEN_DIR en .env).
Los workouts se nombran con prefijo "Coach" para distinguirlos de los de Runna.
Si un workout con el mismo nombre ya existe, se saltea (idempotente).
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

# ─── Helpers para armar el JSON de workout-service ───────────────────────────

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
    """'5:05' (min/km) -> velocidad en m/s."""
    m, s = pace_str.split(":")
    return 1000.0 / (int(m) * 60 + int(s))


_step_order = 0


def step(kind, dist_m=None, time_s=None, fast=None, slow=None, desc=None, child=None):
    """Un paso ejecutable. fast/slow = banda de pace 'M:SS' (fast = límite rápido)."""
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
        # Igual que Runna: targetValueOne = velocidad más alta (pace rápido)
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


# ─── Plan de workouts (workout_plan.py, local, gitignored) ─────────────────

def _load_build_workouts():
    """Carga build_workouts() desde workout_plan.py, al lado del script, y le
    inyecta el DSL step/repeat/workout/reset_order para que lo pueda usar sin
    importar nada. Ver workout_plan.example.py para el formato esperado."""
    path = Path(__file__).resolve().parent / "workout_plan.py"
    if not path.exists():
        raise SystemExit(
            "Falta workout_plan.py al lado de este script.\n"
            "Copia workout_plan.example.py -> workout_plan.py y escribi tu plan "
            "(nunca se sube a git, ya esta en .gitignore)."
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
    print("Conectando a Garmin...")
    g = Garmin()
    g.login(tokenstore=GARMIN_TOKEN_DIR)
    print("Login OK")

    existing = {w["workoutName"]: w["workoutId"] for w in g.get_workouts(0, 100)}

    if "--delete" in sys.argv:
        deleted = 0
        for name, wid in existing.items():
            if name.startswith(WORKOUT_PREFIX + " "):
                g.delete_workout(wid)
                print(f"Borrado: {name} ({wid})")
                deleted += 1
        print(f"{deleted} workouts borrados.")
        return

    for wk, date_str in _load_build_workouts()():
        name = wk["workoutName"]
        if name in existing:
            print(f"Ya existe, salteado: {name}")
            continue
        created = g.upload_workout(wk)
        wid = created.get("workoutId")
        g.schedule_workout(wid, date_str)
        print(f"Creado y agendado {date_str}: {name} (id {wid})")

    print("\nListo! Revisa Garmin Connect > Training & Planning > Workouts / Calendar.")
    print("En el reloj: los workouts agendados aparecen en Entrenamiento > Calendario tras sincronizar.")


if __name__ == "__main__":
    main()
