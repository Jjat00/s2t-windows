"""
Configuración centralizada — lee desde .env.

Funciona tanto corriendo desde fuente como como .exe de PyInstaller.
"""
import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Rutas base ────────────────────────────────────────────────────────────────
# Cuando está frozen (PyInstaller), el .exe está en el directorio de instalación.
# En desarrollo, la raíz del proyecto es un nivel arriba de src/.
if getattr(sys, "frozen", False):
    _project_root = Path(sys.executable).parent
else:
    _project_root = Path(__file__).parent.parent

# Primera ejecución: copiar .env.example → .env si no existe
_env_file = _project_root / ".env"
if not _env_file.exists():
    _example = _project_root / ".env.example"
    if _example.exists():
        shutil.copy(_example, _env_file)

load_dotenv(_env_file, override=False)

# ── STT Engine ────────────────────────────────────────────────────────────────
# "auto"     → Deepgram si hay API key configurada, Whisper si no
# "deepgram" → fuerza Deepgram (requiere DEEPGRAM_API_KEY)
# "whisper"  → fuerza Whisper local
ENGINE: str = os.getenv("ENGINE", "auto").lower()

# ── Deepgram ──────────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL: str        = os.getenv("WHISPER_MODEL", "small")
WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# Directorio donde están (o se descargarán) los modelos de Whisper.
# En producción apunta a la carpeta 'models/' junto al .exe.
# En desarrollo apunta a 'assets/models/'.
if getattr(sys, "frozen", False):
    WHISPER_MODEL_DIR: str = str(_project_root / "models")
else:
    WHISPER_MODEL_DIR: str = str(_project_root / "assets" / "models")

# ── Audio ─────────────────────────────────────────────────────────────────────
_device_raw = os.getenv("AUDIO_DEVICE_INDEX", "")
AUDIO_DEVICE_INDEX: int | None = int(_device_raw) if _device_raw.strip() else None

SAMPLE_RATE: int = 16000
CHANNELS: int    = 1
CHUNK_SIZE: int  = 1024

# ── VAD / endpointing ─────────────────────────────────────────────────────────
ENDPOINTING_MS: int  = int(os.getenv("ENDPOINTING_MS", "500"))
VAD_THRESHOLD: float = 0.5

# ── Idioma ────────────────────────────────────────────────────────────────────
LANGUAGE: str = os.getenv("LANGUAGE", "multi")

# ── Push-to-talk key ──────────────────────────────────────────────────────────
# pynput Key name: ctrl_r, ctrl_l, alt_r, caps_lock, f13 ...
PTT_KEY: str = os.getenv("PTT_KEY", "f9")

# ── Resultados parciales (solo Deepgram) ──────────────────────────────────────
INTERIM_RESULTS: bool = os.getenv("INTERIM_RESULTS", "true").lower() == "true"

# ── Deduplicación ─────────────────────────────────────────────────────────────
DEDUP_LOOKBACK_CHARS: int  = 120
DEDUP_RATIO_THRESHOLD: float = 0.85
