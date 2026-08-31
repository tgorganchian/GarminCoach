import io
import json
import math
import os
import re
import sys
import csv
import time
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import requests

from garminconnect import Garmin

from garmin_coach.paths import load_project_env, project_paths
from garmin_coach.plan import PlanValidationError, TrainingPlan, no_active_plan, parse_training_plan
from garmin_coach.readiness import is_ready, readiness
from garmin_workouts import load_manifest, managed_coverage_days

# Load local variables without imposing machine-specific absolute paths.
PATHS = load_project_env(project_paths())

try:
    import athlete_config as cfg
except ModuleNotFoundError:
    cfg = None

# ─── CONFIG ───────────────────────────────────────────────
GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")

# Start date for requesting history from Garmin
HISTORY_START_DATE = "2024-01-01"
# Days of overlap when fetching "only what's new" (time zones / late sync)
INCREMENTAL_OVERLAP_DAYS = 3
# Set True ONCE if the CSV only had a short stretch and you want to pull the FULL history
# (takes longer; set back to False when done)
FULL_BACKFILL = False
# Set False to skip lap fetching (e.g. if hitting Garmin rate limits)
FETCH_LAPS = True
# Set True ONCE to fetch laps for ALL historical activities; then set back to False
BACKFILL_LAPS = False
# Set False to skip downloading FIT files for self-evaluation + training metrics
FETCH_SELF_EVAL = True
# Set True ONCE to fetch self-eval for ALL historical activities; then set back to False
BACKFILL_SELF_EVAL = False

CSV_PATH = str(PATHS.activities_csv)
GARMIN_TOKEN_DIR = str(PATHS.token_dir)
TRAINING_HISTORY_PATH = str(PATHS.training_history)
LAPS_CSV_PATH = str(PATHS.laps_csv)

# ─── Athlete config (athlete_config.py, local, gitignored) ──────────────
GEAR_CHANGES_SECTION = getattr(cfg, "GEAR_CHANGES_SECTION", "")
HR_ZONES = getattr(cfg, "HR_ZONES", [])
GEAR_CHANGE_DATE = getattr(cfg, "GEAR_CHANGE_DATE", None)
RACE_CALENDAR = getattr(cfg, "RACE_CALENDAR", [])
LONG_RUN_KM = getattr(cfg, "LONG_RUN_KM", 0)
QUALITY_LAP_PACE_THRESHOLD = getattr(cfg, "QUALITY_LAP_PACE_THRESHOLD", 0)
MIN_QUALITY_LAP_KM = getattr(cfg, "MIN_QUALITY_LAP_KM", 0)
QUALITY_KEYWORDS = getattr(cfg, "QUALITY_KEYWORDS", [])
PERSONAL_RECORDS = getattr(cfg, "PERSONAL_RECORDS", [])
WEATHER_LAT = getattr(cfg, "WEATHER_LAT", None)
WEATHER_LON = getattr(cfg, "WEATHER_LON", None)
WEATHER_TIMEZONE = getattr(cfg, "WEATHER_TIMEZONE", "auto") or "auto"
ACTIVE_PLAN: TrainingPlan = no_active_plan()
PLAN_ERROR: str | None = None
# ──────────────────────────────────────────────────────────



def _int_or_none(v):
    return int(float(v)) if v not in ("", None) else None


def _float_or_none(v, ndigits=1):
    return round(float(v), ndigits) if v not in ("", None) else None


def _parse_activities(rows):
    """Converts CSV rows into dicts with correct types."""
    result = []
    for row in rows:
        try:
            date = datetime.strptime(row["date"][:10], "%Y-%m-%d")
            result.append({
                "date": date,
                "title": row.get("title", ""),
                "distance_km": float(row.get("distance_km") or 0),
                "duration_min": float(row.get("duration_min") or 0),
                "avg_pace": row.get("avg_pace_min_km", ""),
                "avg_hr": _int_or_none(row.get("avg_heart_rate", "")),
                "max_hr": _int_or_none(row.get("max_heart_rate", "")),
                "elevation_m": _float_or_none(row.get("elevation_gain_m", "")),
                "cadence": _int_or_none(row.get("cadence", "")),
                "calories": _int_or_none(row.get("calories", "")),
                "activity_id": row.get("activity_id", "") or None,
                "stride_length_m": _float_or_none(row.get("stride_length_m", ""), ndigits=2),
                "vo2max": _float_or_none(row.get("vo2max", "")),
                "feeling": row.get("feeling", ""),
                "perceived_effort": _int_or_none(row.get("perceived_effort", "")),
                "weather_temp_c": _float_or_none(row.get("weather_temp_c", "")),
                "weather_humidity_pct": _int_or_none(row.get("weather_humidity_pct", "")),
            })
        except Exception:
            continue
    return result


def _week_start(dt):
    """Monday of dt's week."""
    return dt - timedelta(days=dt.weekday())


def _pace_to_decimal(pace_str):
    """'5:31' -> 5.5166. None si no parseable."""
    if not pace_str or ":" not in pace_str:
        return None
    try:
        mins, secs = pace_str.split(":")
        return int(mins) + int(secs) / 60
    except Exception:
        return None


def _decimal_to_pace(dec):
    """5.5166 -> '5:31'."""
    if dec is None:
        return "—"
    mins = int(dec)
    secs = int(round((dec - mins) * 60))
    if secs == 60:
        mins += 1
        secs = 0
    return f"{mins}:{secs:02d}"


# Keywords that need a word-boundary check because they collide with
# common distance suffixes (e.g. "5k" matches inside "15km Long Run").
_WORD_BOUNDARY_KEYWORDS = {"5k", "10k"}


def _title_has_keyword(title_lower, kw):
    if kw in _WORD_BOUNDARY_KEYWORDS:
        # "5k" must not be followed by a letter (blocks "5km", "5kilo", etc.)
        return bool(re.search(re.escape(kw) + r"(?![a-z])", title_lower))
    return kw in title_lower


def _is_quality(a, quality_keywords):
    title_lower = a["title"].lower()
    return any(_title_has_keyword(title_lower, kw) for kw in quality_keywords)


def _has_quality_lap(a, laps_by_id):
    """True if any meaningful lap has pace ≤ QUALITY_LAP_PACE_THRESHOLD."""
    aid = str(a.get("activity_id") or "").strip()
    if not aid or aid not in laps_by_id:
        return False
    for lap in laps_by_id[aid]:
        dist = float(lap.get("distance_km") or 0)
        pace = _pace_to_decimal(lap.get("avg_pace_min_km", ""))
        if dist >= MIN_QUALITY_LAP_KM and pace is not None and pace <= QUALITY_LAP_PACE_THRESHOLD:
            return True
    return False


def _is_easy(a, quality_keywords):
    """Aerobic / easy run heuristic: not quality-titled, pace >= 6:00/km."""
    if _is_quality(a, quality_keywords):
        return False
    pace_dec = _pace_to_decimal(a["avg_pace"])
    if pace_dec is None or pace_dec < 6.0:
        return False
    return True


def compute_race_countdown(race_calendar, today):
    rows = []
    for race in race_calendar:
        try:
            race_date = datetime.strptime(race["date"], "%Y-%m-%d")
        except Exception:
            continue
        days = (race_date - today).days
        weeks = days / 7
        if days < 0:
            status = f"past ({-days} d ago)"
        elif days == 0:
            status = "today"
        elif days < 7:
            status = f"{days} d"
        else:
            status = f"{weeks:.1f} wk ({days} d)"
        rows.append({**race, "days": days, "weeks": weeks, "status": status})
    return rows


def compute_weekly_zone_pct(acts, n_weeks=8):
    weekly_zones = defaultdict(lambda: defaultdict(float))
    for a in acts:
        if not a["avg_hr"]:
            continue
        w = _week_start(a["date"])
        for name, lo, hi in HR_ZONES:
            if lo <= a["avg_hr"] < hi:
                weekly_zones[w][name] += a["distance_km"]  # km-weighted, not run count
                break
    if not weekly_zones:
        return []
    recent = sorted(weekly_zones.keys())[-n_weeks:]
    rows = []
    for w in recent:
        total = sum(weekly_zones[w].values())
        if total == 0:
            continue
        z12 = weekly_zones[w]["Z1 Easy"] + weekly_zones[w]["Z2 Aerobic"]
        z3 = weekly_zones[w]["Z3 Tempo"]
        z45 = weekly_zones[w]["Z4 Hard"] + weekly_zones[w]["Z5 Max"]
        rows.append({
            "week_start": w,
            "total_km": round(total, 1),
            "z12_pct": int(z12 / total * 100),
            "z3_pct": int(z3 / total * 100),
            "z45_pct": int(z45 / total * 100),
        })
    return rows


def compute_acwr(acts, end_date):
    """Acute (7d km) : Chronic (28d avg weekly km). 0.8–1.3 = sweet spot, >1.5 = high risk."""
    seven = 0.0
    twentyeight = 0.0
    for a in acts:
        delta = (end_date - a["date"]).days
        if 0 <= delta < 7:
            seven += a["distance_km"]
        if 0 <= delta < 28:
            twentyeight += a["distance_km"]
    chronic = twentyeight / 4.0
    if chronic <= 0:
        return None, seven, chronic
    return seven / chronic, seven, chronic


def compute_easy_hr_baseline(acts, quality_keywords):
    easy = [a for a in acts if _is_easy(a, quality_keywords) and a["avg_hr"]]
    pre = [a for a in easy if a["date"] < GEAR_CHANGE_DATE]
    post = [a for a in easy if a["date"] >= GEAR_CHANGE_DATE]

    def stats(runs):
        if not runs:
            return None
        hrs = [a["avg_hr"] for a in runs]
        paces = [_pace_to_decimal(a["avg_pace"]) for a in runs]
        paces = [p for p in paces if p is not None]
        return {
            "count": len(runs),
            "avg_hr": sum(hrs) / len(hrs),
            "median_hr": sorted(hrs)[len(hrs) // 2],
            "avg_pace": sum(paces) / len(paces) if paces else None,
        }

    return stats(pre), stats(post)


def compute_pace_by_zone(acts):
    zone_paces = defaultdict(list)
    for a in acts:
        if not a["avg_hr"]:
            continue
        pace_dec = _pace_to_decimal(a["avg_pace"])
        if pace_dec is None:
            continue
        for name, lo, hi in HR_ZONES:
            if lo <= a["avg_hr"] < hi:
                zone_paces[name].append(pace_dec)
                break
    rows = []
    for name, _, _ in HR_ZONES:
        paces = zone_paces[name]
        if not paces:
            rows.append((name, 0, "—", "—", "—"))
            continue
        rows.append((
            name,
            len(paces),
            _decimal_to_pace(sum(paces) / len(paces)),
            _decimal_to_pace(min(paces)),
            _decimal_to_pace(max(paces)),
        ))
    return rows


def identify_long_runs(acts, threshold_km=LONG_RUN_KM, n=10):
    lrs = [a for a in acts if a["distance_km"] >= threshold_km]
    lrs.sort(key=lambda x: x["date"], reverse=True)
    return lrs[:n]


def compute_recovery_spacing(acts, quality_keywords, n=10):
    qacts = [a for a in acts if _is_quality(a, quality_keywords)]
    qacts.sort(key=lambda x: x["date"])
    gaps = []
    for i in range(1, len(qacts)):
        gap_days = (qacts[i]["date"] - qacts[i - 1]["date"]).days
        if gap_days <= 1:
            flag = "⚠️ back-to-back"
        elif gap_days == 2:
            flag = "⚠️ tight (2 d)"
        elif gap_days >= 7:
            flag = "long gap"
        else:
            flag = ""
        gaps.append((qacts[i - 1], qacts[i], gap_days, flag))
    return gaps[-n:]


def compute_vo2max_trend(acts, n=10):
    """Last N activities with a Garmin VO2max estimate."""
    vo2_acts = [a for a in acts if a.get("vo2max")]
    vo2_acts.sort(key=lambda x: x["date"], reverse=True)
    return vo2_acts[:n]


def compute_cadence_trend(acts, n_weeks=8):
    """Weekly average cadence (spm) for the last N weeks."""
    weekly = defaultdict(list)
    for a in acts:
        cad = a.get("cadence")
        if cad and cad > 0:
            weekly[_week_start(a["date"])].append(cad)
    recent = sorted(weekly.keys())[-n_weeks:]
    rows = []
    for w in recent:
        cads = weekly[w]
        if not cads:
            continue
        avg = round(sum(cads) / len(cads))
        flag = "✅ optimal" if avg >= 170 else ("⚠️ low" if avg < 165 else "")
        rows.append({"week_start": w, "count": len(cads), "avg": avg, "flag": flag})
    return rows


def compute_stride_trend(acts, n_weeks=8):
    """Weekly average stride length (m) for the last N weeks.
    Garmin's avgStrideLength comes back in centimeters, so we convert ÷ 100."""
    weekly = defaultdict(list)
    for a in acts:
        sl = a.get("stride_length_m")
        if sl and sl > 0:
            weekly[_week_start(a["date"])].append(float(sl) / 100)  # cm → m
    recent = sorted(weekly.keys())[-n_weeks:]
    rows = []
    for w in recent:
        strides = weekly[w]
        if not strides:
            continue
        avg = round(sum(strides) / len(strides), 2)
        rows.append({"week_start": w, "count": len(strides), "avg_m": avg})
    return rows


# ─── VDOT CALCULATOR (Daniels' Running Formula) ─────────────

def compute_vdot(distance_m, time_min):
    """Jack Daniels' VDOT from a race result."""
    velocity = distance_m / time_min
    vo2 = -4.60 + 0.182258 * velocity + 0.000104 * velocity ** 2
    pct_max = (0.8 + 0.1894393 * math.exp(-0.012778 * time_min)
               + 0.2989558 * math.exp(-0.1932605 * time_min))
    return vo2 / pct_max


def predict_race_time(vdot, distance_m):
    """Predict race time (minutes) for a distance given a VDOT. Binary search."""
    lo, hi = 1.0, 600.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if compute_vdot(distance_m, mid) > vdot:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _velocity_at_vo2(target_vo2):
    """Invert the VO2-velocity formula: solve for velocity given target VO2."""
    a = 0.000104
    b = 0.182258
    c = -(4.60 + target_vo2)
    discriminant = b ** 2 - 4 * a * c
    if discriminant < 0:
        return None
    v = (-b + math.sqrt(discriminant)) / (2 * a)
    return v if v > 0 else None


def vdot_training_paces(vdot):
    """Derive training paces (min/km) from VDOT using calibrated Daniels percentages."""
    def pace_at_pct(pct):
        v = _velocity_at_vo2(vdot * pct)
        if not v:
            return None
        return 1000 / v  # min/km

    return {
        "easy_slow": pace_at_pct(0.55),
        "easy_fast": pace_at_pct(0.64),
        "marathon": pace_at_pct(0.75),
        "threshold": pace_at_pct(0.83),
        "interval": pace_at_pct(0.93),
        "repetition": pace_at_pct(1.03),
    }


def compute_vdot_section(personal_records):
    """Build VDOT predictions and training paces from PRs."""
    if not personal_records:
        return None
    best = max(personal_records, key=lambda r: compute_vdot(r["distance_m"], r["time_min"]))
    vdot = compute_vdot(best["distance_m"], best["time_min"])
    predictions = {}
    for label, dist_m in [("5K", 5000), ("10K", 10000), ("15K", 15000), ("HM", 21097), ("Marathon", 42195)]:
        t = predict_race_time(vdot, dist_m)
        h = int(t // 60)
        m = int(t % 60)
        s = int((t - int(t)) * 60)
        predictions[label] = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    paces = vdot_training_paces(vdot)
    return {
        "vdot": round(vdot, 1),
        "source": best,
        "predictions": predictions,
        "paces": paces,
    }


# ─── PLAN COMPLIANCE ─────────────────────────────────────────


def _matches_plan_session(activity, session):
    """Attribute only an unambiguous activity on the planned date."""
    if activity["date"].date() != session.date:
        return False
    title = activity.get("title", "").lower()
    return session.id.lower() in title or session.name.lower() in title


def compute_plan_compliance(acts, plan):
    """Compare completed activities against validated, dated PLAN-DATA sessions."""
    if not plan.is_active:
        return []
    completed = {}
    for session in plan.sessions:
        matches = [activity for activity in acts if _matches_plan_session(activity, session)]
        if len(matches) == 1:
            completed[session.id] = matches[0]

    weeks = []
    for week_num, (week_start, sessions) in enumerate(sorted(plan.sessions_by_week().items()), start=1):
        details = []
        completed_count = 0
        for session in sessions:
            planned_km = session.planned_distance_m / 1000 if session.planned_distance_m is not None else None
            done = completed.get(session.id)
            if done:
                completed_count += 1
                km_diff = done["distance_km"] - planned_km if planned_km is not None else None
                details.append({
                    "day": session.date.strftime("%a"),
                    "planned_type": session.name,
                    "planned_km": planned_km,
                    "actual_km": done["distance_km"],
                    "km_diff": km_diff,
                    "pace": done["avg_pace"],
                    "status": "✅",
                })
            else:
                details.append({
                    "day": session.date.strftime("%a"),
                    "planned_type": session.name,
                    "planned_km": planned_km,
                    "actual_km": None,
                    "km_diff": None,
                    "pace": None,
                    "status": "⬜",
                })
        weeks.append({
            "week": week_num,
            "start": week_start.isoformat(),
            "planned": len(sessions),
            "completed": completed_count,
            "pct": int(completed_count / len(sessions) * 100),
            "details": details,
        })
    return weeks


# ─── WEATHER ─────────────────────────────────────────────────

# Coordinates are rounded to this many decimals before grouping activities
# into a weather-fetch location. 2 decimals (~1km) is already finer than the
# archive API's native grid (~9-11km) — more precision wouldn't add signal,
# it would just fragment nearby runs into separate API calls.
WEATHER_COORD_DECIMALS = 2


def fetch_weather_for_location(lat, lon, dates):
    """Fetch daily temperature and humidity from Open-Meteo for a list of dates at one location.
    Returns dict {date_str: {"temp_c": float, "humidity_pct": int}}."""
    if not dates:
        return {}
    date_strs = sorted(set(d.strftime("%Y-%m-%d") if isinstance(d, datetime) else d for d in dates))
    start = date_strs[0]
    end = date_strs[-1]
    try:
        resp = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": lat,
                "longitude": lon,
                "start_date": start,
                "end_date": end,
                "daily": "temperature_2m_mean,relative_humidity_2m_mean",
                "timezone": WEATHER_TIMEZONE,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("daily", {})
        result = {}
        times = data.get("time", [])
        temps = data.get("temperature_2m_mean", [])
        humids = data.get("relative_humidity_2m_mean", [])
        for i, d in enumerate(times):
            if d in date_strs:
                result[d] = {
                    "temp_c": round(temps[i], 1) if temps[i] is not None else None,
                    "humidity_pct": int(humids[i]) if humids[i] is not None else None,
                }
        return result
    except Exception as e:
        print(f"Warning: weather fetch failed: {e}", flush=True)
        return {}


# ─── AUTO-UPDATE ATHLETE PROFILE ─────────────────────────────

def auto_update_athlete_profile(profile_path, vo2max, avg_4w_km):
    """Update auto-generated sections in athlete-profile.md using HTML markers."""
    if not profile_path or not os.path.exists(profile_path):
        return
    with open(profile_path, "r", encoding="utf-8") as f:
        content = f.read()

    changed = False

    # Update VO2max
    if vo2max is not None:
        pattern = r"(<!-- AUTO:VO2MAX -->).*?(<!-- /AUTO:VO2MAX -->)"
        replacement = f"<!-- AUTO:VO2MAX -->{vo2max:.0f} ml/kg/min (Garmin)<!-- /AUTO:VO2MAX -->"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        if new_content != content:
            content = new_content
            changed = True

    # Update 4-week average
    if avg_4w_km is not None:
        pattern = r"(<!-- AUTO:4WAVG -->).*?(<!-- /AUTO:4WAVG -->)"
        replacement = f"<!-- AUTO:4WAVG -->~{avg_4w_km:.0f} km/week<!-- /AUTO:4WAVG -->"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        if new_content != content:
            content = new_content
            changed = True

    # Shoe mileage — untracked (Strava API now requires a paid developer subscription)
    pattern = r"(<!-- AUTO:SHOES -->).*?(<!-- /AUTO:SHOES -->)"
    replacement = "<!-- AUTO:SHOES -->\n_Not tracked — Strava's API now requires a paid developer subscription._\n<!-- /AUTO:SHOES -->"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    if new_content != content:
        content = new_content
        changed = True

    if changed:
        with open(profile_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("athlete-profile.md auto-updated (VO2max, avg km, shoes)", flush=True)


def _lap_summary(activity_id, laps_by_id):
    """Return a short lap summary string for the full activity log, or '—'."""
    aid = str(activity_id or "").strip()
    if not aid or aid not in laps_by_id:
        return "—"
    laps = [l for l in laps_by_id[aid] if float(l.get("distance_km") or 0) >= 0.1]
    if not laps:
        return "—"
    paces = [_pace_to_decimal(l.get("avg_pace_min_km")) for l in laps]
    paces = [p for p in paces if p is not None]
    if not paces:
        return f"{len(laps)} laps"
    best = _decimal_to_pace(min(paces))
    avg = _decimal_to_pace(sum(paces) / len(paces))
    return f"{len(laps)} laps · best {best} · avg {avg}"


def fetch_activity_laps(client, activity_id):
    """Fetch lap splits for a single activity from Garmin. Returns list of lap dicts."""
    try:
        data = client.get_activity_splits(activity_id)
        if isinstance(data, dict):
            lap_list = data.get("lapDTOs", data.get("laps", []))
        elif isinstance(data, list):
            lap_list = data
        else:
            return []
        laps = []
        for i, lap in enumerate(lap_list):
            if not isinstance(lap, dict):
                continue
            dist_m = lap.get("distance") or lap.get("totalDistance") or 0
            dur_s = lap.get("duration") or lap.get("elapsedDuration") or 0
            distance_km = round(dist_m / 1000, 3)
            duration_min = round(dur_s / 60, 2)
            avg_pace = ""
            if distance_km > 0.05 and duration_min > 0:
                pd = duration_min / distance_km
                avg_pace = f"{int(pd)}:{int((pd - int(pd)) * 60):02d}"
            laps.append({
                "activity_id": str(activity_id),
                "lap_index": i,
                "distance_km": distance_km,
                "duration_min": duration_min,
                "avg_pace_min_km": avg_pace,
                "avg_hr": _int_or_none(lap.get("averageHR")),
                "max_hr": _int_or_none(lap.get("maxHR")),
                "calories": _int_or_none(lap.get("calories")),
            })
        return laps
    except Exception as e:
        print(f"  Warning: no laps for activity {activity_id}: {e}", flush=True)
        return []


_FEELING_MAP = {0: "Very Weak", 25: "Weak", 50: "Normal", 75: "Strong", 100: "Very Strong"}


def _feeling_label(raw_value):
    """Convert session.unknown_192 FIT value (0/25/50/75/100) to feeling label.
    Matches Garmin Connect's own labels: Very Weak / Weak / Normal / Strong / Very Strong."""
    if raw_value is None:
        return ""
    return _FEELING_MAP.get(int(raw_value), str(raw_value))


def fetch_fit_metrics(client, activity_id):
    """Download FIT file and return dict of all FIT-extractable metrics.
    Extracts: feeling, perceived_effort (self-eval).
    Note: aerobic/anaerobic TE and training load are NOT in FR55 FIT files (server-side only)."""
    try:
        import fitparse
        fit_zip = client.download_activity(activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL)
        with zipfile.ZipFile(io.BytesIO(fit_zip)) as z:
            fit_name = next((n for n in z.namelist() if n.endswith(".fit")), None)
            if not fit_name:
                return {}
            fit_data = z.read(fit_name)
        fitfile = fitparse.FitFile(io.BytesIO(fit_data))
        feeling_raw = effort_raw = None
        for msg in fitfile.get_messages("session"):
            for d in msg:
                if d.name == "unknown_192":
                    feeling_raw = d.raw_value
                elif d.name == "unknown_193":
                    effort_raw = d.raw_value
        result = {}
        if feeling_raw is not None:
            result["feeling"] = _feeling_label(feeling_raw)
        if effort_raw is not None:
            result["perceived_effort"] = int(round(effort_raw / 10))
        return result
    except Exception as e:
        print(f"  Warning: no FIT metrics for {activity_id}: {e}", flush=True)
        return {}


def compute_quality_session_breakdowns(quality_acts, laps_by_id, n=6):
    """
    For the N most recent quality sessions with lap data, return formatted markdown blocks.
    Each block is a mini table showing every lap's distance, pace, and HR.
    """
    blocks = []
    for a in quality_acts:
        if len(blocks) >= n:
            break
        aid = str(a.get("activity_id") or "").strip()
        if not aid or aid not in laps_by_id:
            continue
        laps = laps_by_id[aid]
        if not laps:
            continue

        title_short = a["title"][:60]
        header = f"### {a['date'].strftime('%b %d, %Y')} — {title_short}"

        table = ["| Lap | km | Pace | Avg HR | Max HR |",
                 "|-----|----|------|--------|--------|"]
        for lap in laps:
            km = f"{float(lap['distance_km']):.2f}" if lap.get("distance_km") else "—"
            pace = lap.get("avg_pace_min_km") or "—"
            hr = lap.get("avg_hr") or "—"
            mhr = lap.get("max_hr") or "—"
            table.append(f"| {int(lap['lap_index']) + 1} | {km} | {pace} | {hr} | {mhr} |")

        blocks.append(f"{header}\n\n" + "\n".join(table))
    return blocks


def _build_strava_gear_section():
    """Build the Shoe Mileage markdown section (untracked — Strava API requires a paid subscription now)."""
    return (
        "## Shoe Mileage\n\n"
        "_Not tracked — Strava's API now requires a paid developer subscription._"
    )



def _section_has_data(acts, fields, threshold=0.2):
    """True if ≥ threshold fraction of activities have at least one of `fields` populated."""
    if not acts:
        return False
    count = sum(1 for a in acts if any(a.get(f) for f in fields))
    return count / len(acts) >= threshold


def fetch_garmin_race_predictions(client):
    """Fetch Garmin race predictions. Returns dict {distance: time_str} or empty dict."""
    try:
        data = client.get_race_predictions()
        if not data:
            return {}

        def _fmt(seconds):
            if not seconds:
                return None
            s = int(seconds)
            h, rem = divmod(s, 3600)
            m, sec = divmod(rem, 60)
            return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

        predictions = {
            "5K":       _fmt(data.get("fiveKSeconds")),
            "10K":      _fmt(data.get("tenKSeconds")),
            "Half":     _fmt(data.get("halfMarathonSeconds")),
            "Marathon": _fmt(data.get("marathonSeconds")),
        }
        return {k: v for k, v in predictions.items() if v}
    except Exception as e:
        print(f"Note: race predictions not available: {e}", flush=True)
        return {}


def generate_training_history(rows, laps_rows=None, race_predictions=None):
    """Regenerates training-history.md with fresh data from the CSV."""
    acts = _parse_activities(rows)
    if not acts:
        print("No activities to generate training-history.md", flush=True)
        return

    total_runs = len(acts)
    date_min = min(a["date"] for a in acts)
    date_max = max(a["date"] for a in acts)
    total_km = sum(a["distance_km"] for a in acts)

    # ── Build laps index first (needed for quality detection and volume split) ──
    laps_by_id = defaultdict(list)
    for lr in (laps_rows or []):
        laps_by_id[str(lr.get("activity_id", ""))].append(lr)
    for aid in laps_by_id:
        laps_by_id[aid].sort(key=lambda x: int(x.get("lap_index", 0)))

    # ── Monthly volume ──────────────────────────────────────
    monthly = defaultdict(lambda: {"km": 0.0, "runs": 0, "hr_sum": 0, "hr_count": 0})
    month_order = []
    for a in sorted(acts, key=lambda x: x["date"]):
        key = a["date"].strftime("%b %Y")
        if key not in monthly:
            month_order.append(key)
        monthly[key]["km"] += a["distance_km"]
        monthly[key]["runs"] += 1
        if a["avg_hr"]:
            monthly[key]["hr_sum"] += a["avg_hr"]
            monthly[key]["hr_count"] += 1

    monthly_rows = []
    for key in month_order:
        m = monthly[key]
        avg_hr = int(m["hr_sum"] / m["hr_count"]) if m["hr_count"] else "—"
        monthly_rows.append(f"| {key} | {m['km']:.1f} | {m['runs']} | {avg_hr} |")

    # ── Weekly volume (last 10 weeks) with easy/quality split ───
    weekly = defaultdict(lambda: {"total": 0.0, "easy": 0.0, "quality": 0.0})
    for a in acts:
        w_key = _week_start(a["date"])
        is_qual = _is_quality(a, QUALITY_KEYWORDS) or _has_quality_lap(a, laps_by_id)
        weekly[w_key]["total"] += a["distance_km"]
        if is_qual:
            weekly[w_key]["quality"] += a["distance_km"]
        else:
            weekly[w_key]["easy"] += a["distance_km"]

    last_10_weeks = sorted(weekly.keys())[-10:]
    weekly_rows = []
    peak_week = max(last_10_weeks, key=lambda w: weekly[w]["total"])
    for w in last_10_weeks:
        end = w + timedelta(days=6)
        label = f"{w.strftime('%b %d')}–{end.strftime('%b %d')}"
        note = " ← peak" if w == peak_week else ""
        total = weekly[w]["total"]
        easy = weekly[w]["easy"]
        qual = weekly[w]["quality"]
        easy_pct = int(easy / total * 100) if total > 0 else 0
        vol_flag = " ✅" if easy_pct >= 75 else (" ⚠️" if easy_pct < 65 else "")
        weekly_rows.append(
            f"| {label} | {total:.1f}{note} | {easy:.1f} | {qual:.1f} | {easy_pct}%{vol_flag} |"
        )

    last_4 = sorted(weekly.keys())[-4:]
    avg_4w = sum(weekly[w]["total"] for w in last_4) / len(last_4) if last_4 else 0

    # ── HR zone distribution ────────────────────────────────
    zone_counts = defaultdict(int)
    hr_acts = [a for a in acts if a["avg_hr"]]
    for a in hr_acts:
        for name, lo, hi in HR_ZONES:
            if lo <= a["avg_hr"] < hi:
                zone_counts[name] += 1
                break

    zone_rows = []
    for name, lo, hi in HR_ZONES:
        count = zone_counts[name]
        pct = int(count / len(hr_acts) * 100) if hr_acts else 0
        hi_str = "+" if hi == 999 else str(hi)
        zone_rows.append(f"| {name} | {lo}–{hi_str} | {count} | {pct}% |")

    # ── Notable quality sessions (keyword in title OR fast lap) ─
    quality_acts = [
        a for a in acts
        if _is_quality(a, QUALITY_KEYWORDS) or _has_quality_lap(a, laps_by_id)
    ]
    quality_acts.sort(key=lambda x: x["date"], reverse=True)
    quality_rows = []
    for a in quality_acts[:15]:
        quality_rows.append(
            f"| {a['date'].strftime('%b %d, %Y')} | {a['title']} "
            f"| {a['distance_km']:.2f} km | {a['avg_pace']}/km | {a['avg_hr'] or '—'} |"
        )

    # ── Section visibility flags ────────────────────────────
    show_self_eval = _section_has_data(acts, ["feeling", "perceived_effort"], threshold=0.05)

    # ── New metrics ─────────────────────────────────────────
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Race countdown
    race_rows = compute_race_countdown(RACE_CALENDAR, today)
    race_md = []
    for r in race_rows:
        race_md.append(
            f"| {r['name']} | {r['date']} | {r['distance_km']:.1f} km | {r['goal']} | **{r['status']}** |"
        )

    # Garmin race predictions
    race_pred_md = ""
    if race_predictions:
        pred_rows = [f"| {dist} | {t} |" for dist, t in race_predictions.items() if t]
        if pred_rows:
            race_pred_md = (
                "\n### Garmin Race Predictions\n\n"
                "> ⚠️ Garmin's predictions tend to be optimistic — treat them as a ceiling, not a target.\n\n"
                "| Distance | Predicted time |\n"
                "|----------|----------------|\n"
                + "\n".join(pred_rows)
            )

    # Weekly zone %
    wzp = compute_weekly_zone_pct(acts, n_weeks=8)
    wzp_md = []
    for row in wzp:
        end = row["week_start"] + timedelta(days=6)
        label = f"{row['week_start'].strftime('%b %d')}–{end.strftime('%b %d')}"
        flag = ""
        if row["z12_pct"] < 60:
            flag = " ⚠️ too much intensity"
        elif row["z12_pct"] >= 80:
            flag = " ✅ 80/20 on track"
        wzp_md.append(
            f"| {label} | {row['total_km']:.1f} | {row['z12_pct']}% | {row['z3_pct']}% | {row['z45_pct']}% |{flag}"
        )

    # ACWR
    acwr, acute, chronic = compute_acwr(acts, today)
    if acwr is None:
        acwr_block = "_Insufficient data for ACWR (need at least 28 days of running)._"
    else:
        if acwr > 1.5:
            acwr_flag = "⚠️ **HIGH** — injury risk, consider a cutback week"
        elif acwr > 1.3:
            acwr_flag = "⚠️ elevated — monitor closely"
        elif acwr < 0.8:
            acwr_flag = "↓ undertrained vs recent chronic load"
        else:
            acwr_flag = "✅ sweet spot (0.8–1.3)"
        acwr_block = (
            f"- **Last 7 days**: {acute:.1f} km\n"
            f"- **28-day avg weekly**: {chronic:.1f} km\n"
            f"- **ACWR (7d ÷ chronic)**: **{acwr:.2f}** — {acwr_flag}"
        )

    # Easy HR baseline pre/post gear
    pre_stats, post_stats = compute_easy_hr_baseline(acts, QUALITY_KEYWORDS)

    def _fmt_stats(s):
        if not s:
            return "_no data_"
        pace = _decimal_to_pace(s["avg_pace"]) if s["avg_pace"] else "—"
        return (
            f"{s['count']} runs · avg HR **{s['avg_hr']:.0f}** "
            f"(median {s['median_hr']}) · avg pace {pace}/km"
        )

    # Recent long runs
    lrs = identify_long_runs(acts, threshold_km=LONG_RUN_KM, n=10)
    lr_md = []
    for a in lrs:
        lr_md.append(
            f"| {a['date'].strftime('%b %d, %Y')} | {a['title'][:55]} "
            f"| {a['distance_km']:.2f} km | {a['avg_pace'] or '—'}/km "
            f"| {a['avg_hr'] or '—'} |"
        )
    if not lr_md:
        lr_md.append(f"| _no runs ≥ {LONG_RUN_KM:.0f} km in record_ | | | | |")

    # Recovery spacing
    gaps = compute_recovery_spacing(acts, QUALITY_KEYWORDS, n=10)
    gap_md = []
    for prev, curr, days, flag in gaps:
        gap_md.append(
            f"| {prev['date'].strftime('%b %d')} ({prev['title'][:30]}) "
            f"→ {curr['date'].strftime('%b %d')} ({curr['title'][:30]}) "
            f"| {days} d | {flag} |"
        )
    if not gap_md:
        gap_md.append("| _not enough quality sessions yet_ | | |")

    # Pace by zone
    pz = compute_pace_by_zone(acts)
    pz_md = []
    for name, count, avg_p, min_p, max_p in pz:
        pz_md.append(f"| {name} | {count} | {avg_p}/km | {min_p}/km | {max_p}/km |")

    # ── VO2max Trend ─────────────────────────────────────
    vo2_acts = compute_vo2max_trend(acts, n=10)
    vo2_md = []
    for a in vo2_acts:
        vo2_md.append(
            f"| {a['date'].strftime('%b %d, %Y')} | {a['title'][:40]} "
            f"| **{a['vo2max']:.1f}** | {a['avg_hr'] or '—'} | {a['avg_pace'] or '—'} |"
        )
    if not vo2_md:
        vo2_md.append("| _no VO2max data yet_ | | | | |")

    # ── Cadence & stride trends ───────────────────────────
    cadence_data = compute_cadence_trend(acts, n_weeks=8)
    cadence_md = []
    for row in cadence_data:
        end = row["week_start"] + timedelta(days=6)
        label = f"{row['week_start'].strftime('%b %d')}–{end.strftime('%b %d')}"
        cadence_md.append(f"| {label} | {row['count']} | {row['avg']} | {row['flag']} |")

    stride_data = compute_stride_trend(acts, n_weeks=8)
    stride_md = []
    for row in stride_data:
        end = row["week_start"] + timedelta(days=6)
        label = f"{row['week_start'].strftime('%b %d')}–{end.strftime('%b %d')}"
        stride_md.append(f"| {label} | {row['count']} | {row['avg_m']:.2f} |")

    # ── Self-evaluation log ───────────────────────────────
    se_acts = [a for a in sorted(acts, key=lambda x: x["date"], reverse=True)
               if a.get("feeling") or a.get("perceived_effort") is not None]
    se_md = []
    for a in se_acts[:15]:
        feeling_str = a.get("feeling") or "—"
        effort_val = a.get("perceived_effort")
        effort_str = f"{effort_val}/10" if effort_val is not None else "—"
        se_md.append(
            f"| {a['date'].strftime('%Y-%m-%d')} | {a['title'][:50]} "
            f"| {a['distance_km']:.1f} | {feeling_str} | {effort_str} |"
        )

    # ── New: Quality session lap breakdowns ───────────────
    breakdown_blocks = compute_quality_session_breakdowns(quality_acts, laps_by_id, n=6)
    if breakdown_blocks:
        breakdown_section = "\n\n---\n\n".join(breakdown_blocks)
    else:
        breakdown_section = "_No lap data yet — will populate after next sync._"

    # ── VDOT Predictions ─────────────────────────────────
    vdot_data = compute_vdot_section(PERSONAL_RECORDS)
    vdot_section_md = ""
    if vdot_data:
        vdot_val = vdot_data["vdot"]
        src = vdot_data["source"]
        preds = vdot_data["predictions"]
        paces = vdot_data["paces"]
        pred_rows = "\n".join(f"| {dist} | {t} |" for dist, t in preds.items())
        pace_rows = (
            f"| Easy | {_decimal_to_pace(paces['easy_slow'])} – {_decimal_to_pace(paces['easy_fast'])}/km |\n"
            f"| Marathon | {_decimal_to_pace(paces['marathon'])}/km |\n"
            f"| Threshold | {_decimal_to_pace(paces['threshold'])}/km |\n"
            f"| Interval | {_decimal_to_pace(paces['interval'])}/km |\n"
            f"| Repetition | {_decimal_to_pace(paces['repetition'])}/km |"
        )
        vdot_section_md = (
            f"## VDOT Race Predictions & Training Paces\n\n"
            f"**VDOT: {vdot_val}** (from {src['label']}: {int(src['time_min'])}:{int((src['time_min'] % 1) * 60):02d}, {src['date']})\n\n"
            f"### Race Predictions (Daniels)\n\n"
            f"| Distance | Predicted time |\n"
            f"|----------|----------------|\n"
            f"{pred_rows}\n\n"
            f"> Based on Jack Daniels' formula. More conservative and realistic than Garmin's predictions.\n\n"
            f"### Training Paces (VDOT-derived)\n\n"
            f"| Zone | Pace |\n"
            f"|------|------|\n"
            f"{pace_rows}\n\n"
            f"> These paces are derived from the current VDOT. Compare with the real paces in athlete-profile to spot mismatches."
        )

    # ── Plan Compliance ──────────────────────────────────
    compliance_weeks = compute_plan_compliance(acts, ACTIVE_PLAN)
    compliance_md = ""
    if compliance_weeks:
        today_date = today.date()
        current_week = None
        for wk in compliance_weeks:
            wk_start = datetime.strptime(wk["start"], "%Y-%m-%d").date()
            wk_end = wk_start + timedelta(days=6)
            if wk_start <= today_date <= wk_end:
                current_week = wk["week"]
                break

        summary_rows = []
        for wk in compliance_weeks:
            if wk["completed"] == 0 and wk["week"] > (current_week or 0):
                continue
            marker = " ← current" if wk["week"] == current_week else ""
            summary_rows.append(
                f"| W{wk['week']} ({wk['start']}) | {wk['completed']}/{wk['planned']} | {wk['pct']}% |{marker}"
            )

        detail_rows = []
        show_weeks = [w for w in compliance_weeks if w["completed"] > 0 or w["week"] == current_week]
        for wk in show_weeks[-4:]:
            for d in wk["details"]:
                if d["actual_km"] is not None:
                    km_diff = f"{d['km_diff']:+.1f}" if d["km_diff"] else "0"
                    planned = f"{d['planned_km']:.1f}" if d["planned_km"] is not None else "—"
                    detail_rows.append(
                        f"| W{wk['week']} {d['day']} | {d['planned_type']} | {planned} | "
                        f"{d['actual_km']:.1f} | {km_diff} | {d['pace'] or '—'} | {d['status']} |"
                    )
                else:
                    planned = f"{d['planned_km']:.1f}" if d["planned_km"] is not None else "—"
                    detail_rows.append(
                        f"| W{wk['week']} {d['day']} | {d['planned_type']} | {planned} | "
                        f"— | — | — | {d['status']} |"
                    )

        compliance_md = (
            f"## Plan Compliance ({len(ACTIVE_PLAN.sessions_by_week())}-week plan)\n\n"
            f"### Weekly Summary\n\n"
            f"| Week | Sessions | Completion |\n"
            f"|------|----------|------------|\n"
            + "\n".join(summary_rows) + "\n\n"
            f"### Session Detail (last 4 active weeks)\n\n"
            f"| Session | Type | Plan km | Actual km | Diff | Pace | Status |\n"
            f"|---------|------|---------|-----------|------|------|--------|\n"
            + "\n".join(detail_rows) + "\n\n"
            f"> ✅ = completed, ⬜ = pending/missed. Diff = actual − planned km."
        )

    # ── Full activity log (all runs, most recent first) ─────
    all_log_rows = []
    for a in sorted(acts, key=lambda x: x["date"], reverse=True):
        vo2_str = f"{a['vo2max']:.1f}" if a.get("vo2max") is not None else "—"
        lap_sum = _lap_summary(a.get("activity_id"), laps_by_id)
        feeling_str = a.get("feeling") or "—"
        effort_val = a.get("perceived_effort")
        effort_str = f"{effort_val}/10" if effort_val is not None else "—"
        temp_str = f"{a['weather_temp_c']:.0f}°" if a.get("weather_temp_c") is not None else "—"
        hum_str = f"{a['weather_humidity_pct']}%" if a.get("weather_humidity_pct") is not None else "—"
        all_log_rows.append(
            f"| {a['date'].strftime('%Y-%m-%d')} | {a['title']} "
            f"| {a['distance_km']:.2f} | {a['duration_min']:.0f} | {a['avg_pace'] or '—'} "
            f"| {a['avg_hr'] or '—'} | {a['max_hr'] or '—'} "
            f"| {a['cadence'] or '—'} | {a['calories'] or '—'} "
            f"| {vo2_str} | {feeling_str} | {effort_str} | {temp_str} | {hum_str} | {lap_sum} |"
        )

    # ── Build markdown ──────────────────────────────────────
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"""\
# Training History & Load Context

> Load this file when analyzing trends, planning training phases, or assessing race readiness.
> This summarizes the athlete's Garmin activity history ({date_min.strftime('%b %Y')} – {date_max.strftime('%b %d, %Y')}, {total_runs} runs).
> **Auto-generated by sync.py on {now_str}** — do not edit manually.

---

## Race Countdown (as of {today.strftime('%Y-%m-%d')})

| Race | Date | Distance | Goal | Time to race |
|------|------|----------|------|--------------|
{chr(10).join(race_md) if race_md else '| _no races configured_ | | | | |'}
{race_pred_md}

---

## Monthly Volume Summary

| Month | km | Runs | Avg HR |
|-------|----|------|--------|
{chr(10).join(monthly_rows)}

**Total recorded**: ~{total_km:.0f} km over ~{len(month_order)} months

---

## Recent Weekly Volume (last 10 weeks)

| Week | Total km | Easy km | Quality km | Easy % |
|------|----------|---------|------------|--------|
{chr(10).join(weekly_rows)}

**Avg weekly km (last 4 weeks)**: ~{avg_4w:.1f} km

---

## Weekly HR-Zone Split (last 8 weeks, km-weighted)

| Week | km | Z1–Z2 % | Z3 % | Z4–Z5 % | Flag |
|------|----|---------|------|---------|------|
{chr(10).join(wzp_md) if wzp_md else '| _no HR data_ | | | | | |'}

> Target for an advanced runner building base: ≥ 80% in Z1–Z2. Isolated hard weeks (race weeks, peak) can dip lower — consistent sub-60% is the injury/stagnation red zone.

---

## Acute:Chronic Workload Ratio (ACWR)

{acwr_block}

> ACWR = last 7 days of km ÷ 28-day rolling weekly average. Rising through 1.0→1.3 is a healthy build; sustained > 1.5 is the injury danger zone; < 0.8 flags a cutback/taper or missed training.

---

## Heart Rate Zone Distribution (all runs, by avg HR)

| Zone | BPM | Activities | % |
|------|-----|------------|---|
{chr(10).join(zone_rows)}

> ⚠️ **Coaching note**: The ideal distribution for an 80/20 aerobic base is ~80% in Z1–Z2. Z3 dominance suggests easy days may be run too hard.

---

## Pace Distribution by HR Zone (sanity check for easy-day discipline)

| Zone | Runs | Avg pace | Fastest | Slowest |
|------|------|----------|---------|---------|
{chr(10).join(pz_md)}

> If Z1–Z2 avg pace is faster than the athlete's listed easy-pace band, the discipline problem is pace-driven, not just HR-driven.

---

## VO2max Trend (Garmin estimate, last 10 activities)

| Date | Session | VO2max (ml/kg/min) | Avg HR | Pace |
|------|---------|-------------------|--------|------|
{chr(10).join(vo2_md)}

> Garmin's VO2max estimate updates after hard efforts and long runs. Upward trend = aerobic fitness improving. Use to confirm adaptation, not as a precise lab value.

---

## Easy-Day HR Baseline (pre vs post gear change {GEAR_CHANGE_DATE.strftime('%Y-%m-%d')})

- **Before gear change**: {_fmt_stats(pre_stats)}
- **After gear change**: {_fmt_stats(post_stats)}

> Use this split when interpreting HR improvements since mid-Mar 2026. A drop of ~5–10 bpm at similar pace is expected from shoes/insoles alone — only attribute the residual gain to fitness.

---

## Running Economy Trends (last 8 weeks)

### Cadence (spm)

| Week | Runs | Avg spm | Flag |
|------|------|---------|------|
{chr(10).join(cadence_md) if cadence_md else '| _no cadence data_ | | | |'}

> Target: 170–180 spm. Low cadence often means overstriding. Track alongside pace to gauge running economy improvements.

### Stride Length (m)

| Week | Runs | Avg stride (m) |
|------|------|----------------|
{chr(10).join(stride_md) if stride_md else '| _no stride data_ | | |'}

> Step length (half-stride, Garmin's unit). Typical range: 0.90–1.05 m easy, 1.00–1.20 m tempo. Rising trend at same pace/cadence = improving running economy.

---

## Notable Quality Sessions (most recent 15)

| Date | Session | Distance | Avg Pace | Avg HR |
|------|---------|----------|----------|--------|
{chr(10).join(quality_rows)}

---

## Quality Session Breakdowns (last 6 with lap data)

{breakdown_section}

---

## Recent Long Runs (≥ {LONG_RUN_KM:.0f} km, last 10)

| Date | Title | Distance | Pace | Avg HR |
|------|-------|----------|------|--------|
{chr(10).join(lr_md)}

---

## Recovery Spacing Between Quality Sessions (last 10 gaps)

| From → To | Days | Flag |
|-----------|------|------|
{chr(10).join(gap_md)}

> Advanced runners typically need ≥ 48 h between hard sessions. Back-to-back or 2-day gaps are only appropriate in specific race-prep micro-blocks; otherwise they compound fatigue.

---
{"" if not show_self_eval else f"""
## Post-Workout Self-Evaluation (last 15 with data)

| Date | Session | km | Feeling | Effort |
|------|---------|----|---------|----|
{chr(10).join(se_md) if se_md else "| _no self-eval data yet_ | | | | |"}

> Feeling scale: Very Weak → Weak → Normal → Strong → Very Strong. Effort: 1–10 (RPE).
> Useful for spotting overreaching (low feeling + high effort) or underperformance.

---
"""}
{"---" + chr(10) + chr(10) + vdot_section_md + chr(10) + chr(10) if vdot_section_md else ""}
{"---" + chr(10) + chr(10) + compliance_md + chr(10) + chr(10) if compliance_md else ""}
---

{_build_strava_gear_section()}

---

{GEAR_CHANGES_SECTION}

---

## Full Activity Log ({total_runs} runs, most recent first)

> Full per-lap splits are in `{LAPS_CSV_PATH}` — consult that file for detailed lap-by-lap analysis of any activity.

| Date | Title | km | min | Pace | Avg HR | Max HR | Cad | Cal | VO2 | Feel | Eff | Temp | Hum | Laps |
|------|-------|----|-----|------|--------|--------|-----|-----|-----|------|-----|------|-----|------|
{chr(10).join(all_log_rows)}
"""

    with open(TRAINING_HISTORY_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"training-history.md updated ({total_runs} activities, through {date_max.date()})", flush=True)


def main():
    global ACTIVE_PLAN, PLAN_ERROR
    # Avoids a blank console (e.g. when opening the .py via Windows file association)
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(line_buffering=True)
            sys.stderr.reconfigure(line_buffering=True)
        except Exception:
            pass

    requirements = readiness(PATHS)
    if not is_ready(requirements, "sync"):
        print("Sync setup is incomplete. Run: python setup_status.py --json", flush=True)
        for item in requirements:
            if "sync" in item.required_for and item.state != "ready":
                print(f"- {item.name}: {item.remediation}", flush=True)
        return 2
    try:
        ACTIVE_PLAN = parse_training_plan(PATHS.training_plan)
    except PlanValidationError as exc:
        PLAN_ERROR = str(exc)
        ACTIVE_PLAN = no_active_plan()
        print(f"Warning: plan compliance skipped: {PLAN_ERROR}", flush=True)

    # Connect to Garmin
    print("Connecting to Garmin...", flush=True)

    try:
        # Try using saved tokens first
        client = Garmin()
        client.login(tokenstore=GARMIN_TOKEN_DIR)
        print("Login with saved tokens succeeded", flush=True)
    except Exception as e:
        # An empty except used to hide 429s / broken tokens; the reason needs to be visible
        print(f"Could not use saved tokens: {e}", flush=True)
        print("Logging in with username and password...", flush=True)
        client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD)
        client.login()
        # Save tokens for next time
        os.makedirs(GARMIN_TOKEN_DIR, exist_ok=True)
        client.client.dump(GARMIN_TOKEN_DIR)
        print("Tokens saved for future runs", flush=True)

    # Read dates already in the CSV to avoid duplicates
    # On FULL_BACKFILL we rebuild from scratch so all rows get the latest fields (e.g. activity_id)
    existing_dates = set()
    existing_rows = []
    if not FULL_BACKFILL and os.path.exists(CSV_PATH):
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_rows.append(row)
                existing_dates.add(row["date"] + row["title"])  # date + title as unique key

    # Date range: full history (empty CSV or FULL_BACKFILL) or just the new stretch
    end_date = datetime.today()
    history_start = datetime.strptime(HISTORY_START_DATE, "%Y-%m-%d")

    if FULL_BACKFILL:
        start_date = history_start
        print(
            f"Full backfill mode: from {start_date.date()} to {end_date.date()}...",
            flush=True,
        )
    elif not existing_rows:
        start_date = history_start
        print(
            f"Empty CSV: downloading full history from {start_date.date()}...",
            flush=True,
        )
    else:
        max_d = max(
            datetime.strptime(row["date"][:10], "%Y-%m-%d") for row in existing_rows
        )
        start_date = max(
            history_start,
            max_d - timedelta(days=INCREMENTAL_OVERLAP_DAYS),
        )
        print(
            f"Incremental mode: activities from {start_date.date()} "
            f"(latest in CSV: {max_d.date()})...",
            flush=True,
        )

    activities = client.get_activities_by_date(
        start_date.strftime("%Y-%m-%d"),
        end_date.strftime("%Y-%m-%d"),
        "running",
    )

    # Filter only the new ones
    new_rows = []
    for act in activities:
        date = act.get("startTimeLocal", "")[:10]
        title = act.get("activityName", "")
        if date + title in existing_dates:
            continue  # ya existe, saltar

        distance_km = round((act.get("distance") or 0) / 1000, 2)
        duration_min = round((act.get("duration") or 0) / 60, 2)
        avg_pace = ""
        if distance_km > 0 and duration_min > 0:
            pace_decimal = duration_min / distance_km
            mins = int(pace_decimal)
            secs = int((pace_decimal - mins) * 60)
            avg_pace = f"{mins}:{secs:02d}"

        start_lat = act.get("startLatitude")
        start_lon = act.get("startLongitude")

        new_rows.append({
            "activity_id": act.get("activityId", ""),
            "date": date,
            "title": title,
            "distance_km": distance_km,
            "duration_min": duration_min,
            "avg_pace_min_km": avg_pace,
            "avg_heart_rate": act.get("averageHR", ""),
            "max_heart_rate": act.get("maxHR", ""),
            "elevation_gain_m": act.get("elevationGain", ""),
            "cadence": act.get("averageRunningCadenceInStepsPerMinute", ""),
            "calories": act.get("calories", ""),
            "stride_length_m": act.get("avgStrideLength", ""),
            "vo2max": act.get("vO2MaxValue", ""),
            "feeling": "",
            "perceived_effort": "",
            "weather_temp_c": "",
            "weather_humidity_pct": "",
            "weather_lat": round(start_lat, WEATHER_COORD_DECIMALS) if start_lat is not None else "",
            "weather_lon": round(start_lon, WEATHER_COORD_DECIMALS) if start_lon is not None else "",
        })

    if not new_rows:
        print("No new activities", flush=True)
    else:
        print(f"{len(new_rows)} new activities found", flush=True)

    # Combine existing + new and sort by date
    all_rows = existing_rows + new_rows
    all_rows.sort(key=lambda x: x["date"])

    # ── Fetch FIT metrics (self-eval: feeling + perceived_effort) ───────
    if FETCH_SELF_EVAL:
        source = [
            r for r in (all_rows if BACKFILL_SELF_EVAL else new_rows)
            if r.get("activity_id") and r.get("feeling", "") == ""
        ]
        if source:
            print(f"Fetching FIT metrics for {len(source)} activities...", flush=True)
            for i, act_row in enumerate(source):
                metrics = fetch_fit_metrics(client, act_row["activity_id"])
                for key, val in metrics.items():
                    act_row[key] = val
                if i < len(source) - 1:
                    time.sleep(0.5)

    # ── Fetch weather for activities missing it ─────────
    # Grouped by each activity's own start coordinates (falling back to
    # WEATHER_LAT/WEATHER_LON for older rows or GPS-less activities), so an
    # athlete who runs in different parts of a city gets weather for where
    # they actually ran, not one fixed point.
    weather_missing = [r for r in all_rows if r.get("weather_temp_c", "") in ("", None)]
    if weather_missing:
        location_groups = defaultdict(list)
        for row in weather_missing:
            lat = _float_or_none(row.get("weather_lat", ""), ndigits=WEATHER_COORD_DECIMALS)
            lon = _float_or_none(row.get("weather_lon", ""), ndigits=WEATHER_COORD_DECIMALS)
            if lat is None or lon is None:
                lat, lon = WEATHER_LAT, WEATHER_LON
            location_groups[(lat, lon)].append(row)

        print(
            f"Fetching weather for {len(weather_missing)} activities "
            f"across {len(location_groups)} location(s)...",
            flush=True,
        )
        for (lat, lon), rows_at_location in location_groups.items():
            dates_to_fetch = [r["date"][:10] for r in rows_at_location]
            weather_data = fetch_weather_for_location(lat, lon, dates_to_fetch)
            for row in rows_at_location:
                d = row["date"][:10]
                if d in weather_data:
                    row["weather_temp_c"] = weather_data[d].get("temp_c", "")
                    row["weather_humidity_pct"] = weather_data[d].get("humidity_pct", "")

    # Rewrite the full sorted CSV
    fieldnames = [
        "activity_id", "date", "title",
        "distance_km", "duration_min", "avg_pace_min_km",
        "avg_heart_rate", "max_heart_rate", "elevation_gain_m", "cadence", "calories",
        "stride_length_m", "vo2max",
        "feeling", "perceived_effort",
        "weather_temp_c", "weather_humidity_pct", "weather_lat", "weather_lon",
    ]

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(
        f"CSV updated at {CSV_PATH} ({len(all_rows)} total activities)",
        flush=True,
    )

    filled = sum(1 for row in all_rows for f in fieldnames if row.get(f, "") not in ("", None))
    total_possible = len(all_rows) * len(fieldnames)
    print(
        f"Data: {filled:,} filled fields out of {total_possible:,} possible "
        f"({filled / total_possible * 100:.1f}% coverage, {len(fieldnames)} fields x {len(all_rows)} activities)",
        flush=True,
    )
    n = len(all_rows)
    for f in fieldnames:
        count = sum(1 for row in all_rows if row.get(f, "") not in ("", None))
        bar = "#" * (count * 20 // n) + "-" * (20 - count * 20 // n)
        print(f"  {f:<35} {bar} {count:>3}/{n} ({count/n*100:>5.1f}%)", flush=True)

    # ── Fetch lap data for new activities ─────────────────
    laps_rows = []
    if LAPS_CSV_PATH and os.path.exists(LAPS_CSV_PATH):
        with open(LAPS_CSV_PATH, "r", encoding="utf-8") as f:
            laps_rows = list(csv.DictReader(f))

    if LAPS_CSV_PATH and os.path.exists(LAPS_CSV_PATH):
        lap_ids_in_csv = set(r.get("activity_id", "") for r in laps_rows)
        acts_with_laps = sum(1 for r in all_rows if str(r.get("activity_id", "")) in lap_ids_in_csv)
        print(
            f"Laps: {len(laps_rows):,} splits across {acts_with_laps}/{len(all_rows)} activities "
            f"({acts_with_laps/len(all_rows)*100:.1f}% coverage)",
            flush=True,
        )

    if FETCH_LAPS and (new_rows or BACKFILL_LAPS):
        existing_lap_ids = {r.get("activity_id", "") for r in laps_rows}
        source = all_rows if BACKFILL_LAPS else new_rows
        to_fetch = [
            r for r in source
            if r.get("activity_id") and str(r["activity_id"]) not in existing_lap_ids
        ]
        if to_fetch:
            print(f"Fetching laps for {len(to_fetch)} new activities...", flush=True)
            new_lap_rows = []
            for i, act_row in enumerate(to_fetch):
                laps = fetch_activity_laps(client, str(act_row["activity_id"]))
                new_lap_rows.extend(laps)
                if i < len(to_fetch) - 1:
                    time.sleep(0.5)
            if new_lap_rows:
                laps_rows = laps_rows + new_lap_rows
                lap_fieldnames = ["activity_id", "lap_index", "distance_km",
                                  "duration_min", "avg_pace_min_km",
                                  "avg_hr", "max_hr", "calories"]
                with open(LAPS_CSV_PATH, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=lap_fieldnames, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(laps_rows)
                print(f"{len(new_lap_rows)} lap records saved to {LAPS_CSV_PATH}", flush=True)

    # ── Garmin race predictions ────────────────────────────
    race_predictions = fetch_garmin_race_predictions(client)

    # Regenerate training-history.md with fresh data
    generate_training_history(all_rows, laps_rows, race_predictions)

    if ACTIVE_PLAN.is_active:
        try:
            coverage = managed_coverage_days(load_manifest(PATHS.workout_manifest), datetime.today().date())
            if coverage < 14:
                print(f"Managed Garmin workout coverage is {coverage} days. Ask whether to preview the next 14 days.", flush=True)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Warning: workout coverage could not be checked: {exc}", flush=True)

    # ── Auto-update athlete-profile.md ────────────────────
    profile_path = str(Path(TRAINING_HISTORY_PATH).parent / "athlete-profile.md") if TRAINING_HISTORY_PATH else None
    latest_vo2 = None
    for row in reversed(all_rows):
        if row.get("vo2max", "") not in ("", None):
            latest_vo2 = float(row["vo2max"])
            break
    # Compute 4-week average
    parsed_acts = _parse_activities(all_rows)
    weekly_km = defaultdict(float)
    for a in parsed_acts:
        weekly_km[_week_start(a["date"])] += a["distance_km"]
    last_4_weeks = sorted(weekly_km.keys())[-4:]
    avg_4w_km = sum(weekly_km[w] for w in last_4_weeks) / len(last_4_weeks) if last_4_weeks else None
    auto_update_athlete_profile(profile_path, latest_vo2, avg_4w_km)

    print("Done!", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.", flush=True)
        raise SystemExit(130) from None
