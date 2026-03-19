# S2T — Speech to Text Desktop App

Aplicación de escritorio para Windows que captura audio del micrófono en tiempo real, lo transcribe mediante IA y escribe el texto donde esté el cursor. Sin copiar, sin pegar — habla y el texto aparece directamente en cualquier app.

---

## Características

- **Push-to-talk** — mantén **F9** presionado para grabar, suelta para escribir
- **Preview en tiempo real** — las palabras aparecen en el HUD mientras hablas, sin tocar el documento
- **Resultado limpio** — al soltar F9, Deepgram escribe la versión final corregida (sin residuos ni palabras incompletas)
- **Escribe donde esté el cursor** — funciona en cualquier aplicación (VS Code, Word, Notion, Chrome, etc.)
- **Bilingüe** — español + inglés simultáneo con Deepgram Nova-3 (`LANGUAGE=multi`)
- **Dos motores** — Deepgram (cloud, baja latencia) o faster-whisper (local, sin internet)
- **Sin duplicados** — deduplicación por similitud para evitar frases repetidas
- **HUD flotante** — panel estilo Vercel con timer, preview de transcripción, visualizador de voz y botón Stop
- **System tray** — vive en la bandeja del sistema, sin ventanas en el escritorio

---

## Tecnologías

| Componente | Tecnología | Por qué |
|---|---|---|
| **Lenguaje** | Python 3.12 | Mejor ecosistema para audio e IA |
| **Gestión de deps** | [uv](https://github.com/astral-sh/uv) | Instalación rápida, versiones exactas |
| **Captura de audio** | PyAudio | Streaming de micrófono en tiempo real |
| **STT cloud** | [Deepgram Nova-3](https://deepgram.com) | WebSocket nativo, baja latencia, multilingüe |
| **STT local** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper 4× más rápido, funciona offline |
| **VAD** | [silero-vad](https://github.com/snakers4/silero-vad) ONNX | Detección de pausas (modo local, sin PyTorch) |
| **Teclado** | pynput | Escribe en la ventana activa, soporta Unicode |
| **System tray** | pystray + Pillow | Icono en bandeja sin frameworks pesados |
| **UI** | tkinter | HUD flotante y diálogo de configuración |

---

## Requisitos

- Windows 10/11
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) instalado
- Micrófono
- Cuenta en [Deepgram](https://console.deepgram.com) si usas el motor cloud (tiene free tier)

---

## Instalación

```bash
# 1. Clona el repositorio
git clone git@github.com:Jjat00/s2t-windows.git
cd s2t-windows

# 2. Instala las dependencias (crea el .venv automáticamente)
uv sync

# 3. Crea tu archivo de configuración
cp .env.example .env
```

---

## Configuración

Edita el archivo `.env` con tus valores:

```env
# Motor: "auto" (Deepgram si hay API key, Whisper si no), "deepgram" o "whisper"
ENGINE=auto

# API Key de Deepgram — opcional, solo necesaria si ENGINE=deepgram o auto con key
# Obtén la tuya en https://console.deepgram.com
DEEPGRAM_API_KEY=

# Idioma de transcripción
# multi  = español + inglés simultáneo (recomendado con Deepgram Nova-3)
# es     = solo español
# en-US  = solo inglés
# auto   = igual que multi (Deepgram) o auto-detect (Whisper)
LANGUAGE=multi

# Tamaño del modelo Whisper (solo si ENGINE=whisper)
# tiny | base | small | medium | large-v3
WHISPER_MODEL=small

# Tipo de cómputo para Whisper
# int8 (CPU) | float16 (GPU) | float32
WHISPER_COMPUTE_TYPE=int8

# Índice del micrófono (dejar vacío para el predeterminado)
AUDIO_DEVICE_INDEX=

# Silencio necesario para cerrar una utterance (ms)
# 500 = natural, reduce cortes de palabras al final
ENDPOINTING_MS=500

# Tecla push-to-talk: mantener presionada para grabar
# f9 = F9 (recomendado — sin conflictos con atajos del sistema)
PTT_KEY=f9
```

### Motores disponibles

#### Deepgram Nova-3 (recomendado)
- Requiere internet y API key
- Baja latencia, precisión excelente en español + inglés simultáneo
- Preview en tiempo real en el HUD, resultado final limpio al soltar F9
- Precio: ~$0.004/min (tiene free tier generoso)

#### faster-whisper (local)
- Sin internet, sin API key, sin costo
- Requiere GPU (NVIDIA) para baja latencia con modelos grandes
- En CPU funciona bien con el modelo `small` (~1-2s de latencia)
- El modelo se descarga automáticamente en el primer uso (~460 MB para `small`)

| Modelo | VRAM | Precisión | Velocidad CPU |
|---|---|---|---|
| tiny | <1 GB | Básica | Muy rápido |
| small | ~1 GB | Buena | Rápido |
| medium | ~3 GB | Muy buena | Lento |
| large-v3 | ~6 GB | Excelente | Muy lento |

---

## Uso

```bash
uv run python src/main.py
```

1. Aparece un icono en la **bandeja del sistema**
2. **Mantén F9 presionado** para grabar — el HUD aparece con el preview de lo que dices
3. **Suelta F9** — el texto final se escribe donde esté el cursor
4. Click derecho en el icono de la bandeja → **Settings** para cambiar idioma, motor y más

---

## Estructura del proyecto

```
s2t/
├── src/
│   ├── main.py              # Orquestador principal y punto de entrada
│   ├── config.py            # Configuración centralizada (lee .env)
│   ├── audio_capture.py     # Captura de micrófono con PyAudio
│   ├── vad.py               # VAD con silero-vad ONNX (sin PyTorch)
│   ├── text_processor.py    # Deduplicación y limpieza de texto
│   ├── keyboard_emitter.py  # Escritura de texto con pynput
│   ├── hotkeys.py           # Push-to-talk (F9 por defecto)
│   ├── tray_app.py          # Icono en bandeja del sistema
│   ├── stt/
│   │   ├── base.py              # Interfaz abstracta STTEngine
│   │   ├── deepgram_engine.py   # Motor Deepgram Nova-3 (WebSocket)
│   │   └── whisper_engine.py    # Motor faster-whisper (local)
│   └── ui/
│       ├── recording_window.py  # HUD flotante (timer + preview + waveform)
│       └── settings_window.py   # Diálogo de configuración
├── assets/
│   └── icon.ico             # Icono de la bandeja
├── scripts/
│   ├── build.py             # Build completo (icono + modelo + PyInstaller + Inno Setup)
│   ├── download_models.py   # Pre-descarga modelo Whisper para el instalador
│   └── generate_icon.py     # Regenera el icono
├── installer/
│   └── setup.iss            # Script de Inno Setup 6
├── s2t.spec                 # Configuración de PyInstaller
├── .env.example             # Plantilla de configuración
├── pyproject.toml           # Definición del proyecto
└── uv.lock                  # Versiones exactas de dependencias
```
