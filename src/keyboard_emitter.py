"""
Types transcribed text at the current cursor position using pynput.

pynput.keyboard.Controller.type() sends synthetic keystrokes to whatever
window currently has focus — i.e., wherever the user's cursor is positioned.
"""
from __future__ import annotations

import logging

from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)


class KeyboardEmitter:
    """Emits text as synthetic keyboard input at the active cursor position."""

    def __init__(self) -> None:
        self._keyboard = Controller()

    def type(self, text: str) -> None:
        """Type text followed by a space (committed final result)."""
        if not text:
            return
        logger.debug("Typing final: %r", text)
        self._keyboard.type(text + " ")

    def type_raw(self, text: str) -> None:
        """Type text with no trailing space (interim / partial result)."""
        if not text:
            return
        logger.debug("Typing interim: %r", text)
        self._keyboard.type(text)

    def backspace(self, n: int) -> None:
        """Delete the last n characters by sending n backspace keystrokes."""
        if n <= 0:
            return
        logger.debug("Backspace x%d", n)
        for _ in range(n):
            self._keyboard.press(Key.backspace)
            self._keyboard.release(Key.backspace)
