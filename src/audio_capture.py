"""
Microphone capture using PyAudio.

Usage:
    with AudioCapture() as cap:
        for chunk in cap.stream():
            process(chunk)   # chunk is bytes (PCM16 mono 16kHz)
"""
import logging
import queue
import threading
from typing import Generator

import pyaudio

from src import config

logger = logging.getLogger(__name__)

PYAUDIO_FORMAT = pyaudio.paInt16  # 16-bit PCM


class AudioCapture:
    """Captures microphone audio as a continuous stream of PCM16 chunks."""

    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = config.SAMPLE_RATE,
        channels: int = config.CHANNELS,
        chunk_size: int = config.CHUNK_SIZE,
    ) -> None:
        self._device_index = device_index if device_index is not None else config.AUDIO_DEVICE_INDEX
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_size = chunk_size

        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._running = False

    # ── context manager ────────────────────────────────────────────────────

    def __enter__(self) -> "AudioCapture":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ── public ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._pa = pyaudio.PyAudio()
        self._stream = self._pa.open(
            format=PYAUDIO_FORMAT,
            channels=self._channels,
            rate=self._sample_rate,
            input=True,
            input_device_index=self._device_index,
            frames_per_buffer=self._chunk_size,
            stream_callback=self._callback,
        )
        self._running = True
        self._stream.start_stream()
        logger.info(
            "AudioCapture started: device=%s rate=%d channels=%d chunk=%d",
            self._device_index,
            self._sample_rate,
            self._channels,
            self._chunk_size,
        )

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._queue.put(None)  # sentinel to unblock stream()
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()
        logger.info("AudioCapture stopped.")

    def stream(self) -> Generator[bytes, None, None]:
        """Yields PCM16 byte chunks until stop() is called."""
        while True:
            chunk = self._queue.get()
            if chunk is None:
                break
            yield chunk

    # ── private ────────────────────────────────────────────────────────────

    def _callback(
        self,
        in_data: bytes,
        frame_count: int,
        time_info: dict,
        status: int,
    ) -> tuple[None, int]:
        if self._running:
            self._queue.put(in_data)
        return None, pyaudio.paContinue

    # ── utility ────────────────────────────────────────────────────────────

    @staticmethod
    def list_devices() -> list[dict]:
        """Return info dicts for all available input devices."""
        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({"index": i, "name": info["name"], "rate": int(info["defaultSampleRate"])})
        pa.terminate()
        return devices
