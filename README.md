# GarminCoach

GarminCoach is an installable, privacy-safe local running-coaching workspace.
It brings Garmin facts, a mandatory coaching journal, confirmed training plans,
and Garmin workout rendering into one local project.

Start with the [Guide](GUIDE.md) for setup, data ownership, the `PLAN-DATA`
contract, the Garmin preview/apply lifecycle, and verification.

## Quick start

```bash
npx create-garmin-coach my-coach
cd my-coach
python -m pip install -r requirements.txt
# Ask a supported coaching agent to begin setup.
```

Node is needed only for `npx` scaffolding. Normal sync, analysis, and workout
rendering use the generated Python project. Credentials are entered directly in
the local `.env`; a coaching agent reports missing variable names but never
reads them back.

## What the public release provides

- A scaffold that copies only generic public files and creates ignored local
  coaching state.
- A readiness check that separates required Garmin/coaching configuration from
  optional integrations.
- Garmin history, a generated `coaching/training-history.md`, and a mandatory
  journal for session readings and weekly synthesis.
- One confirmed `coaching/training-plan.md` shared by compliance and Garmin
  workout rendering.
- A preview-first Garmin renderer that only writes after a confirmed `--apply`.
- Modular coaching skills for routing, session review, journal sync, patterns,
  planning, workouts, and post-race work.

Optional voice feedback, an Obsidian vault, Garmin workout upload, and an
active plan do not block coaching from starting.

## Local data ownership

| Data | Authoritative local location |
| --- | --- |
| Raw activities and laps | `data/` managed by `sync.py` |
| Aggregated history | `coaching/training-history.md`, generated |
| Stable profile and Coach Model | `coaching/athlete-profile.md` |
| Material decisions | `coaching/coach-log.md` |
| Confirmed plan and workout definitions | `coaching/training-plan.md` |
| Session narrative and coach readings | `coaching/journal/` by default |
| Garmin workouts owned by this system | ignored local manifest |

No personal state belongs in Git, the npm package, templates, examples, or
skills. The [Guide](GUIDE.md) explains the complete privacy model.

## Repository map

The repository contains generic, publishable source material. Running the
scaffold creates a separate local workspace for the athlete's configuration,
history, journal, tokens, and feedback; that private state is ignored by Git.

| Command | Purpose |
| --- | --- |
| `sync.py` | Fetch Garmin facts and generate training history. |
| `setup_status.py` | Report missing local configuration without printing secrets. |
| `garmin_workouts.py` | Preview and apply confirmed plan workouts. |
| `collect_feedback.py` | Optionally collect and transcribe Telegram voice notes. |
| `release_audit.py` | Check tracked files and the npm tarball before release. |

## Public project layout

```text
GarminCoach/
|- .env.example
|- athlete_config.example.py
|- README.md and GUIDE.md       # overview and complete operating guide
|- package.json
|- bin/                         # npx scaffold entry point
|- sync.py, setup_status.py, garmin_workouts.py, collect_feedback.py
|- release_audit.py             # release-only verification command
|- garmin_coach/                # internal Python implementation
|- skills/                      # modular coaching instructions
|- templates/                   # blank local-workspace starter files
|- examples/                    # fictional coaching examples
`- tests/                       # Python behavior and Node packaging tests
```

The project may be prepared and tested as an npm package, but publishing is a
separate action requiring the maintainer's account and credentials. It is not
part of this work.
