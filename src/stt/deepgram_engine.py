"""
Streaming STT engine using the Deepgram SDK v6 WebSocket API.

Lifecycle:
  start()      – validate config only (no connection)
  connect()    – open WebSocket for a recording session
  stream_audio – send audio chunks
  disconnect() – close WebSocket at end of recording session
  stop()       – alias for disconnect + cleanup

This way the connection is created fresh for each recording session,
avoiding the "no audio received within timeout" error.
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from deepgram import DeepgramClient
from deepgram.listen.v1.socket_client import EventType, V1SocketClient
from deepgram.listen.v1.types.listen_v1results import ListenV1Results

from src import config
from src.stt.base import STTEngine

logger = logging.getLogger(__name__)

_SENTINEL = None


class DeepgramEngine(STTEngine):
    """
    Per-session Deepgram WebSocket streaming engine.

    connect() opens the WebSocket; disconnect() closes it.
    A new connection is made for every recording session.
    """

    def __init__(self, on_transcript: Callable[[str, bool], None]) -> None:
        super().__init__(on_transcript)
        if not config.DEEPGRAM_API_KEY:
            raise ValueError(
                "DEEPGRAM_API_KEY is not set. "
                "Add it to your .env file or set the environment variable."
            )
        self._client = DeepgramClient(api_key=config.DEEPGRAM_API_KEY)
        self._audio_queue: queue.Queue[bytes | None] = queue.Queue(maxsize=400)
        self._ws_thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._stop_flag = threading.Event()

    # ── STTEngine lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        """Validate config. Connection is opened per-session via connect()."""
        logger.info("DeepgramEngine ready (connect() each session).")

    def stop(self) -> None:
        self.disconnect()

    # ── Per-session connection ─────────────────────────────────────────────

    def connect(self) -> None:
        """Open a fresh WebSocket connection for a new recording session."""
        # Drain any leftover audio from a previous session
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._stop_flag.clear()
        self._connected.clear()
        self._ws_thread = threading.Thread(
            target=self._ws_loop, daemon=True, name="deepgram-ws"
        )
        self._ws_thread.start()

        if not self._connected.wait(timeout=15):
            raise RuntimeError("Deepgram WebSocket did not connect within 15 seconds.")
        logger.info("DeepgramEngine connected.")

    def disconnect(self) -> None:
        """Close the WebSocket and wait for the background thread to finish."""
        if not self._ws_thread or not self._ws_thread.is_alive():
            return
        self._stop_flag.set()
        self._audio_queue.put(_SENTINEL)  # unblock the sender loop
        self._ws_thread.join(timeout=10)
        self._ws_thread = None
        logger.info("DeepgramEngine disconnected.")

    def stream_audio(self, chunk: bytes) -> None:
        """Thread-safe: enqueue audio for sending to Deepgram."""
        if not self._stop_flag.is_set():
            try:
                self._audio_queue.put_nowait(chunk)
            except queue.Full:
                pass  # drop rather than block

    # ── private ────────────────────────────────────────────────────────────

    def _ws_loop(self) -> None:
        # "auto" and "multi" both map to Deepgram's multilingual mode (es + en + more)
        lang = "multi" if config.LANGUAGE in ("auto", "multi") else config.LANGUAGE
        connect_params = dict(
            model="nova-3",
            language=lang,
            encoding="linear16",
            sample_rate=str(config.SAMPLE_RATE),
            channels=str(config.CHANNELS),
            interim_results="true" if config.INTERIM_RESULTS else "false",
            smart_format="true",
            endpointing=str(config.ENDPOINTING_MS),
        )
        try:
            with self._client.listen.v1.connect(**connect_params) as ws:
                self._connected.set()

                # Reader thread — iterates WebSocket messages concurrently
                reader = threading.Thread(
                    target=self._read_loop, args=(ws,), daemon=True, name="deepgram-reader"
                )
                reader.start()

                # Sender loop — drains ALL audio until sentinel.
                # Must NOT exit on stop_flag alone: audio captured just before
                # disconnect() would be lost, cutting off the last words.
                while True:
                    try:
                        chunk = self._audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if chunk is _SENTINEL:
                        break
                    try:
                        ws.send_media(chunk)
                    except Exception:
                        if not self._stop_flag.is_set():
                            logger.exception("Error sending audio to Deepgram")
                        break

                ws.send_close_stream()
                reader.join(timeout=5)

        except Exception:
            if not self._stop_flag.is_set():
                logger.exception("Deepgram WebSocket error")
            self._connected.set()  # unblock connect() on failure

    def _read_loop(self, ws: V1SocketClient) -> None:
        """Process ALL messages until Deepgram closes the connection.

        Do NOT break early on _stop_flag — we need to receive the final
        transcript that Deepgram sends after send_close_stream().
        """
        try:
            for msg in ws:
                if isinstance(msg, ListenV1Results):
                    self._handle_result(msg)
        except Exception:
            if not self._stop_flag.is_set():
                logger.exception("Error reading from Deepgram WebSocket")

    def _handle_result(self, result: ListenV1Results) -> None:
        try:
            text = result.channel.alternatives[0].transcript.strip()
        except (AttributeError, IndexError):
            return
        if not text:
            return
        is_final = bool(result.is_final)
        logger.debug("Deepgram: %r (final=%s)", text, is_final)
        self.on_transcript(text, is_final)
