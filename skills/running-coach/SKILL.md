---
name: running-coach
description: Route GarminCoach setup and running-coaching requests after checking local readiness. Use for general running, Garmin, training-plan, or coaching requests in a GarminCoach workspace.
---

# Running Coach Router

Run `python setup_status.py --json` first. If required setup is incomplete,
guide only the missing non-secret decisions, show proposed local file changes,
and wait for confirmation before writing. The athlete enters `.env` credentials
directly; never print or request their values.

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
