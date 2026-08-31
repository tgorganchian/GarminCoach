---
name: running-coach
description: Route GarminCoach setup and running-coaching requests after checking local readiness. Use for general running, Garmin, training-plan, or coaching requests in a GarminCoach workspace.
---

# Running Coach Router

Run `python setup_status.py --json` first. If required setup is incomplete,
guide only the missing non-secret decisions, show proposed local file changes,
and wait for confirmation before writing. The athlete enters `.env` credentials
directly; never print or request their values.

During setup, record the athlete's goal, weekly running availability,
strength-day timing, session preferences, injury history, and their low-aerobic
zone mapping in `coaching/athlete-profile.md`. The goal is a dated race, a time
target at a distance, or a general goal such as building aerobic base, holding
fitness, or returning from a layoff; ask for it rather than assuming one, and
record its type and date. Zone systems vary in size, so confirm which of the
athlete's zones count as easy and as hard; if that is not the default split of
their zone list into thirds, set `EASY_ZONE_MAX` and `HARD_ZONE_MIN` in
`athlete_config.py`. These are decision inputs, not a fixed weekly recipe;
route plan design and material plan changes to their specialised skills.

When ready, run `sync.py`. If it fails, disclose the freshness caveat and use
existing facts only with that caveat. Read `coaching/athlete-profile.md`,
`coaching/training-history.md`, the relevant journal entries, and
`coaching/coach-log.md` before prescribing. Route a new activity to
`running-post-race` only after race confirmation; otherwise route it to
`running-session-review`. Follow its journal handoff before pattern review.

On each interaction or sync, check manifest-owned workout coverage. If fewer
than 14 days remain, ask whether the athlete wants a preview; never send a
background notification or load workouts without the explicit request.

Do not prescribe while setup is incomplete, treat a missing active plan as an
error, or make remote Garmin changes without the explicit workout skill flow.
