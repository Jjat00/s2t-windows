"""
Voice Activity Detection using silero-vad ONNX via onnxruntime.

Pure numpy/onnxruntime — no PyTorch required.
The ONNX file is bundled inside the silero_vad package (and into the installer).

Emits:
  on_speech_end(audio_bytes)  -> complete utterance ready for transcription
  on_speech_start()           -> speech start detected
"""
import logging
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import onnxruntime as ort

from src import config

logger = logging.getLogger(__name__)


def _find_onnx_path() -> str:
    """Locate silero_vad.onnx whether frozen (PyInstaller) or running from source."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        candidates = list(base.rglob("silero_vad.onnx"))
        if candidates:
            return str(candidates[0])
        raise FileNotFoundError("silero_vad.onnx not found in frozen bundle")
    # Source: use the package's data directory
    try:
        from importlib.resources import files
        return str(files("silero_vad").joinpath("data").joinpath("silero_vad.onnx"))
    except Exception:
        import silero_vad as _sv
        return str(Path(_sv.__file__).parent / "data" / "silero_vad.onnx")


class _OnnxVAD:
    """
    Minimal silero-vad ONNX wrapper using pure numpy (no torch).
    Replicates the OnnxWrapper logic from silero_vad/utils_vad.py.
    """
    _CONTEXT_SIZE = 64  # audio context prepended at 16 kHz

    def __init__(self, model_path: str) -> None:
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = ort.InferenceSession(
            model_path,
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )
        self.reset_states()

    def reset_states(self) -> None:
        self._state   = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._CONTEXT_SIZE), dtype=np.float32)

    def __call__(self, audio: np.ndarray, sr: int) -> float:
        """audio: float32 array of 512 samples at 16 kHz. Returns speech probability."""
        x = audio.reshape(1, -1)                             # (1, 512)
        x = np.concatenate([self._context, x], axis=1)      # (1, 576)
        ort_out, self._state = self.session.run(
            None,
            {"input": x, "state": self._state, "sr": np.array(sr, dtype=np.int64)},
        )
        self._context = x[:, -self._CONTEXT_SIZE:]           # keep last 64 samples
        return float(ort_out.flatten()[0])


class VADProcessor:
    """
    Detects speech boundaries in streaming PCM16 audio.

    Parameters
    ----------
    on_speech_end   : callback(pcm16_bytes) on utterance complete
    on_speech_start : optional callback() on speech start
    endpointing_ms  : silence ms before closing an utterance
    threshold       : minimum speech probability (0-1)
    sample_rate     : must match audio capture (16000)
    """

    _WINDOW_SAMPLES = 512  # required by silero-vad at 16 kHz

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

        logger.info("Loading silero-vad ONNX model...")
        self._model = _OnnxVAD(_find_onnx_path())
        logger.info("silero-vad ready.")

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
        prob  = self._model(audio, self._sample_rate)

        if prob >= self._threshold:
            self._silence_start = None
            if not self._speaking:
                self._speaking = True
                logger.debug("Speech detected (prob=%.2f)", prob)
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
        logger.debug("Utterance end — %d bytes", len(audio))
        self._on_speech_end(audio)
