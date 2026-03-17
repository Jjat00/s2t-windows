"""
Pre-descarga el modelo Whisper a assets/models/ para incluirlo en el build.
Corre esto UNA VEZ antes de hacer el build del instalador.

Uso:
    uv run python scripts/download_models.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MODELS_DIR = ROOT / "assets" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Lee el modelo configurado en .env (default: small)
from dotenv import load_dotenv
import os
load_dotenv(ROOT / ".env")
model_name = os.getenv("WHISPER_MODEL", "small")
compute    = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

print(f"Descargando modelo faster-whisper '{model_name}' en {MODELS_DIR} ...")
print("(puede tardar varios minutos la primera vez)\n")

from faster_whisper import WhisperModel
WhisperModel(model_name, device="cpu", compute_type=compute,
             download_root=str(MODELS_DIR))

# Verificar que quedó descargado
model_dirs = list(MODELS_DIR.rglob("model.bin"))
if model_dirs:
    size_mb = model_dirs[0].stat().st_size // (1024 * 1024)
    print(f"\nOK: modelo descargado ({size_mb} MB) en:\n  {model_dirs[0].parent}")
else:
    print("ERROR: no se encontro model.bin despues de la descarga")
    sys.exit(1)
