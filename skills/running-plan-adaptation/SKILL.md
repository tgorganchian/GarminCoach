---
name: running-plan-adaptation
description: Safely adapt an active GarminCoach training plan using recent load, compliance, feedback, and journal evidence. Use after fatigue, pain, missed quality work, or a weekly check-in.
---

# Plan Adaptation

Read the active plan, generated compliance, recent facts, relevant journal
entries, coach log, and explicit athlete limits. Apply the plan's safety gates
and traffic-light rules; make the smallest justified change and record the
evidence and decision in `coaching/coach-log.md` and the journal.

Every adaptation serves the plan's stated goal. If the goal itself has changed —
a new race, a new target, a shift to general fitness — that is a redesign for
`running-plan-design`, not an adaptation.

## Compare plan against execution before changing load

Look at session execution, recent volume, intensity distribution, HR/pace
response, recovery, pain, athlete narrative, weather, strength load, and whether
the same signal appears more than once. Observed intensity outranks the name of
the session: a run titled "easy" that was run at tempo is tempo.

Read the intensity split the way it is computed. The Weekly Intensity Split in
`coaching/training-history.md` is time-weighted and split lap by lap where lap
data exists, so a quality session already carries its warm-up, recoveries, and
cooldown as easy running. The same section names which of the athlete's
configured zones count as easy, moderate, and hard; use those bands rather than
assuming a five-zone system. Check the `From laps` coverage before reacting to a
number: a week with low coverage was classified whole-activity by average HR,
which overstates its hardest band, and is not evidence of an intensity problem
on its own.

Treat interval/tempo work, a demanding long run, racing, hills, and heavy
lower-body strength as a combined stress budget. Do not make up missed quality
by stacking it into another session or by silently making an easy or long run
harder.

## Adjust by the minimum that the evidence supports

With poor recovery, pain, or accumulating stress, protect aerobic volume and
reduce, shorten, reschedule, or remove the least essential intensity first —
least essential meaning least connected to the stated goal.

With a sustained good response, progress one relevant variable at a time —
volume, long-run duration, density, specificity, or intensity — and say what
makes the athlete ready. Anchor the new value to the athlete's own history:
compare it with the recent weekly median, the longest recent run, and the
observed quality frequency rather than applying a fixed percentage. Evidence
that unlocks more is concrete — key sessions completed at target with a normal
HR response, recovery holding, no pain, and the athlete's own account agreeing.
A single good week is not that evidence; a single bad session is not proof of
overload either.

Keep roughly 80% low-aerobic running across the block, counting warm-ups,
cooldowns, and recovery running as the easy running they are. A single week may
sit below that with a stated reason; a block drifting below it is what to
correct. State the zone mapping being used.

## Before requesting approval

Show the concrete changed sessions, the total-load and intensity-mix effect
against both the history and the 80% target, recovery/strength spacing,
evidence, uncertainty, and the next review trigger. An adaptation is a coaching
decision, not a way to force a predefined weekly template.

Ask for approval before changing the confirmed `PLAN-DATA` block. Do not adapt
an absent or invalid plan; offer retrospective coaching or a new plan proposal
instead. Hand approved future-workout changes to `running-garmin-workouts`.
