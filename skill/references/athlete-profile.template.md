# Athlete Profile

> Always load this file when coaching. Every pace/HR recommendation should be
> personalized to this data.
>
> **The paces below should reflect current training reality** (from
> `activities.csv` / `training-history.md`), not aspirational targets. Keep a
> separate "target paces" section for race goals — see the bottom of this file.

---

## Physical data

| Field | Value |
|---|---|
| Age | |
| Weight | |
| Height | |
| Estimated VO2max | <!-- AUTO:VO2MAX --><!-- /AUTO:VO2MAX --> |

---

## Watch and metric limitations

| Field | Value |
|---|---|
| Watch | |
| Usage pattern | e.g. "only during runs" vs "worn all day" |

**Available metrics**: list what your device actually reports.

**NOT available** — list what it doesn't, so the skill never references or
requests these.

---

## Gear

### Shoes

<!-- AUTO:SHOES -->
_Not tracked yet._
<!-- /AUTO:SHOES -->

> List each pair's role (easy runs, speed work, race day) so the coach can
> flag when a HR change is actually a gear change.

---

## Heart rate profile

| Field | Value |
|---|---|
| Max HR | |
| Resting HR | |
| HR Reserve (HRR) | |
| Method | Karvonen (HRR-based) or %HRmax |

### HR zones

| Zone | Name | % HRR | bpm range | Feel |
|---|---|---|---|---|
| Z1 | Easy / Recovery | 50–60% | | Very comfortable, full conversation |
| Z2 | Aerobic Base | 60–70% | | Comfortable, can talk in sentences |
| Z3 | Tempo / Threshold | 70–80% | | Comfortably hard, short phrases |
| Z4 | Hard / VO2max | 80–90% | | Hard, heavy breathing |
| Z5 | Max Effort | 90–100% | | All out |

> These bands **must match `HR_ZONES` in `athlete_config.py`** and the zone
> tables in `training-history.md`. Change one, change all three.

---

## Race history and PRs

| Distance | Time | Pace | Date | Notes |
|---|---|---|---|---|
| | | | | |

---

## 2026 race calendar

> The dynamic countdown is computed on every sync and shown at the top of
> `training-history.md`. This table is the static source of truth — keep it
> in sync with `RACE_CALENDAR` in `athlete_config.py`.

| Race | Date | Distance | Goal | Status |
|---|---|---|---|---|
| | | | | |

---

## Training context

- **Level**:
- **Primary focus**:
- **Current plan**:

---

## Weekly training structure

| Field | Value |
|---|---|
| Running days | |
| Strength sessions | |
| Historical weekly average | |
| Current 4-week average | <!-- AUTO:4WAVG --><!-- /AUTO:4WAVG --> |
| Sustainable ceiling for this build | |

### Day availability

| Day | Available | Notes |
|---|---|---|
| Mon | | |
| Tue | | |
| Wed | | |
| Thu | | |
| Fri | | |
| Sat | | |
| Sun | | |

---

## Strength training

If relevant to interpreting fatigue on adjacent running days, describe the
routine here (what day, what exercises, expected DOMS timing).

---

## Current training paces (from real runs, not targets)

| Session type | Pace | HR band | Reference |
|---|---|---|---|
| Recovery / Z1 easy | | | |
| Standard easy / Z2 | | | |
| Long run (aerobic) | | | |
| Tempo / threshold | | | |
| Intervals | | | |
| Race pace | | | |

> For VDOT-derived paces (threshold, interval, easy per Daniels), see the
> "VDOT Race Predictions & Training Paces" section in `training-history.md` —
> recalculated automatically on every sync.

### Target race paces

| Goal | Target pace | Notes |
|---|---|---|
| | | |

---

## Tactical race patterns

> Fill this in after a race debrief — pacing tendencies, how you handle
> crowded starts, closing speed, anything that should shape strategy for the
> next one.

| Pattern | Description | Implication |
|---|---|---|
| | | |
