---
name: running-coach
description: Route GarminCoach setup and running-coaching requests after checking local readiness. Use for general running, Garmin, training-plan, or coaching requests in a GarminCoach workspace.
---

# Running Coach Router

Run `python setup_status.py --json` first; its `ready_for` says what the
workspace supports right now. While `ready_for.coaching` is false, guide only
the missing non-secret decisions named in `requirements`, show proposed local
file changes, and wait for confirmation before writing. The athlete enters
`.env` credentials directly; never print or request their values.

During setup, record the athlete's goal, weekly running availability,
strength-day timing, session preferences, injury history, and their low-aerobic
zone mapping in `coaching/athlete-profile.md`. Ask for the goal rather than
assuming one, offering the goal types `running-plan-design` defines, and record
its type and date. Confirm which of the athlete's zones count as easy and as
hard, as `running-intensity` describes; if that is not the default split of
their zone list into thirds, set `EASY_ZONE_MAX` and `HARD_ZONE_MIN` in
`athlete_config.py`. These are decision inputs, not a fixed weekly recipe;
route plan design and material plan changes to their specialised skills.

When `ready_for.sync` is true, run `sync.py`. If it fails, disclose that the
facts end at `latest_activity` and use them only with that caveat. Read
`coaching/athlete-profile.md`, `coaching/training-history.md`, the relevant
journal entries, and `coaching/coach-log.md` before prescribing. Route a new
activity to `running-post-race` only after race confirmation; otherwise route
it to `running-session-review`. Follow its journal handoff before pattern
review.

When `workout_coverage_days` is a number below 14, ask whether the athlete
wants a preview; never send a background notification or load workouts without
the explicit request.

Do not prescribe while `ready_for.coaching` is false, treat a missing active
plan as an error, or make remote Garmin changes without the explicit workout
skill flow.
