"""Plantilla de plan de workouts para create_workouts.py.

Copia este archivo a workout_plan.py (mismo directorio) y escribi tus propios
workouts. workout_plan.py ya esta en .gitignore — nunca se sube a git.

create_workouts.py inyecta step / repeat / workout / reset_order / WORKOUT_PREFIX
en este archivo antes de ejecutarlo — no hace falta importarlos, ya estan
disponibles cuando build_workouts() corre.
"""


def build_workouts():
    """Devuelve una lista de (workout_json, fecha_agenda 'YYYY-MM-DD')."""
    out = []

    # Ejemplo 1: sesion simple, un solo tramo con banda de pace.
    reset_order()
    out.append((workout(
        f"{WORKOUT_PREFIX} Easy 8km",
        [
            step("interval", dist_m=8000, fast="5:30", slow="5:50",
                 desc="8km easy, que se sienta comodo"),
        ],
    ), "2026-04-06"))

    # Ejemplo 2: warmup + intervalos repetidos + cooldown.
    reset_order()
    out.append((workout(
        f"{WORKOUT_PREFIX} 5x1km Intervals",
        [
            step("warmup", dist_m=2000, desc="2km easy"),
            repeat(5, [
                step("interval", dist_m=1000, fast="4:40", slow="4:50", desc="1km fuerte", child=1),
                step("recovery", time_s=90, desc="90s trote suave", child=1),
            ]),
            step("cooldown", dist_m=2000, desc="2km easy"),
        ],
        "Sesion de intervalos de ejemplo.",
    ), "2026-04-08"))

    return out
