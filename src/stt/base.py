"""
Abstract base class for all STT engines.

Each engine must implement:
- start()      : open connections / load models
- stop()       : release resources
- transcribe() : (for batch/local engines) synchronous transcription
- stream_audio(): (for streaming engines) feed audio chunks continuously

The engine calls self.on_transcript(text, is_final) as results arrive.
"""
from __future__ import annotations

import abc
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class STTEngine(abc.ABC):
    """
    Base class for speech-to-text engines.

    on_transcript(text, is_final) is called whenever a transcription result
    is available.  `is_final=True` means the result is committed and will not
    change; `is_final=False` means it is an interim/partial result.
    """

    def __init__(self, on_transcript: Callable[[str, bool], None]) -> None:
        self.on_transcript = on_transcript

    @abc.abstractmethod
    def start(self) -> None:
        """Initialise the engine (load model, open connection, etc.)."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Shut down the engine and release all resources."""

    def transcribe(self, audio: bytes) -> str:
        """
        Synchronously transcribe a complete audio segment (PCM16 mono 16kHz).
        Returns the transcribed text.  Default implementation raises NotImplementedError.
        Override in batch/local engines.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support batch transcription.")

    def stream_audio(self, chunk: bytes) -> None:
        """
        Feed a raw audio chunk into a streaming engine.
        Override in streaming (WebSocket-based) engines.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support streaming audio input.")

    def connect(self) -> None:
        """Open a per-session connection (e.g. WebSocket). No-op by default."""

    def disconnect(self) -> None:
        """Close the per-session connection. No-op by default."""
