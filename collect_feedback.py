"""
Collects voice notes from Telegram Saved Messages, transcribes them with
faster-whisper, and drops them in feedback/pending.jsonl so the
running-coach skill can fold them into the weekly Obsidian log.

Usage:
    python collect_feedback.py --login    -> initial authentication (one-time, interactive)
    python collect_feedback.py            -> fetches what's new and transcribes it
    python collect_feedback.py --dry-run  -> shows what would be fetched, without transcribing or writing

State:
    feedback/state.json      last processed message_id (to avoid repeats)
    feedback/audios/*.ogg    original audio files, always kept
    feedback/pending.jsonl   append-only queue consumed by the skill
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ctranslate2 on Windows needs CUDA 12's cuBLAS/cuDNN. The nvidia-*-cu12
# wheels bundle them, but ctranslate2 resolves the DLL on its own and
# os.add_dll_directory() isn't enough: they need to be on the process PATH
# BEFORE the module is imported.
if sys.platform == "win32":
    _dirs = [
        str(Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / sub / "bin")
        for sub in ("cublas", "cudnn", "cuda_nvrtc")
    ]
    _dirs = [d for d in _dirs if Path(d).is_dir()]
    if _dirs:
        os.environ["PATH"] = os.pathsep.join(_dirs) + os.pathsep + os.environ["PATH"]

from dotenv import load_dotenv
from telethon.sync import TelegramClient

BASE = Path(__file__).parent
FEEDBACK = BASE / "feedback"
AUDIOS = FEEDBACK / "audios"
PENDING = FEEDBACK / "pending.jsonl"
STATE = FEEDBACK / "state.json"
SESSION = FEEDBACK / "telegram"          # Telethon appends .session

MODEL = os.environ.get("WHISPER_MODEL", "medium")
COMPUTE = "int8_float16"
DEVICE = "cuda"

# Vocabulary passed to Whisper as a context hint (improves transcription of
# running jargon and injury/muscle names). Written in Spanish because it's
# tuned for Spanish-language voice notes — override with WHISPER_PROMPT in
# .env to match your own language and vocabulary (injuries you're carrying,
# session names you use, etc.), entirely up to you.
PROMPT = os.environ.get("WHISPER_PROMPT") or (
    "Entrenamiento de running. Ritmo, pace, kilometros, series, intervalos, "
    "tempo, fondo, trote regenerativo, umbral, pulsaciones, zancada, cadencia."
)

# Safety cap: if it's never been run before, don't pull the entire Saved
# Messages history at once. The first run only looks at the last N messages.
FIRST_RUN_LIMIT = 20


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8-sig"))
    return {"last_id": 0}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def client_() -> TelegramClient:
    load_dotenv(BASE / ".env")
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        print("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in .env")
        raise SystemExit(1)
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(SESSION), int(api_id), api_hash)


def login() -> int:
    """Initial authentication. Prompts for phone number and code on the console."""
    print("Telegram authentication (one-time only).")
    print("The code arrives INSIDE Telegram, not via SMS.\n")
    with client_() as cli:
        me = cli.get_me()
        print(f"\nDone. Logged in as: {me.first_name} (@{me.username or 'no username'})")
        print(f"Session saved to: {SESSION}.session")
        print("That file is a credential for your account: don't share it or commit it.")
    return 0


def load_model():
    from faster_whisper import WhisperModel

    print(f"Loading {MODEL} on {DEVICE} ({COMPUTE})...")
    t0 = time.perf_counter()
    m = WhisperModel(MODEL, device=DEVICE, compute_type=COMPUTE)
    print(f"Model loaded in {time.perf_counter() - t0:.1f}s")
    return m


def transcribe(model, path: Path) -> str:
    segments, _ = model.transcribe(
        str(path),
        language="es",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        initial_prompt=PROMPT,
    )
    return " ".join(s.text.strip() for s in segments).strip()


def collect(dry_run: bool = False) -> int:
    AUDIOS.mkdir(parents=True, exist_ok=True)
    state = load_state()
    last_id = state.get("last_id", 0)

    with client_() as cli:
        if not cli.is_user_authorized():
            print("No valid session. Run this first:")
            print("    python collect_feedback.py --login")
            return 1

        kwargs = {"min_id": last_id} if last_id else {"limit": FIRST_RUN_LIMIT}
        if not last_id:
            print(f"First run: checking the last {FIRST_RUN_LIMIT} messages.")

        # 'me' is Saved Messages. No other chats are ever read.
        messages = [m for m in cli.iter_messages("me", **kwargs) if m.voice or m.audio]
        messages.reverse()  # chronological order

        if not messages:
            print("No new voice notes.")
            return 0

        print(f"New voice notes: {len(messages)}")
        if dry_run:
            for m in messages:
                dur = getattr(m.voice or m.audio, "duration", "?") if (m.voice or m.audio) else "?"
                print(f"  id={m.id}  {m.date.astimezone():%Y-%m-%d %H:%M}  {dur}s")
            return 0

        model = load_model()
        new_last_id = last_id

        with PENDING.open("a", encoding="utf-8") as queue:
            for m in messages:
                ts_local = m.date.astimezone()
                name = f"{ts_local:%Y%m%dT%H%M%S}_{m.id}.ogg"
                dest = AUDIOS / name

                if not dest.exists():
                    cli.download_media(m, file=str(dest))

                print(f"\n[{m.id}] {ts_local:%Y-%m-%d %H:%M}  -> {name}")
                try:
                    text = transcribe(model, dest)
                    print(f"  {text}")
                except Exception as exc:  # the audio is already safe on disk
                    text = None
                    print(f"  ERROR transcribing: {exc}")

                queue.write(json.dumps({
                    "ts": ts_local.isoformat(),
                    "message_id": m.id,
                    "audio": str(dest.relative_to(BASE)).replace("\\", "/"),
                    "text": text,
                    "activity_id": None,
                    "consumed": False,
                    "rejected": False,
                }, ensure_ascii=False) + "\n")
                queue.flush()

                # Save state after every message: if it's interrupted mid-batch,
                # the next run won't re-process (and duplicate) what's already written.
                new_last_id = max(new_last_id, m.id)
                state["last_id"] = new_last_id
                state["last_run"] = datetime.now(timezone.utc).isoformat()
                save_state(state)
        print(f"\nDone. {len(messages)} entries added to {PENDING.name}")

    return 0


def main() -> int:
    if "--login" in sys.argv:
        return login()
    return collect(dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
