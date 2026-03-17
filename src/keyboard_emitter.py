"""
Types transcribed text at the current cursor position using pynput.

pynput.keyboard.Controller.type() sends synthetic keystrokes to whatever
window currently has focus — i.e., wherever the user's cursor is positioned.

Usage:
    emitter = KeyboardEmitter()
    emitter.type("Hello, world!")
"""
from __future__ import annotations

import logging
import time

from pynput.keyboard import Controller

logger = logging.getLogger(__name__)

# Small delay between typing the text and the next operation.
# Helps some apps (like browsers) catch up with synthetic input.
_TYPE_DELAY_MS = 0


class KeyboardEmitter:
    """Emits text as synthetic keyboard input at the active cursor position."""

    def __init__(self) -> None:
        self._keyboard = Controller()

    def type(self, text: str) -> None:
        """
        Type `text` followed by a space (natural dictation behaviour).
        Thread-safe: pynput Controller is thread-safe on Windows.
        """
        if not text:
            return
        # Append a trailing space so successive words are separated automatically
        output = text + " "
        logger.debug("Typing: %r", output)
        self._keyboard.type(output)
        if _TYPE_DELAY_MS:
            time.sleep(_TYPE_DELAY_MS / 1000)
