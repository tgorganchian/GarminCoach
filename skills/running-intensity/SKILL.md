---
name: running-intensity
description: Count and judge running intensity in GarminCoach — the 80% low-aerobic target, planned intensity by step, the synced Weekly Intensity Split, zone bands, and the combined stress budget. Use when proposing, adapting, or checking a plan's intensity mix.
---

# Intensity Accounting

## Target

Aim for roughly 80% of running time at low-aerobic intensity across the block,
counting warm-ups, cooldowns, and recovery running as the easy running they
are. A single week may sit below that with a stated reason — a build week, a
race week, a sharpening week — as long as the block holds. A block that misses
the target is a design error to correct, not a variation.

## Count planned intensity by step

Compute the planned split from the `plan-data` steps rather than estimating it.
`warmup`, `cooldown`, and `recovery` steps are easy running; an `interval`
counts in the band of its target. No session is wholly hard: 4x800m between a
1600m warm-up and a 1600m cooldown is mostly easy running, and counting it as a
hard session inflates the intensity of the whole week. A long run holding a
sustained block counts that block in its band and the rest as easy, and must be
declared as a key stressor and offset elsewhere in the week.

## Read the observed split the way it is computed

The Weekly Intensity Split in `coaching/training-history.md` is time-weighted
and split lap by lap where lap data exists, so a quality session already
carries its warm-up, recoveries, and cooldown as easy running. Check the
`From laps` coverage before reacting to a number: a week with low coverage was
classified whole-activity by average HR, which overstates its hardest band, and
is not evidence of an intensity problem on its own. Observed intensity outranks
the name of the session: a run titled "easy" that was run at tempo is tempo.

## Zone bands

The athlete's system is whatever they configured — three physiological zones
around LT1/LT2, Garmin's five, or their own split. The line under the Weekly
Intensity Split names which of their zones fall in the easy, moderate, and hard
bands. Read it there instead of assuming five zones, state the mapping you
used, and do not equate the 80/20 literature's threshold-based zones with
Garmin's automatically.

## Combined stress budget

Interval/tempo work, a demanding long run, racing, hill work, and heavy
lower-body strength all consume recovery budget; assess their combined load
rather than counting only sessions named "quality". Do not make up missed
quality by stacking it into another session or by silently making an easy or
long run harder.
