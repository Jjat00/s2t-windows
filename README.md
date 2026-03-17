# S2T — Speech to Text Desktop App

Aplicación de escritorio para Windows que captura audio del micrófono en tiempo real, lo transcribe mediante IA y escribe el texto donde esté el cursor. Sin copiar, sin pegar — habla y el texto aparece directamente en cualquier app.

---

## Características

- **Dictado fluido en tiempo real** — las palabras aparecen mientras hablas (~100ms con Deepgram), sin esperar a terminar la frase
- **Escribe donde esté el cursor** — funciona en cualquier aplicación (VS Code, Word, Notion, Chrome, etc.)
- **Multiidioma** — español, inglés, francés, portugués y más, configurable en `.env`
- **Dos motores** — Deepgram (cloud, ~100ms) o faster-whisper (local, sin internet)
- **Sin duplicados** — deduplicación por similitud para evitar frases repetidas
- **Sin parpadeo** — los resultados parciales se extienden palabra por palabra, sin borrar y reescribir
- **Hotkey global** — F9 para iniciar/detener sin salir de la app donde estés
- **HUD flotante** — panel estilo Vercel con timer, visualizador de voz y botón de stop
- **System tray** — vive en la bandeja del sistema, sin ventanas en el escritorio

---

## Tecnologías

| Componente | Tecnología | Por qué |
|---|---|---|
| **Lenguaje** | Python 3.12 | Mejor ecosistema para audio e IA |
| **Gestión de deps** | [uv](https://github.com/astral-sh/uv) | Instalación rápida, versiones exactas |
| **Captura de audio** | PyAudio | Streaming de micrófono en tiempo real |
| **STT cloud** | [Deepgram Nova-2](https://deepgram.com) | WebSocket nativo, ~300ms, VAD integrado |
| **STT local** | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Whisper 4× más rápido, funciona offline |
| **VAD** | [silero-vad](https://github.com/snakers4/silero-vad) | Detección de pausas precisa (modo local) |
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
# Motor de transcripción: "deepgram" (cloud) o "whisper" (local)
ENGINE=deepgram

# API Key de Deepgram (solo necesaria si ENGINE=deepgram)
# Obtén la tuya en https://console.deepgram.com
DEEPGRAM_API_KEY=tu_api_key_aqui

# Idioma de transcripción (BCP-47 o "auto")
# Ejemplos: es, es-419, en-US, fr, pt, de
LANGUAGE=es

# Tamaño del modelo Whisper (solo si ENGINE=whisper)
# tiny | base | small | medium | large-v3
# Más grande = más preciso pero más lento y más RAM/VRAM
WHISPER_MODEL=small

# Tipo de cómputo para Whisper
# int8 (CPU, rápido) | float16 (GPU) | float32
WHISPER_COMPUTE_TYPE=int8

# Índice del micrófono (dejar vacío para el predeterminado)
AUDIO_DEVICE_INDEX=

# Silencio necesario para considerar que terminaste de hablar (ms)
ENDPOINTING_MS=300

# Mostrar palabras parciales mientras hablas (true) o solo al terminar la frase (false)
# true  → texto aparece en ~100ms, fluido, recomendado con Deepgram
# false → texto aparece solo al terminar la frase, más estable (recomendado con Whisper)
INTERIM_RESULTS=true

# Tecla global para iniciar/detener grabación
TOGGLE_HOTKEY=<f9>
```

### Motores disponibles

#### Deepgram (recomendado)
- Requiere internet y API key
- Latencia ~300ms, precisión excelente
- VAD y detección de pausas integrados
- Precio: ~$0.004/min (tiene free tier generoso)

#### faster-whisper (local)
- Sin internet, sin API key, sin costo
- Requiere GPU (NVIDIA) para baja latencia con modelos grandes
- En CPU funciona bien con el modelo `small` (~1-2s de latencia)
- El modelo se descarga automáticamente en el primer uso (~460 MB para `small`)
- Recomendado: `INTERIM_RESULTS=false` y `ENDPOINTING_MS=700`

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

- Aparece un icono en la **bandeja del sistema**
- Presiona **F9** para iniciar la grabación
- Habla — el texto se escribe donde esté el cursor
- Presiona **F9** de nuevo o el botón **Stop** del HUD para detener
- Click derecho en el icono de la bandeja para acceder a **Settings** y **Exit**

### Configuración desde la UI

Click derecho en el icono → **Settings** para cambiar idioma, motor, micrófono y más sin editar el `.env` manualmente. Los cambios aplican al reiniciar.

---

## Estructura del proyecto

```
s2t/
├── src/
│   ├── main.py              # Orquestador principal y punto de entrada
│   ├── config.py            # Configuración centralizada (lee .env)
│   ├── audio_capture.py     # Captura de micrófono con PyAudio
│   ├── vad.py               # Detección de voz con silero-vad
│   ├── text_processor.py    # Deduplicación y limpieza de texto
│   ├── keyboard_emitter.py  # Escritura de texto con pynput
│   ├── hotkeys.py           # Hotkey global (F9)
│   ├── tray_app.py          # Icono en bandeja del sistema
│   ├── stt/
│   │   ├── base.py          # Interfaz abstracta STTEngine
│   │   ├── deepgram_engine.py  # Motor Deepgram (WebSocket)
│   │   └── whisper_engine.py   # Motor faster-whisper (local)
│   └── ui/
│       ├── recording_window.py  # HUD flotante (timer + waveform + stop)
│       └── settings_window.py   # Diálogo de configuración
├── assets/
│   └── icon.ico             # Icono de la bandeja
├── scripts/
│   └── generate_icon.py     # Script para regenerar el icono
├── .env.example             # Plantilla de configuración
├── pyproject.toml           # Definición del proyecto
└── uv.lock                  # Versiones exactas de dependencias
```
