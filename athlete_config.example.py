"""Plantilla de config del atleta para sync.py / create_workouts.py.

Copia este archivo a athlete_config.py (mismo directorio) y completa tus datos
reales. athlete_config.py ya esta en .gitignore — nunca se sube a git.

Los valores de abajo son de un atleta ficticio, solo para que el formato quede
claro. Reemplazalos por los tuyos.
"""

from datetime import datetime

# HR zones (Karvonen: %HRR sobre HR reserva, no %HRmax) — deben coincidir con
# lo que le digas a la skill en references/athlete-profile.md.
HR_ZONES = [
    ("Z1 Easy",    120, 135),
    ("Z2 Aerobic", 135, 150),
    ("Z3 Tempo",   150, 165),
    ("Z4 Hard",    165, 180),
    ("Z5 Max",     180, 999),
]

# Si cambiaste de zapatillas o de algo que afecte la interpretacion del HR,
# documentalo aca — la skill lo usa para no confundir un HR mas bajo con
# fitness ganado. Si no aplica, dejalo como string vacio: GEAR_CHANGES_SECTION = "".
GEAR_CHANGE_DATE = datetime(2026, 1, 1)
GEAR_CHANGES_SECTION = """\
## Gear Changes (Important for HR Interpretation)

| Date (approx) | Change | Impact |
|----------------|--------|--------|
| 1 Jan 2026 | Ejemplo: zapatillas nuevas | Ejemplo: HR mas bajo en fondos desde esta fecha |
"""

# Tus carreras — pasadas o futuras. La skill usa esto para el countdown y
# para detectar carreras nuevas en el sync.
RACE_CALENDAR = [
    {
        "name": "10K de ejemplo",
        "date": "2026-04-12",
        "distance_km": 10.0,
        "goal": "Sub-45min",
    },
]

# A partir de que distancia (km) una sesion cuenta como "long run" para vos.
LONG_RUN_KM = 10.0
# Pace de lap (min/km, decimal) para considerar un lap "de calidad" al
# detectar sesiones sin depender solo del titulo.
QUALITY_LAP_PACE_THRESHOLD = 5 + 30 / 60  # 5:30/km
MIN_QUALITY_LAP_KM = 0.3

# ─── VDOT / predicciones de carrera (formula de Jack Daniels) ──────────────
# Tus mejores marcas reales, mas reciente al final si empatan distancia.
PERSONAL_RECORDS = [
    {"distance_m": 5000, "time_min": 25 + 0 / 60, "date": "2026-02-01", "label": "5K"},
    {"distance_m": 10000, "time_min": 52 + 0 / 60, "date": "2026-03-15", "label": "10K"},
]

# ─── Tu plan de entrenamiento semana a semana ───────────────────────────────
# Formato: {numero_de_semana: {"start": "YYYY-MM-DD", "mon"/"wed"/"fri"/"sun": {...} | None}}
# Los dias sin sesion van en None. Los nombres de dia son fijos (mon/wed/fri/sun)
# porque create_workouts.py y el parser de compliance los usan para matchear.
TRAINING_PLAN = {
    1: {"start": "2026-04-01", "mon": None, "wed": {"km": 6, "type": "Easy"}, "fri": {"km": 8, "type": "Tempo"}, "sun": {"km": 10, "type": "Long Run"}},
    2: {"start": "2026-04-08", "mon": {"km": 5, "type": "Easy"}, "wed": {"km": 6, "type": "Intervals"}, "fri": None, "sun": {"km": 12, "type": "Long Run"}},
}

# Coordenadas para el clima (Open-Meteo) — usadas para explicar HR/pace
# anomalos por temperatura/humedad. Poné las de tu ciudad.
WEATHER_LAT = -34.6037
WEATHER_LON = -58.3816
