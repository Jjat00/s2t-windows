"""
Voice Activity Detection using silero-vad.

Wraps incoming PCM16 audio chunks and emits speech segments:
- Buffers audio while speech is detected.
- Fires on_speech_end(audio_bytes) after silence >= endpointing_ms.
- Fires on_speech_start() when speech begins.

Usage:
    def handle_segment(audio: bytes):
        # audio is 16kHz mono PCM16 of a complete utterance
        transcribe(audio)

    vad = VADProcessor(on_speech_end=handle_segment)
    for chunk in audio_capture.stream():
        vad.process(chunk)
"""
import logging
import time
from collections import deque
from typing import Callable

import numpy as np
import torch

from src import config

logger = logging.getLogger(__name__)


def _load_silero() -> tuple:
    """Load silero-vad model and utilities."""
    model, utils = torch.hub.load(
        repo_or_dir="snakers4/silero-vad",
        model="silero_vad",
        force_reload=False,
        trust_repo=True,
    )
    (get_speech_timestamps, _, read_audio, *_) = utils
    return model, get_speech_timestamps


class VADProcessor:
    """
    Wraps silero-vad to detect speech start/end in a streaming PCM16 buffer.

    Parameters
    ----------
    on_speech_end   : called with (pcm16_bytes,) when an utterance ends
    on_speech_start : called with no args when speech begins
    endpointing_ms  : silence duration (ms) required to end an utterance
    threshold       : silero probability threshold (0-1)
    sample_rate     : must match audio capture (default 16000)
    """

    # silero-vad requires 512-sample windows at 16kHz
    _WINDOW_SAMPLES = 512

    def __init__(
        self,
        on_speech_end: Callable[[bytes], None],
        on_speech_start: Callable[[], None] | None = None,
        endpointing_ms: int = config.ENDPOINTING_MS,
        threshold: float = config.VAD_THRESHOLD,
        sample_rate: int = config.SAMPLE_RATE,
    ) -> None:
        self._on_speech_end = on_speech_end
        self._on_speech_start = on_speech_start
        self._endpointing_ms = endpointing_ms
        self._threshold = threshold
        self._sample_rate = sample_rate

        logger.info("Loading silero-vad model…")
        self._model, _ = _load_silero()
        self._model.eval()
        logger.info("silero-vad loaded.")

        # State
        self._speaking = False
        self._speech_buffer: list[bytes] = []  # accumulates speech audio
        self._silence_start: float | None = None  # wall clock

        # Leftover bytes that don't fill a full window
        self._remainder = b""

    def process(self, chunk: bytes) -> None:
        """Feed a raw PCM16 chunk (arbitrary size) into the VAD pipeline."""
        data = self._remainder + chunk
        self._remainder = b""

        window_bytes = self._WINDOW_SAMPLES * 2  # int16 = 2 bytes/sample

        offset = 0
        while offset + window_bytes <= len(data):
            window = data[offset : offset + window_bytes]
            offset += window_bytes
            self._process_window(window)

        # Keep any trailing bytes for next call
        self._remainder = data[offset:]

        # Check if silence duration has exceeded threshold
        if self._speaking and self._silence_start is not None:
            silence_ms = (time.monotonic() - self._silence_start) * 1000
            if silence_ms >= self._endpointing_ms:
                self._end_utterance()

    def reset(self) -> None:
        """Discard any buffered speech (e.g. when stopping recording)."""
        self._speaking = False
        self._speech_buffer.clear()
        self._silence_start = None
        self._remainder = b""
        self._model.reset_states()

    # ── private ────────────────────────────────────────────────────────────

    def _process_window(self, window: bytes) -> None:
        # Convert PCM16 bytes to float32 tensor [-1, 1]
        audio_np = np.frombuffer(window, dtype=np.int16).astype(np.float32) / 32768.0
        tensor = torch.from_numpy(audio_np)

        with torch.no_grad():
            prob = self._model(tensor, self._sample_rate).item()

        is_speech = prob >= self._threshold

        if is_speech:
            self._silence_start = None
            if not self._speaking:
                self._speaking = True
                logger.debug("Speech start detected (prob=%.2f)", prob)
                if self._on_speech_start:
                    self._on_speech_start()
            self._speech_buffer.append(window)
        else:
            if self._speaking:
                # Still accumulate audio during short silences (within endpointing window)
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
        logger.debug("Speech end — %d bytes of audio", len(audio))
        self._on_speech_end(audio)
