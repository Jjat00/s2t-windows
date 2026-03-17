"""
Local STT engine using faster-whisper.

Works in batch mode: receives a complete utterance (as PCM16 bytes from VAD),
transcribes it synchronously, then calls on_transcript with is_final=True.

The engine is intentionally simple — no sliding window / LocalAgreement.
For this app, silero-vad handles utterance boundaries, so we only ever
transcribe complete utterances (no duplicate / overlap problem).
"""
from __future__ import annotations

import io
import logging
import queue
import threading
from typing import Callable

import numpy as np
from faster_whisper import WhisperModel

from src import config
from src.stt.base import STTEngine

logger = logging.getLogger(__name__)


class WhisperEngine(STTEngine):
    """
    Transcribes audio utterances using faster-whisper running locally.

    Audio is queued and processed in a background thread so that the calling
    thread (audio capture / VAD) is never blocked.
    """

    def __init__(self, on_transcript: Callable[[str, bool], None]) -> None:
        super().__init__(on_transcript)
        self._model: WhisperModel | None = None
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    # ── STTEngine interface ────────────────────────────────────────────────

    def start(self) -> None:
        logger.info(
            "Loading faster-whisper model '%s' (compute_type=%s)…",
            config.WHISPER_MODEL,
            config.WHISPER_COMPUTE_TYPE,
        )
        self._model = WhisperModel(
            config.WHISPER_MODEL,
            device="auto",
            compute_type=config.WHISPER_COMPUTE_TYPE,
        )
        logger.info("faster-whisper model loaded.")
        self._thread = threading.Thread(target=self._worker, daemon=True, name="whisper-worker")
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)  # sentinel
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("WhisperEngine stopped.")

    def transcribe(self, audio: bytes) -> str:
        """Synchronous transcription of a PCM16 audio segment."""
        if self._model is None:
            raise RuntimeError("WhisperEngine not started.")
        return self._do_transcribe(audio)

    def stream_audio(self, audio: bytes) -> None:
        """
        Enqueue a complete utterance for async transcription.
        Called by VADProcessor.on_speech_end.
        """
        self._queue.put(audio)

    # ── private ────────────────────────────────────────────────────────────

    def _worker(self) -> None:
        while True:
            audio = self._queue.get()
            if audio is None:
                break
            try:
                text = self._do_transcribe(audio)
                if text:
                    self.on_transcript(text, is_final=True)
            except Exception:
                logger.exception("Error during Whisper transcription")

    def _do_transcribe(self, audio: bytes) -> str:
        """Convert PCM16 bytes to float32 and run Whisper."""
        # faster-whisper accepts a numpy float32 array or a file path
        audio_np = (
            np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        )
        # Whisper wants 2-letter ISO codes; "auto" → None triggers auto-detect
        lang = None if config.LANGUAGE == "auto" else config.LANGUAGE[:2]
        segments, info = self._model.transcribe(
            audio_np,
            language=lang,
            beam_size=5,
            vad_filter=False,       # we already ran our own VAD
            condition_on_previous_text=False,
        )
        parts = [seg.text.strip() for seg in segments]
        text = " ".join(p for p in parts if p)
        if text:
            logger.debug("Whisper: %r (lang=%s)", text, info.language)
        return text
