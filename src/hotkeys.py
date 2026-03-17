"""
Global hotkey listener.

Registers a system-wide hotkey (default F9) to toggle recording on/off.
Uses pynput's GlobalHotKeys so it works even when the app window is not focused.

Usage:
    hk = HotkeyManager(on_toggle=my_callback)
    hk.start()
    ...
    hk.stop()
"""
from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard

from src import config

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Listens for the configured global toggle hotkey."""

    def __init__(self, on_toggle: Callable[[], None]) -> None:
        self._on_toggle = on_toggle
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        hotkey_str = config.TOGGLE_HOTKEY
        try:
            self._listener = keyboard.GlobalHotKeys({hotkey_str: self._on_toggle})
            self._listener.start()
            logger.info("Hotkey registered: %s", hotkey_str)
        except Exception:
            logger.exception("Failed to register hotkey %r", hotkey_str)

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("HotkeyManager stopped.")
