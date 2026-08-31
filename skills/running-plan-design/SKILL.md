---
name: running-plan-design
description: Propose or redesign a GarminCoach training block from current evidence. Use for a new race build, future week, taper, or confirmed plan redesign.
---

# Plan Design

Read profile, history, journal, Coach Model, availability, constraints, and
race context. Propose the human rationale and dated sessions first. Do not
write an active plan until the athlete approves it.

After approval, update `coaching/training-plan.md` with exactly one valid
`plan-data` JSON block. It is the single source for compliance and Garmin
workouts. Validate it with `garmin_coach.plan.parse_training_plan`; preserve the approval/change
history in prose. Hand any requested watch loading to `running-garmin-workouts`.
