---
name: running-garmin-workouts
description: Preview or reconcile manifest-owned Garmin workouts from a confirmed GarminCoach plan. Use only after an explicit user request to load, update, preview, or reconcile workouts.
---

# Garmin Workouts

Require a valid active `coaching/training-plan.md`. Run
`python garmin_workouts.py preview --days 14` or a longer requested horizon.
Explain the exact create, update, reschedule, unchanged, and unschedule actions
and which manifest-owned sessions they affect.

Remote writes require the user's explicit confirmation of that exact preview
and `--apply <preview-id>`. Never modify a workout absent from the local
manifest, bypass a name/date/state mismatch, or treat a manual Garmin workout
as owned.
