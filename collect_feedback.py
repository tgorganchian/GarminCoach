"""
Recolecta las notas de voz de Mensajes Guardados de Telegram, las transcribe
con faster-whisper y las deja en feedback/pending.jsonl para que la skill
running-coach las vuelque a la bitacora semanal de Obsidian.

Uso:
    python collect_feedback.py --login    -> autenticacion inicial (una sola vez, interactivo)
    python collect_feedback.py            -> baja lo nuevo y transcribe
    python collect_feedback.py --dry-run  -> muestra que bajaria, sin transcribir ni escribir

Estado:
    feedback/state.json      ultimo message_id procesado (para no repetir)
    feedback/audios/*.ogg    audios originales, se conservan siempre
    feedback/pending.jsonl   cola append-only que consume la skill
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ctranslate2 en Windows necesita cuBLAS/cuDNN de CUDA 12. Los wheels nvidia-*-cu12
# las traen, pero ctranslate2 resuelve la DLL por su cuenta y os.add_dll_directory()
# no le alcanza: hay que meterlas en el PATH del proceso ANTES de importar el modulo.
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
SESSION = FEEDBACK / "telegram"          # Telethon le agrega .session

MODELO = os.environ.get("WHISPER_MODEL", "medium")
COMPUTE = "int8_float16"
DEVICE = "cuda"

PROMPT = (
    "Entrenamiento de running. Ritmo, pace, kilometros, series, tempo, fondo, "
    "trote regenerativo, umbral, pulsaciones, rodilla, gemelos, isquiotibiales, "
    "cintilla iliotibial, zancada, cadencia."
)

# Tope de seguridad: si nunca se corrio, no bajar todo el historial de Mensajes
# Guardados de golpe. La primera corrida mira solo los ultimos N mensajes.
PRIMERA_CORRIDA_LIMITE = 20


def cargar_estado() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"ultimo_id": 0}


def guardar_estado(estado: dict) -> None:
    STATE.write_text(json.dumps(estado, indent=2), encoding="utf-8")


def cliente() -> TelegramClient:
    load_dotenv(BASE / ".env")
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")
    if not api_id or not api_hash:
        print("Faltan TELEGRAM_API_ID / TELEGRAM_API_HASH en .env")
        raise SystemExit(1)
    FEEDBACK.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(SESSION), int(api_id), api_hash)


def login() -> int:
    """Autenticacion inicial. Pide telefono y codigo por consola."""
    print("Autenticacion de Telegram (solo la primera vez).")
    print("El codigo llega DENTRO de Telegram, no por SMS.\n")
    with cliente() as cli:
        yo = cli.get_me()
        print(f"\nListo. Sesion iniciada como: {yo.first_name} (@{yo.username or 'sin usuario'})")
        print(f"Sesion guardada en: {SESSION}.session")
        print("Ese archivo es una credencial de tu cuenta: no lo compartas ni lo subas a la Vault.")
    return 0


def cargar_modelo():
    from faster_whisper import WhisperModel

    print(f"Cargando {MODELO} en {DEVICE} ({COMPUTE})...")
    t0 = time.perf_counter()
    m = WhisperModel(MODELO, device=DEVICE, compute_type=COMPUTE)
    print(f"Modelo cargado en {time.perf_counter() - t0:.1f}s")
    return m


def transcribir(modelo, ruta: Path) -> str:
    segmentos, _ = modelo.transcribe(
        str(ruta),
        language="es",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
        initial_prompt=PROMPT,
    )
    return " ".join(s.text.strip() for s in segmentos).strip()


def recolectar(dry_run: bool = False) -> int:
    AUDIOS.mkdir(parents=True, exist_ok=True)
    estado = cargar_estado()
    ultimo_id = estado.get("ultimo_id", 0)

    with cliente() as cli:
        if not cli.is_user_authorized():
            print("No hay sesion valida. Corré primero:")
            print("    python collect_feedback.py --login")
            return 1

        kwargs = {"min_id": ultimo_id} if ultimo_id else {"limit": PRIMERA_CORRIDA_LIMITE}
        if not ultimo_id:
            print(f"Primera corrida: reviso los ultimos {PRIMERA_CORRIDA_LIMITE} mensajes.")

        # 'me' es Mensajes Guardados. Nunca se leen otros chats.
        mensajes = [m for m in cli.iter_messages("me", **kwargs) if m.voice or m.audio]
        mensajes.reverse()  # cronologico

        if not mensajes:
            print("No hay notas de voz nuevas.")
            return 0

        print(f"Notas de voz nuevas: {len(mensajes)}")
        if dry_run:
            for m in mensajes:
                dur = getattr(m.voice or m.audio, "duration", "?") if (m.voice or m.audio) else "?"
                print(f"  id={m.id}  {m.date.astimezone():%Y-%m-%d %H:%M}  {dur}s")
            return 0

        modelo = cargar_modelo()
        nuevo_ultimo = ultimo_id

        with PENDING.open("a", encoding="utf-8") as cola:
            for m in mensajes:
                ts_local = m.date.astimezone()
                nombre = f"{ts_local:%Y%m%dT%H%M%S}_{m.id}.ogg"
                destino = AUDIOS / nombre

                if not destino.exists():
                    cli.download_media(m, file=str(destino))

                print(f"\n[{m.id}] {ts_local:%Y-%m-%d %H:%M}  -> {nombre}")
                try:
                    texto = transcribir(modelo, destino)
                    print(f"  {texto}")
                except Exception as exc:  # el audio ya esta a salvo en disco
                    texto = None
                    print(f"  ERROR al transcribir: {exc}")

                cola.write(json.dumps({
                    "ts": ts_local.isoformat(),
                    "message_id": m.id,
                    "audio": str(destino.relative_to(BASE)).replace("\\", "/"),
                    "text": texto,
                    "activity_id": None,
                    "consumed": False,
                    "rechazado": False,
                }, ensure_ascii=False) + "\n")
                cola.flush()

                # Guardar estado por mensaje: si se corta a mitad de lote, el
                # proximo run no re-procesa (y duplica en pending.jsonl) lo ya escrito.
                nuevo_ultimo = max(nuevo_ultimo, m.id)
                estado["ultimo_id"] = nuevo_ultimo
                estado["ultima_corrida"] = datetime.now(timezone.utc).isoformat()
                guardar_estado(estado)
        print(f"\nListo. {len(mensajes)} entradas agregadas a {PENDING.name}")

    return 0


def main() -> int:
    if "--login" in sys.argv:
        return login()
    return recolectar(dry_run="--dry-run" in sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
