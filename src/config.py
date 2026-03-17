"""
Central configuration — reads from environment / .env file.
All other modules import from here instead of reading env vars directly.

Works both when running from source and as a PyInstaller frozen .exe.
"""
import os
import shutil
import sys
from pathlib import Path
from dotenv import load_dotenv

# When frozen by PyInstaller the .exe lives in the install dir.
# When running from source the project root is one level above src/.
if getattr(sys, "frozen", False):
    _project_root = Path(sys.executable).parent
else:
    _project_root = Path(__file__).parent.parent

# First-run: copy .env.example → .env so the app starts without manual setup
_env_file = _project_root / ".env"
if not _env_file.exists():
    _example = _project_root / ".env.example"
    if _example.exists():
        shutil.copy(_example, _env_file)

load_dotenv(_env_file, override=False)

# ── STT Engine ──────────────────────────────────────────────────────────────
ENGINE: str = os.getenv("ENGINE", "whisper").lower()  # "deepgram" | "whisper"

# ── Deepgram ─────────────────────────────────────────────────────────────────
DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "")

# ── Whisper ──────────────────────────────────────────────────────────────────
WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "small")
WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# ── Audio ────────────────────────────────────────────────────────────────────
_device_raw = os.getenv("AUDIO_DEVICE_INDEX", "")
AUDIO_DEVICE_INDEX: int | None = int(_device_raw) if _device_raw.strip() else None

SAMPLE_RATE: int = 16000       # Hz — required by Whisper and Deepgram
CHANNELS: int = 1
CHUNK_SIZE: int = 1024         # frames per PyAudio read

# ── VAD / endpointing ────────────────────────────────────────────────────────
ENDPOINTING_MS: int = int(os.getenv("ENDPOINTING_MS", "700"))
VAD_THRESHOLD: float = 0.5     # silero-vad speech probability threshold

# ── Language ─────────────────────────────────────────────────────────────────
# BCP-47 tag or "auto".  Examples: es, es-419, en-US, fr, pt, de
# For Deepgram: used verbatim (auto → "multi")
# For Whisper:  uses the first 2 chars (auto → None for auto-detect)
LANGUAGE: str = os.getenv("LANGUAGE", "es")

# ── Hotkey ───────────────────────────────────────────────────────────────────
TOGGLE_HOTKEY: str = os.getenv("TOGGLE_HOTKEY", "<f9>")

# ── Interim results (Deepgram only) ─────────────────────────────────────────
# Type partial results in real-time and replace with final on completion.
# Set to false to only type confirmed final results (higher latency, more stable).
INTERIM_RESULTS: bool = os.getenv("INTERIM_RESULTS", "true").lower() == "true"

# ── Deduplication ────────────────────────────────────────────────────────────
# How many characters of previously typed text to check for overlap
DEDUP_LOOKBACK_CHARS: int = 120
# Minimum Levenshtein ratio to consider two strings a duplicate (0–1)
DEDUP_RATIO_THRESHOLD: float = 0.85
