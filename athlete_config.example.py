"""Athlete config template for sync.py / create_workouts.py.

Copy this file to athlete_config.py (same directory) and fill in your real
data. athlete_config.py is already in .gitignore — never committed to git.

The values below belong to a fictional athlete, just to show the expected
format. Replace them with your own.
"""

from datetime import datetime

# HR zones (Karvonen: %HRR over HR reserve, not %HRmax) — must match what
# you tell the skill in references/athlete-profile.md.
HR_ZONES = [
    ("Z1 Easy",    120, 135),
    ("Z2 Aerobic", 135, 150),
    ("Z3 Tempo",   150, 165),
    ("Z4 Hard",    165, 180),
    ("Z5 Max",     180, 999),
]

# If you changed shoes or anything else that affects how HR should be read,
# document it here — the skill uses this to avoid mistaking a lower HR for
# fitness gained. If it doesn't apply, leave it as an empty string: GEAR_CHANGES_SECTION = "".
GEAR_CHANGE_DATE = datetime(2026, 1, 1)
GEAR_CHANGES_SECTION = """\
## Gear Changes (Important for HR Interpretation)

| Date (approx) | Change | Impact |
|----------------|--------|--------|
| 1 Jan 2026 | Example: new shoes | Example: lower HR on easy runs since this date |
"""

# Your races — past or upcoming. The skill uses this for the countdown and
# to detect new races during sync.
RACE_CALENDAR = [
    {
        "name": "Example 10K",
        "date": "2026-04-12",
        "distance_km": 10.0,
        "goal": "Sub-45min",
    },
]

# From what distance (km) a session counts as a "long run" for you.
LONG_RUN_KM = 10.0
# Lap pace (min/km, decimal) to consider a lap "quality" when detecting
# sessions without relying solely on the title.
QUALITY_LAP_PACE_THRESHOLD = 5 + 30 / 60  # 5:30/km
MIN_QUALITY_LAP_KM = 0.3

# Keywords in the activity title that flag it as a quality session (matched
# case-insensitively). Adjust this to the vocabulary you or your training
# app use (Runna, TrainingPeaks, titles you set by hand, etc.) — entirely
# up to you. Spanish entries are kept here since they're what this athlete's
# own activity titles use; swap in whatever language yours are in.
QUALITY_KEYWORDS = [
    "interval", "tempo", "fartlek", "repetici", "series", "800m", "1000m",
    "400m", "umbral", "threshold", "race", "carrera", "5k", "10k", "competencia",
    "stairway", "pyramid", "piramide", "rolling", "cruise", "200m", "300m", "600m",
]

# ─── VDOT / race predictions (Jack Daniels formula) ──────────────
# Your real best marks, most recent last if tied on distance.
PERSONAL_RECORDS = [
    {"distance_m": 5000, "time_min": 25 + 0 / 60, "date": "2026-02-01", "label": "5K"},
    {"distance_m": 10000, "time_min": 52 + 0 / 60, "date": "2026-03-15", "label": "10K"},
]

# ─── Your week-by-week training plan ───────────────────────────────
# Format: {week_number: {"start": "YYYY-MM-DD", "mon"/"tue"/"wed"/"thu"/"fri"/"sat"/"sun": {...} | None}}
# Use any subset of the 7 days — whichever you actually train (see the
# "Day availability" table in references/athlete-profile.md; if you're
# chatting with the skill to build the plan, that's where you tell it which
# days you have free). Days without a session go in as None or are simply omitted.
# The day NAMES (mon/tue/wed/thu/fri/sat/sun) are fixed because
# create_workouts.py and the compliance parser use them for matching — but
# you can use any combination of them, they don't need to be 4 or exactly these.
TRAINING_PLAN = {
    1: {"start": "2026-04-01", "mon": None, "wed": {"km": 6, "type": "Easy"}, "fri": {"km": 8, "type": "Tempo"}, "sun": {"km": 10, "type": "Long Run"}},
    2: {"start": "2026-04-08", "mon": {"km": 5, "type": "Easy"}, "wed": {"km": 6, "type": "Intervals"}, "fri": None, "sun": {"km": 12, "type": "Long Run"}},
}

# Fallback coordinates for weather (Open-Meteo) — used to explain HR/pace
# anomalies from temperature/humidity. sync.py prefers each activity's own
# GPS start coordinates; these are only used when an activity has none
# (treadmill, indoor, GPS didn't lock). Put your city's here.
WEATHER_LAT = -34.6037
WEATHER_LON = -58.3816
