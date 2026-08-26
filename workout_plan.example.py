"""Workout plan template for create_workouts.py.

Copy this file to workout_plan.py (same directory) and write your own
workouts. workout_plan.py is already in .gitignore — never committed to git.

create_workouts.py injects step / repeat / workout / reset_order / WORKOUT_PREFIX
into this file before running it — no need to import them, they're already
available when build_workouts() runs.
"""


def build_workouts():
    """Returns a list of (workout_json, schedule_date 'YYYY-MM-DD')."""
    out = []

    # Example 1: simple session, a single segment with a pace band.
    reset_order()
    out.append((workout(
        f"{WORKOUT_PREFIX} Easy 8km",
        [
            step("interval", dist_m=8000, fast="5:30", slow="5:50",
                 desc="8km easy, keep it comfortable"),
        ],
    ), "2026-04-06"))

    # Example 2: warmup + repeated intervals + cooldown.
    reset_order()
    out.append((workout(
        f"{WORKOUT_PREFIX} 5x1km Intervals",
        [
            step("warmup", dist_m=2000, desc="2km easy"),
            repeat(5, [
                step("interval", dist_m=1000, fast="4:40", slow="4:50", desc="1km hard", child=1),
                step("recovery", time_s=90, desc="90s easy jog", child=1),
            ]),
            step("cooldown", dist_m=2000, desc="2km easy"),
        ],
        "Example interval session.",
    ), "2026-04-08"))

    return out
