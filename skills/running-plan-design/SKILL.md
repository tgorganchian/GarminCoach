---
name: running-plan-design
description: Propose or redesign a GarminCoach training block from the athlete's own history and a stated goal. Use for a new race build, future week, taper, or confirmed plan redesign.
---

# Plan Design

Read profile, history, journal, Coach Model, availability, constraints, and
race context. Propose the human rationale and dated sessions first. Do not
write an active plan until the athlete approves it.

## Establish the goal before proposing anything

Do not design a block without a goal the athlete has stated. A plan with no
goal has nothing to justify its hard sessions against, and defaults to whatever
a training plan is expected to look like. Accept three kinds:

- A **dated race**: distance, date, and the athlete's intent for it (finish,
  target time, or a tune-up for a later race).
- A **time target** at a distance, with or without a date.
- A **general goal**: build aerobic base, hold current fitness, return from a
  layoff or injury, add consistency.

If the athlete has none in mind, offer the general options and let them pick
one; do not proceed with an unnamed goal. Record the goal, its type, and its
date in `coaching/athlete-profile.md`.

The goal is what makes a quality session justifiable. State which goal each
quality session serves; quality that serves no stated goal does not belong in
the plan. Under a general goal, volume and consistency are the stimulus, and
any intensity needs an explicit reason. Race specificity and peaking work are
justified by a dated race, not by a general goal.

## Read the history before proposing

`sync.py` regenerates `coaching/training-history.md` from `data/activities.csv`
and `data/activity_laps.csv`. Extract and show these, because they decide the
proposal:

- Weekly volume median and maximum over the last 4, 8, and 12 weeks. The median
  is tolerated load; a single large week is not.
- Runs per week, and how stable that frequency is.
- Longest run in the last 8 and 12 weeks.
- The observed intensity split from the Weekly Intensity Split table, together
  with its `From laps` coverage — a low coverage week is an estimate that
  overstates its hardest band.
- Which quality sessions actually appear, how often, and how the athlete
  responded: pace and HR across repeats, `feeling`, `perceived_effort`.
- Interruptions: layoffs, missed weeks, illness, and pain in the journal.
- Direction of travel: volume rising, flat, or falling.

Name whichever of these the data cannot answer, and let that uncertainty make
the proposal more conservative rather than going unmentioned.

## Anchor the plan to what the athlete has already done

History sets the level; the goal sets the direction. Compare explicitly:
planned weekly volume against the recent median, planned longest run against
the longest recent one, planned quality frequency against the observed one, and
the planned easy share against the observed one. Anything above the history is a
deliberate progression — say so, give the reason, and say how recovery is
protected. If the goal needs more than the history supports, say that and
extend the timeline or lower the target instead of opening the volume.

This cuts both ways. Do not hold an experienced athlete at a beginner's level:
if the history shows two quality sessions a week sustained across weeks with a
good response, two are justified and proposing one is ignoring the evidence.
The constraint is the athlete's data, not a template. The number of weekly
running days does not prescribe a fixed arrangement.

## Count intensity by step, not by session

Compute the planned split from the `plan-data` steps rather than estimating it.
`warmup`, `cooldown`, and `recovery` steps are easy running; an `interval`
counts in the band of its target. No session is wholly hard: 4x800m between a
1600m warm-up and a 1600m cooldown is mostly easy running, and counting it as a
hard session inflates the intensity of the whole week. A long run holding a
sustained block counts that block in its band and the rest as easy, and must be
declared as a key stressor and offset elsewhere in the week.

Show planned minutes per band for each week and for the block, next to the
observed split from the history. Aim for roughly 80% low-aerobic across the
block. Individual weeks may sit below that — a build week, a race week, a
sharpening week — as long as the block holds and the week states its reason. A
block that misses the target is a design error, not a variation.

State the zone mapping you used. The athlete's system is whatever they
configured — three physiological zones around LT1/LT2, Garmin's five, or their
own split — and `coaching/training-history.md` names which of their zones fall
in the easy, moderate, and hard bands. Read that line instead of assuming five
zones, and do not equate the 80/20 literature's threshold-based zones with
Garmin's automatically.

## Choose the week's stressors deliberately

Interval/tempo work, a demanding long run, racing, hill work, and heavy
lower-body strength all consume recovery budget; assess their combined load
rather than counting only sessions named "quality". Preserve enough easy
aerobic running and recovery spacing for the athlete's current base. Avoid
turning every run into moderate work or adding intensity merely to fill an
available day. Select the minimum quality that serves the goal, and justify any
additional demanding stimulus with recent evidence.

## Before approval

Show the proposed dates, each session's primary purpose and stress level, total
planned volume or time, the intensity mix against both the history and the 80%
target, strength interaction, recovery spacing, the progression or cutback
logic, and what observation would change the plan. Offer coaching judgment, not
a menu of workouts for the athlete to design.

After approval, update `coaching/training-plan.md` with exactly one valid
`plan-data` JSON block. It is the single source for compliance and Garmin
workouts. Validate it with `garmin_coach.plan.parse_training_plan`; preserve the
approval/change history in prose. Hand any requested watch loading to
`running-garmin-workouts`.
