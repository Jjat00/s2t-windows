"""
Voice Activity Detection usando silero-vad.

Usa el modelo ONNX bundleado en el paquete silero_vad —
no descarga nada de internet en tiempo de ejecución.

Emite:
  on_speech_end(audio_bytes)   → utterance completo listo para transcribir
  on_speech_start()            → inicio de voz detectado
"""
import logging
import time
from typing import Callable

import numpy as np
import torch
from silero_vad import load_silero_vad

from src import config

logger = logging.getLogger(__name__)


class VADProcessor:
    """
    Detecta pausas en audio PCM16 usando silero-vad ONNX.

    Parameters
    ----------
    on_speech_end   : callback(pcm16_bytes) al terminar una utterance
    on_speech_start : callback() al detectar inicio de voz
    endpointing_ms  : ms de silencio para cerrar la utterance
    threshold       : probabilidad mínima para considerar voz (0-1)
    sample_rate     : debe coincidir con la captura de audio (16000)
    """

    _WINDOW_SAMPLES = 512  # requerido por silero-vad a 16kHz

    def __init__(
        self,
        on_speech_end: Callable[[bytes], None],
        on_speech_start: Callable[[], None] | None = None,
        endpointing_ms: int = config.ENDPOINTING_MS,
        threshold: float = config.VAD_THRESHOLD,
        sample_rate: int = config.SAMPLE_RATE,
    ) -> None:
        self._on_speech_end   = on_speech_end
        self._on_speech_start = on_speech_start
        self._endpointing_ms  = endpointing_ms
        self._threshold       = threshold
        self._sample_rate     = sample_rate

        logger.info("Cargando silero-vad (ONNX, bundleado)...")
        self._model = load_silero_vad(onnx=True)
        logger.info("silero-vad listo.")

        self._speaking       = False
        self._speech_buffer: list[bytes] = []
        self._silence_start: float | None = None
        self._remainder      = b""

    def process(self, chunk: bytes) -> None:
        data = self._remainder + chunk
        self._remainder = b""

        window_bytes = self._WINDOW_SAMPLES * 2  # int16 = 2 bytes/sample
        offset = 0
        while offset + window_bytes <= len(data):
            self._process_window(data[offset : offset + window_bytes])
            offset += window_bytes
        self._remainder = data[offset:]

        # Verificar timeout de silencio
        if self._speaking and self._silence_start is not None:
            if (time.monotonic() - self._silence_start) * 1000 >= self._endpointing_ms:
                self._end_utterance()

    def reset(self) -> None:
        self._speaking = False
        self._speech_buffer.clear()
        self._silence_start = None
        self._remainder = b""
        self._model.reset_states()

    # ── private ────────────────────────────────────────────────────────────

    def _process_window(self, window: bytes) -> None:
        audio = np.frombuffer(window, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio)
        prob = float(self._model(tensor, self._sample_rate))

        if prob >= self._threshold:
            self._silence_start = None
            if not self._speaking:
                self._speaking = True
                logger.debug("Voz detectada (prob=%.2f)", prob)
                if self._on_speech_start:
                    self._on_speech_start()
            self._speech_buffer.append(window)
        else:
            if self._speaking:
                self._speech_buffer.append(window)
                if self._silence_start is None:
                    self._silence_start = time.monotonic()

    def _end_utterance(self) -> None:
        if not self._speech_buffer:
            return
        audio = b"".join(self._speech_buffer)
        self._speech_buffer.clear()
        self._speaking = False
        self._silence_start = None
        logger.debug("Fin de utterance — %d bytes", len(audio))
        self._on_speech_end(audio)
