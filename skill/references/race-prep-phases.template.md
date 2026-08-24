# Race Prep Phases — Block Map

> **Note**: the week-by-week plan lives in `training-plan.md` and takes
> priority over the session-level detail here. Use this file for the macro
> block map and race-day execution notes.

---

## Block map for your current race build

Replace this section with your own blocks as you build toward a race —
dates, weekly structure, volume targets, and exit criteria for each block.
The generic phase guide below tells you what a block should generally
contain; this section is where you make it concrete for the race you're
actually training for.

| Block | Dates | Objective |
|---|---|---|
| | | |

---

## Race-day execution plan

For each upcoming race, write the pacing plan and nutrition plan here before
race day — not after. Something like:

- Km 0–X: target pace, HR ceiling
- Km X–Y: hold goal pace
- Km Y–finish: push only if HR/form allow

**Pre-race checklist:**
- No new foods in the days before
- Race shoes broken in, not worn out
- Carb-loading plan if relevant

**Race nutrition plan:** gels/fuel, timing relative to aid stations, what's
been rehearsed in training (never debut anything on race day).

---

## Generic principles (for any race)

Apply these when adding a new race to the calendar and the block map needs
to be re-derived.

### 1. Base / Aerobic foundation
**Duration**: 4–8 weeks. High Z1–Z2 volume, strides 2–3×/week, one moderate
long run. No structured speedwork yet. **Ready to advance when**: weekly
volume has been consistent for 3+ weeks and easy pace feels fluid.

### 2. Build / Threshold development
**Duration**: 4–8 weeks. 1–2 tempo runs/week (20–40 min at threshold). Long
run with the last 20–25% at marathon/half pace. Optional short hill repeats.
**Ready to advance when**: tempo pace is improving and long runs feel
controlled at moderate effort.

### 3. Peak / Race-specific
**Duration**: 3–4 weeks. Intervals at or faster than goal pace, long runs at
race pace or tune-up races, easy volume slightly reduced. One race simulation
or time trial. **Ready to taper when**: quality feels solid, same pace at
lower HR.

### 4. Taper
- 5K/10K: 7–10 days
- Half Marathon: 10–14 days
- Marathon: 2–3 weeks

Cut volume 20–40% (marathon) or 15–25% (shorter distances). **Keep
intensity** — don't strip all quality along with volume. Short race-pace
efforts to stay sharp. **Common mistake**: cutting intensity along with
volume → heavy legs on race day.

### Distance-specific cues

- **5K**: VO2max focus (800m–1200m repeats at 5K pace), 1-week taper, race
  simulation of 2×2K at goal pace.
- **10K**: Mix of threshold + intervals, 10–12 day taper, long run up to ~16km.
- **Half Marathon**: Threshold + long run are king, long run 18–21km with
  race-pace km, 2-week taper.
- **Marathon**: Aerobic base is everything, long runs 32–35km, multiple
  marathon-pace long runs in the final 8 weeks, full 3-week taper.

---

## Post-race protocol

Run this after **any** race (tune-up or A-race), fully, before recommending
the next block.

### 1. Split analysis
Read the lap file for the race activity (join by `activity_id`). Was it a
positive split, negative split, or even pace? How much did km-to-km pace
vary? Was the first 3km conservative, on target, or too fast?

### 2. Compare against the execution plan
Log actual deviations vs. the plan written in "Race-day execution plan"
above. Was a deviation a tactical call or an execution error?

### 3. HR management
How long did HR take to settle in the first 2km? Did it drift steadily
(normal aerobic drift) or spike abruptly? Finished with reserves, or hit the
limit? Compare against the easy-day HR baseline — did it reflect pre-race
accumulated fatigue?

### 4. Update PR and VDOT
If the result improves the current PR:
1. Update the "Race history and PRs" table in `athlete-profile.md`
2. Update `PERSONAL_RECORDS` in `athlete_config.py` so VDOT recalculates on
   the next sync
3. Recalculate VDOT and compare: how much did it rise? What are the new
   derived training paces? Do the current profile paces still hold?

### 5. Next-block evaluation

| Result vs. goal | Action |
|---|---|
| Beat the goal | Consider a more ambitious pace goal for the next A-race |
| Met the goal | Continue the plan unchanged — the next block is validated |
| Close (±2–3%) | Continue; monitor the next 2 weeks |
| Well off (>3–4%) | Reconsider the next block; possibly extend base or adjust the goal |

### 6. Post-race recovery

| Time post-race | Recommendation |
|---|---|
| Days 1–2 | Full rest or walking. No running. |
| Days 3–4 | Up to 30 min very easy Z1, only if the body wants it |
| Days 5–7 | Short easy runs (5–7km Z1–Z2). Check how it feels before any quality |
| Week 2 | Resume normal structure if pain-free. First light quality (fartlek or strides). |
| Tune-up race | No more than ~5 days of recovery before resuming the plan |
| A-race | 10–14 days of real recovery before any quality |

> **Note**: the body takes longer to recover from a race than from an
> equivalent-distance training run — muscle damage from race pace under
> fatigue is disproportionate. Don't rush it.
