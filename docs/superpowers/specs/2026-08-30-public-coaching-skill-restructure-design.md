# Public coaching skill restructure

## Purpose

Turn GarminCoach into an installable, privacy-safe coaching system whose
modular skill structure matches the private coaching workflow without carrying
any athlete-specific data, paths, credentials, preferences, history, or
integrations.

The public project will create a local coaching workspace, guide a new user
through configuration, analyse their Garmin history, retain a mandatory
journal, and render a confirmed plan into Garmin workouts.

## Goals

- Provide `npx create-garmin-coach <directory>` as the primary onboarding
  path. It creates a generic GarminCoach project; Node is required only for
  scaffolding, not for normal runtime use.
- Replace the monolithic skill with a router and specialised skills that have
  the same responsibilities and handoffs as the private workflow.
- Detect incomplete local setup before attempting sync or coaching, then guide
  the user through the missing non-secret configuration and write it after a
  final confirmation.
- Make a weekly coaching journal mandatory. Obsidian is an optional location
  for that journal, not a requirement for the workflow.
- Keep confirmed `training-plan.md` as the one plan source for compliance and
  Garmin workouts.
- Render workouts from structured plan data. Users never edit renderer code
  for individual sessions.
- Keep all public files generic. Personal state stays local and ignored by
  Git.

## Non-goals

- Do not publish, copy, or derive real athlete state from the private system.
- Do not require voice feedback, Obsidian, a Garmin workout upload, or an
  active training plan before coaching can begin.
- Do not provide background notifications. Workout coverage is evaluated on a
  sync or interaction and surfaced by the coach then.
- Do not retain the legacy `workout_plan.py` / `create_workouts.py` workflow
  alongside the plan renderer; two plan sources would drift.

## Public project layout

```text
GarminCoach/
|-- package.json                         # npm package and scaffold CLI
|-- bin/create-garmin-coach.mjs          # npx entry point
|-- sync.py                              # Garmin facts and generated history
|-- training_plan.py                     # PLAN-DATA parser and plan queries
|-- garmin_workouts.py                   # preview/apply renderer and manifest
|-- setup_status.py                      # local readiness checks, JSON output
|-- athlete_config.example.py            # generic machine-readable template
|-- .env.example                         # blank, non-secret path defaults
|-- skills/
|   |-- running-coach/
|   |-- running-session-review/
|   |-- running-journal-sync/
|   |-- running-pattern-review/
|   |-- running-plan-design/
|   |-- running-plan-adaptation/
|   |-- running-garmin-workouts/
|   `-- running-post-race/
|-- templates/coaching/                  # tracked blank MD templates
|-- examples/coaching/                   # tracked fictional examples only
|-- tests/
`-- docs/
```

The scaffold copies a whitelist of public project files into a new, empty
destination. It creates local working copies under `coaching/`, including
`athlete-profile.md`, `coach-log.md`, `training-plan.md`, generated
`training-history.md`, and `journal/`. Those working copies, Garmin tokens,
audio feedback, CSV data, manifests, and all configuration with athlete data
are ignored by Git.

## Setup and readiness

`setup_status.py --json` reports named setup requirements without reading back
or printing secrets. It distinguishes required setup from optional
integrations:

| Requirement | Owner | Required before sync/coaching |
| --- | --- | --- |
| Garmin credentials and local paths | `.env` | Yes for sync; no for guided setup |
| Zones, records, calendar, classifiers, weather fallback | `athlete_config.py` | Yes for data-driven sync |
| Athlete profile and coaching references | `coaching/` | Yes for normal coaching |
| Training plan | `coaching/training-plan.md` | No; an explicit no-active-plan state is valid |
| Journal | `coaching/journal/` by default | Yes; created on setup |
| Obsidian location | local configuration | No |
| Voice feedback | `.env` and feedback files | No |

On every entry, `running-coach` first checks readiness. If incomplete, it
enters onboarding instead of syncing or prescribing. It asks only for the
data required by the missing setup, guides the user one decision at a time,
and presents the non-secret files it will write. The user confirms before
those local files are created or updated. The user enters credentials into
`.env` themselves; the skill only identifies missing variables.

## Skill contracts and flow

`running-coach` is the entry router. Once setup is ready it runs sync, handles
optional feedback collection, reads current coaching context, and routes work
without treating scripts as autonomous decision makers.

```text
running-coach
  |-- setup incomplete -> guided onboarding
  `-- setup ready -> sync -> new activity?
                         |-- race -> running-post-race
                         `-- session -> running-session-review
                                         -> running-journal-sync
                                         -> running-pattern-review
                                                `-- load change -> running-plan-adaptation
```

- `running-session-review` converts one non-race activity into a factual
  session reading. It separates facts, interpretation, uncertainty, athlete
  narrative, and safety signals. It does not by itself establish a pattern or
  change the plan.
- `running-journal-sync` is mandatory. It records session readings and weekly
  summaries in the local journal, preserves athlete-authored narrative, and
  associates optional audio feedback safely. Its storage root defaults to
  `coaching/journal/` and may point to an Obsidian folder.
- `running-pattern-review` reads the journal alongside Garmin facts to promote
  repeated evidence into a revisable Coach Model, retain candidates as
  observations, and retire refuted patterns.
- `running-plan-design` creates or redesigns a block from current evidence.
  It writes one confirmed plan and one valid `PLAN-DATA` block only after the
  user approves the proposal.
- `running-plan-adaptation` applies the active plan's safety gates and traffic
  light rules to feedback, compliance, recent data, and journal evidence. It
  records material decisions and updates the plan only when justified.
- `running-garmin-workouts` previews or reconciles a minimum 14-day horizon
  after an explicit request. It never owns workouts outside its manifest.
- `running-post-race` confirms a real race, evaluates execution and tactics,
  updates records when applicable, records learning, and defines recovery
  before quality work resumes. It is a specialised session review, not merely
  a high-heart-rate classification.

Every analysis skill reads relevant journal entries. New session and race
reviews always result in a coach reading in the journal, even without voice
feedback or athlete narrative.

## Data ownership and privacy

| Data | Authoritative location |
| --- | --- |
| Raw activities and laps | `sync.py` local data files |
| Aggregated history | generated `coaching/training-history.md` |
| Stable profile and Coach Model | `coaching/athlete-profile.md` |
| Material coaching decisions | `coaching/coach-log.md` |
| Confirmed plan and workout definitions | `coaching/training-plan.md` |
| Per-session narrative and coach readings | mandatory journal |
| Garmin-owned workouts managed by this system | local manifest |

The journal records concise evidence and interpretation; it does not duplicate
raw CSV data. Subjective feedback is evidence of sensation and context, but
objective data leads physiological interpretation. Pain, injury, or an
explicit athlete limit always wins for safety.

## Plan and workout renderer

The human-readable plan includes exactly one machine-readable `PLAN-DATA`
block. It has a versioned schema containing plan identity, weeks, dated
sessions, and composable steps. A session can use distance/time, warmup,
cooldown, interval, recovery, repeat groups, and optional target ranges.

`garmin_workouts.py` is generic compiler-like infrastructure:

1. Parse and validate the active plan.
2. Select dated sessions inside a requested horizon of at least 14 days.
3. Render each session's generic steps into Garmin workout payloads.
4. Compare a deterministic fingerprint with the local manifest.
5. Produce a preview containing `create`, `update`, `reschedule`, `unchanged`,
   and `unschedule` actions.
6. Perform remote writes only with `--apply`, after the user confirms that
   exact preview.

The plan contains user-specific details such as an 8-by-400-metre session;
the renderer contains no athlete-specific code. Unsupported workout concepts
are either expressed through supported primitives or added once to the schema,
renderer, and tests for all users. Manual remote edits and workouts absent
from the manifest remain outside the pipeline's ownership.

The coach checks manifest coverage on each interaction or sync. When the
remaining managed horizon is low, it asks whether the user wants to preview
and load the next 14 days. It does not send background notifications.

## Code migration

`sync.py` will use `training_plan.py` for plan compliance and plan-derived
session metadata. `athlete_config.py` remains the local, ignored
machine-readable configuration for values needed by data processing. The
onboarding flow writes it from confirmed answers, alongside the Markdown
references, so the user does not edit application code.

The legacy direct workout script and its local workout-plan file are removed.
Documentation and tests move to the plan renderer flow. No default gear name,
device, language, city, calendar, race, pace, shoe, historical result, local
filesystem path, contact detail, or private integration is preserved.

## Errors and safety boundaries

- Incomplete setup yields a precise readiness report and onboarding; it never
  makes a best-effort sync from template data.
- A sync or feedback collection failure is reported and existing data may be
  used only with an explicit freshness caveat.
- An invalid or absent active plan prevents workout rendering, not ordinary
  retrospective coaching.
- The renderer previews by default and validates manifest ownership, workout
  name, schedule, and remote state before changing a managed future workout.
- Ambiguous race classification or audio-to-session association requires a
  user question before a narrative record is written as a fact.
- The project never prints, commits, packages, or asks an agent to echo a
  credential or token.

## Verification

- Python tests cover setup-state detection, plan parsing and validation,
  rendering steps, fingerprints, manifest reconciliation, coverage warnings,
  and sync's integration with the structured plan.
- Node tests cover CLI argument handling, empty-destination protection,
  whitelist copying, and absence of ignored/private paths from a generated
  project.
- Fixture projects contain only synthetic values. Tests perform no Garmin,
  Telegram, Obsidian, or npm publish operation.
- A deterministic public-release audit scans all tracked files and the npm
  package contents for known private-path patterns, credentials, real
  configuration files, and template markers that should not be distributed.
- Documentation verification ensures the quickstart, setup guide, project
  layout, skill installation, journal configuration, and workout lifecycle
  describe the same supported workflow.

## Release boundary

The repository is prepared as an npm package and can be exercised locally.
Publishing to npm is a separate explicit action requiring the maintainer's
account and credentials; it is not part of this implementation.
