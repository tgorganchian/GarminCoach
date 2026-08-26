# Setup

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

`garminconnect` is pulled straight from GitHub (the community-maintained
client) rather than PyPI, since rate-limit and auth fixes land there first.

## 2. Configure `.env`

```bash
cp .env.example .env
```

- `GARMIN_EMAIL` / `GARMIN_PASSWORD` — your Garmin Connect login. Only used
  the first time, or when saved tokens expire; after that `sync.py` reuses
  the tokens in `GARMIN_TOKEN_DIR`.
- `CSV_PATH` / `GARMIN_TOKEN_DIR` / `TRAINING_HISTORY_PATH` — absolute paths.
  `TRAINING_HISTORY_PATH` should point at wherever your coaching skill's
  `references/training-history.md` lives.
- Telegram variables are optional — leave them blank if you don't use voice
  feedback. (Shoe-mileage tracking via Strava isn't implemented — the API
  now requires a paid developer subscription — so there's no `.env` variable
  for it.)

## 3. Configure your athlete data

```bash
cp athlete_config.example.py athlete_config.py
```

Fill in your real HR zones, PRs, race calendar, and training plan. This file
is gitignored — it never leaves your machine unless you choose to commit it
somewhere yourself.

Two fields are worth getting right immediately, since a lot depends on them:

- **`HR_ZONES`** — must match whatever you tell the coaching skill in
  `athlete-profile.md`. If they drift apart, zone-distribution tables and
  coaching advice stop agreeing with each other.
- **`PERSONAL_RECORDS`** — drives the VDOT calculation and every derived
  training pace. Use your most relevant recent result per distance.

## 4. First sync

```bash
python sync.py
```

The first run pulls your full history (from `HISTORY_START_DATE` in
`sync.py` — 2024-01-01 by default, change it if you want less) and can take
a while depending on how many activities you have. Every run after that is
incremental — it only fetches what's new.

If you hit a Garmin rate limit (`429`) on the first backfill, wait a bit and
re-run; it picks up from where the CSV left off.

## 5. Optional: structured workouts on your watch

```bash
cp workout_plan.example.py workout_plan.py
```

Write your own workouts using the `step`/`repeat`/`workout` DSL (see the
example file). Then:

```bash
python create_workouts.py
```

Workouts get a name prefix (`WORKOUT_PREFIX` in `create_workouts.py`, default
`"Coach"`) so you can tell them apart from anything else on your Garmin
Connect calendar, and so `--delete` knows what's safe to remove.

## 6. Optional: voice feedback pipeline

This one has a few more moving parts because it runs a local speech-to-text
model.

1. **Get Telegram API credentials** — go to <https://my.telegram.org>, log
   in, create an app, and copy the `api_id` / `api_hash` into `.env`
   (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`).
2. **Use a separate virtualenv for this one.** `faster-whisper` pulls in
   heavy ML dependencies (CUDA libraries) you probably don't want mixed into
   the environment you use for `sync.py`. Create a dedicated venv, activate
   it, then install:
   ```bash
   pip install -r requirements-feedback.txt
   ```
3. **GPU vs. CPU** — `collect_feedback.py` defaults to `device="cuda"` with
   `faster-whisper`. If you have an NVIDIA GPU, also install the three
   `nvidia-*-cu12` packages commented at the bottom of
   `requirements-feedback.txt`. If you don't have a GPU, edit `DEVICE` and
   `COMPUTE` near the top of the script instead (e.g. `device="cpu"`,
   `compute_type="int8"`) — it'll be slower but works fine for occasional use.
4. **Authenticate once**:
   ```bash
   python collect_feedback.py --login
   ```
   This asks for your phone number and the code Telegram sends you (inside
   the app, not SMS). It saves a session file locally — that file is a
   credential, keep it out of git (already covered by `.gitignore`).
5. **Run it**:
   ```bash
   python collect_feedback.py            # pulls new voice notes, transcribes, queues them
   python collect_feedback.py --dry-run  # see what it would pull, without downloading/transcribing
   ```
   It only ever reads your own Telegram **Saved Messages** — never any other
   chat.

## 7. Install the coaching skill

Copy `skill/` into wherever your agent (Claude Code, Codex, or anything else
that reads Markdown skill files) loads user skills from. Then:

1. Copy each `skill/references/*.template.md` file, drop the `.template`
   suffix, and fill it in with your real data — or start from
   `skill/references/example/` to see a fully worked version first.
2. Update the `<repo>` and `<skill>` placeholders in `SKILL.md` to your
   actual paths.
3. Point `TRAINING_HISTORY_PATH` in `.env` at your real
   `references/training-history.md` so `sync.py` writes there directly.

## Troubleshooting

- **Garmin login keeps failing** — Garmin occasionally requires an MFA
  step the `garminconnect` library doesn't handle gracefully. Delete
  `GARMIN_TOKEN_DIR`'s contents and log in fresh; if it persists, check the
  [upstream repo's issues](https://github.com/cyberjunky/python-garminconnect/issues).
- **VDOT / paces look wrong** — almost always a stale `PERSONAL_RECORDS`
  entry. Update it after every race that matters.
- **Compliance table is empty or wrong** — check that your `TRAINING_PLAN`
  week `"start"` dates in `athlete_config.py` actually match your calendar;
  compliance matches activities to weeks by date range.
