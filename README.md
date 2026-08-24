# GarminCoach

Your Garmin data, an AI coach that actually reads it, and a feedback loop that
gets sharper every week.

GarminCoach pulls your running history out of Garmin Connect, turns it into a
rich, structured training report, and hands that report to an AI coaching
skill (built for Claude Code and Codex) that gives you real, personalized
coaching instead of generic training-app advice — anchored to your actual HR
zones, your actual paces, your actual race history, and what you told it
about how a session felt.

It's not a dashboard. It's not a chatbot bolted onto a CSV. It's a small
pipeline plus a skill that knows how to read it.

## What it actually does

- **Syncs your training data** (`sync.py`) — pulls runs from Garmin Connect
  and computes the stuff a real coach looks at: weekly volume with easy/quality
  split, HR-zone distribution (km-weighted, not run-count), Acute:Chronic
  Workload Ratio, VDOT and race predictions (Jack Daniels' formula), plan
  compliance, running economy trends (cadence/stride), recovery spacing
  between hard sessions, and weather-adjusted anomaly detection — so an
  unusually high HR on a hot, humid day doesn't get misread as fatigue.
- **Pushes your plan to the watch** (`create_workouts.py`) — builds structured
  workouts (warmup/interval/repeat/cooldown, pace bands) and schedules them
  directly in Garmin Connect, so they show up on your watch the day you're
  supposed to run them.
- **Captures how a session actually felt** (`collect_feedback.py`) — an
  optional voice-feedback pipeline: record a note to your own Telegram Saved
  Messages right after a run, and it gets transcribed locally (faster-whisper)
  into a queue the coaching skill reads and folds into its analysis. No app,
  no typing after a hard session.
- **Coaches you** (`skill/`) — a Claude Code / Codex skill that loads your
  profile, your training history, your plan, and your past feedback before
  saying anything, flags real risk signals (volume spikes, missed recovery,
  HR drift, stalled cadence), and adapts your plan week to week based on how
  you're actually responding — not a fixed script.

## Why it gets better with time, not worse

Most training tools are most useful on day one and then just accumulate rows.
This one compounds the opposite way. The more runs, races, and feedback you
feed it:

- VDOT and pace predictions get more accurate as your PR history grows
- HR-zone and gear-change baselines get sharper (a shoe change or a fitness
  gain look very different once you have weeks of data on both sides of it)
- ACWR and recovery-spacing signals need a real training history to mean
  anything — week one, there's nothing to compare against
- The coach's memory of *why* a plan changed (your subjective feedback,
  cross-checked against the objective data) becomes the thing that makes
  session two hundred smarter than session twenty

That compounding is the actual point of the project — not the sync script by
itself.

## Optional: pair it with Obsidian as a running "second brain"

GarminCoach doesn't need Obsidian to work. But if you already keep a vault,
wiring the two together turns this from "a coach that answers questions" into
a running knowledge base that writes itself: a note per race (splits, HR
drift, tactical patterns, PRs) with your objective data automatically filled
in, a weekly training log that folds together your voice/text feedback with
what the data showed, and a running profile note that tracks your PRs and
tactical patterns over time — all linked, all searchable, all queryable via
Dataview.

The skill treats data and narrative as strictly separate layers: `sync.py`
owns the numbers, the Vault owns the story. Nothing auto-generated ever gets
copied into the Vault (it would go stale the moment you sync again) — only
your race debriefs, your weekly narrative, and the coach's read on them do.
See `skill/SKILL.md` for the exact protocol if you want to wire this up.

## Quickstart

```bash
git clone <this-repo> GarminCoach
cd GarminCoach
pip install -r requirements.txt

cp .env.example .env                              # fill in your Garmin/Strava/Telegram creds and paths
cp athlete_config.example.py athlete_config.py     # fill in your HR zones, PRs, race calendar, training plan
cp workout_plan.example.py workout_plan.py         # optional, only needed for create_workouts.py

python sync.py                 # first run pulls your full history; later runs are incremental
python create_workouts.py      # optional: pushes your structured workouts to Garmin Connect
python collect_feedback.py --login   # optional: one-time Telegram auth for voice feedback
```

`athlete_config.py`, `workout_plan.py`, and `.env` are already in
`.gitignore` — they hold your real data, they're meant to sit right here next
to the scripts, and they never get committed.

## Configuration

| File | What goes in it |
|---|---|
| `.env` | Garmin login, file paths, and optional Strava/Telegram credentials. See `.env.example`. |
| `athlete_config.py` | HR zones, personal records, race calendar, your week-by-week training plan. See `athlete_config.example.py`. |
| `workout_plan.py` | The actual structured workouts `create_workouts.py` schedules — written with the `step`/`repeat`/`workout` DSL. See `workout_plan.example.py`. Only needed if you use `create_workouts.py`. |

## Using the coaching skill

`skill/SKILL.md` is written for Claude Code and Codex (or any agent that
supports Markdown skill files). Copy the `skill/` folder into wherever your
tool loads user skills from, then point it at your own `references/` files
(templates in `skill/references/`, a filled-out fictional example in
`skill/references/example/` so you can see the expected shape before writing
your own).

The skill:
1. Runs `sync.py` before answering anything, so it's never coaching off stale
   data
2. Loads your profile, then your training history, then your coaching log —
   in that order, because context matters more than raw numbers
3. Proactively flags risk (volume spikes, missed recovery, HR drift, taper
   windows before a race) instead of waiting to be asked
4. Runs a weekly check-in loop: cross-references your subjective feedback
   against the objective data, applies a 🟢/🟡/🔴 adaptation protocol, and
   edits your actual plan — not just talks about it

## Project structure

```
GarminCoach/
├── sync.py                    # Garmin -> CSV + training-history.md
├── create_workouts.py         # push structured workouts to Garmin Connect
├── collect_feedback.py        # optional voice-feedback pipeline
├── athlete_config.example.py  # -> athlete_config.py (yours, gitignored)
├── workout_plan.example.py    # -> workout_plan.py (yours, gitignored)
├── .env.example                # -> .env (yours, gitignored)
├── requirements.txt
├── skill/
│   ├── SKILL.md
│   └── references/
│       ├── *.template.md      # copy + fill in for your own athlete
│       └── example/           # a fully worked fictional athlete
└── docs/
    └── SETUP.md
```

## Notes

- Uses the community [`garminconnect`](https://github.com/cyberjunky/python-garminconnect)
  library — this is not Garmin's official API, and it can break when Garmin
  changes something server-side. The upstream repo tends to patch fast.
- This handles your training and (if you use the feedback pipeline) health
  data. Keep `.env`, `athlete_config.py`, credentials, and tokens local —
  they're gitignored by default; don't force-add them.
- `collect_feedback.py` is fully optional and only reads your own Telegram
  Saved Messages — it never touches any other chat.
