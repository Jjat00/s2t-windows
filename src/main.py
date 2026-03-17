"""
S2T — Speech-to-Text Desktop App
Entry point.

Flow:
  1. Load config from .env
  2. Create the STT engine (Deepgram or Whisper)
  3. On each recording session:
     - engine.connect() opens a fresh WebSocket (Deepgram) or does nothing (Whisper)
     - AudioCapture + VADProcessor stream audio
     - engine.disconnect() at end of session
  4. RecordingWindow shows elapsed time, waveform, and a Stop button
  5. System tray + F9 hotkey for start/stop toggle

Press F9 (or configured hotkey) to start/stop.
Right-click tray icon for menu.
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

import numpy as np

from src import config
from src.audio_capture import AudioCapture
from src.hotkeys import HotkeyManager
from src.keyboard_emitter import KeyboardEmitter
from src.text_processor import TextProcessor
from src.tray_app import TrayApp
from src.ui.recording_window import RecordingWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Engine factory ──────────────────────────────────────────────────────────

def _make_engine(on_transcript: Callable[[str, bool], None]):
    if config.ENGINE == "deepgram":
        from src.stt.deepgram_engine import DeepgramEngine
        return DeepgramEngine(on_transcript)
    else:
        from src.stt.whisper_engine import WhisperEngine
        return WhisperEngine(on_transcript)


# ── RMS helper ──────────────────────────────────────────────────────────────

def _rms(pcm16: bytes) -> float:
    """Return normalised RMS amplitude [0, 1] of a PCM16 chunk."""
    arr = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
    if len(arr) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(arr ** 2))) / 32768.0
    return min(1.0, rms * 6)  # scale up so quiet speech is visible


# ── App ─────────────────────────────────────────────────────────────────────

class S2TApp:
    def __init__(self) -> None:
        self._recording = False
        self._lock = threading.Lock()

        self._keyboard = KeyboardEmitter()
        self._text_proc = TextProcessor()
        self._engine = _make_engine(self._on_transcript)

        # Text currently on-screen as interim (not yet confirmed).
        # We only type the new suffix each update instead of rewriting everything.
        self._interim_typed: str = ""
        self._interim_lock = threading.Lock()
        self._capture: AudioCapture | None = None
        self._capture_thread: threading.Thread | None = None
        self._rec_window: RecordingWindow | None = None

        # VAD is only used with Whisper (Deepgram has built-in endpointing)
        self._vad = None
        if config.ENGINE != "deepgram":
            from src.vad import VADProcessor
            self._vad = VADProcessor(
                on_speech_end=self._engine.stream_audio,
                on_speech_start=self._on_speech_start,
            )

        self._tray = TrayApp(
            on_start=self.start_recording,
            on_stop=self.stop_recording,
            on_settings=self._open_settings,
            on_exit=self._exit,
        )
        self._hotkeys = HotkeyManager(on_toggle=self.toggle_recording)

    # ── public ────────────────────────────────────────────────────────────

    def run(self) -> None:
        logger.info("S2T starting (engine=%s)", config.ENGINE)
        self._engine.start()
        self._hotkeys.start()
        logger.info(
            "Press %s to toggle recording. Right-click tray icon for menu.",
            config.TOGGLE_HOTKEY,
        )
        self._tray.run()  # blocks until exit

    def toggle_recording(self) -> None:
        with self._lock:
            if self._recording:
                self._stop_recording_locked()
            else:
                self._start_recording_locked()

    def start_recording(self) -> None:
        with self._lock:
            if not self._recording:
                self._start_recording_locked()

    def stop_recording(self) -> None:
        with self._lock:
            if self._recording:
                self._stop_recording_locked()

    # ── private ────────────────────────────────────────────────────────────

    def _start_recording_locked(self) -> None:
        logger.info("Recording started.")
        self._recording = True
        self._text_proc.reset()
        with self._interim_lock:
            self._interim_typed = ""
        if self._vad:
            self._vad.reset()

        # Open a fresh WebSocket connection for this session
        self._engine.connect()

        # Start audio capture
        self._capture = AudioCapture()
        self._capture.start()
        self._capture_thread = threading.Thread(
            target=self._audio_loop, daemon=True, name="audio-loop"
        )
        self._capture_thread.start()

        # Show recording HUD
        self._rec_window = RecordingWindow(on_stop=self.stop_recording)
        self._rec_window.show()

        self._tray.set_recording(True)

    def _stop_recording_locked(self) -> None:
        logger.info("Recording stopped.")
        self._recording = False

        # Erase any interim text still on screen
        with self._interim_lock:
            if self._interim_typed:
                self._keyboard.backspace(len(self._interim_typed))
                self._interim_typed = ""

        # Stop audio first
        if self._capture:
            self._capture.stop()
            self._capture = None

        # Disconnect WebSocket
        self._engine.disconnect()

        if self._vad:
            self._vad.reset()

        # Hide recording HUD
        if self._rec_window:
            self._rec_window.hide()
            self._rec_window = None

        self._tray.set_recording(False)

    def _audio_loop(self) -> None:
        """Runs in a background thread; feeds audio to VAD or Deepgram."""
        capture = self._capture
        if capture is None:
            return
        try:
            for chunk in capture.stream():
                if not self._recording:
                    break
                # Push amplitude to waveform display
                if self._rec_window:
                    self._rec_window.push_amplitude(_rms(chunk))
                # Feed audio to STT
                if self._vad:
                    self._vad.process(chunk)
                else:
                    self._engine.stream_audio(chunk)
        except Exception:
            logger.exception("Error in audio loop")

    def _on_transcript(self, text: str, is_final: bool) -> None:
        text = text.strip()
        if not text:
            return

        with self._interim_lock:
            if not is_final and config.INTERIM_RESULTS:
                # ── Interim: only type words that are NEW at the end ──────
                if text.startswith(self._interim_typed):
                    # Common case: Deepgram added more words — type the suffix
                    suffix = text[len(self._interim_typed):]
                    if suffix:
                        self._keyboard.type_raw(suffix)
                        self._interim_typed = text
                else:
                    # Deepgram corrected an earlier word — full rewrite (rare)
                    self._keyboard.backspace(len(self._interim_typed))
                    self._keyboard.type_raw(text)
                    self._interim_typed = text

            elif is_final:
                # ── Final: commit the result ──────────────────────────────
                cleaned = self._text_proc.process(text)

                if cleaned is None:
                    # Duplicate utterance — erase the interim and skip
                    self._keyboard.backspace(len(self._interim_typed))
                elif cleaned.startswith(self._interim_typed):
                    # Final extends what's already on screen — type the rest
                    suffix = cleaned[len(self._interim_typed):]
                    self._keyboard.type_raw(suffix + " ")
                else:
                    # smart_format changed capitalization/punctuation — correct it
                    self._keyboard.backspace(len(self._interim_typed))
                    self._keyboard.type_raw(cleaned + " ")

                self._interim_typed = ""

    def _on_speech_start(self) -> None:
        logger.debug("Speech detected.")

    def _open_settings(self) -> None:
        import tkinter as tk
        from src.ui.settings_window import SettingsWindow
        root = tk.Tk()
        root.withdraw()
        SettingsWindow(root).show()

    def _exit(self) -> None:
        logger.info("Exiting…")
        self.stop_recording()
        self._hotkeys.stop()
        self._engine.stop()
        self._tray.stop()


def main() -> None:
    app = S2TApp()
    app.run()


if __name__ == "__main__":
    main()
