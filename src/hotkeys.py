"""
Push-to-talk hotkey manager.

Hold the PTT key to record; release it to stop.
Default: Right Ctrl.  Configurable via PTT_KEY in .env.

Supported key names (pynput Key enum names):
  ctrl_r, ctrl_l, alt_r, alt_l, shift_r, shift_l,
  caps_lock, f13, f14 ... or any single character like 'x'
"""
from __future__ import annotations

import logging
from typing import Callable

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from src import config

logger = logging.getLogger(__name__)


def _parse_key(name: str):
    """Parse a key name string into a pynput Key or KeyCode."""
    try:
        return Key[name]
    except KeyError:
        pass
    if len(name) == 1:
        return KeyCode.from_char(name)
    raise ValueError(f"Unknown PTT key: {name!r}. Use a pynput Key name (e.g. ctrl_r, alt_r).")


class HotkeyManager:
    """
    Push-to-talk: hold PTT_KEY to record, release to stop.
    """

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        self._on_start = on_start
        self._on_stop  = on_stop
        self._listener: keyboard.Listener | None = None
        self._active   = False
        self._ptt_key  = _parse_key(config.PTT_KEY)

    def start(self) -> None:
        self._active = False
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("Push-to-talk ready: hold %s to record.", config.PTT_KEY)

    def stop(self) -> None:
        if self._active:
            self._active = False
            self._on_stop()
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("HotkeyManager stopped.")

    # ── private ────────────────────────────────────────────────────────────

    def _matches(self, key) -> bool:
        return key == self._ptt_key

    def _on_press(self, key) -> None:
        if self._matches(key) and not self._active:
            self._active = True
            logger.debug("PTT: start")
            self._on_start()

    def _on_release(self, key) -> None:
        if self._matches(key) and self._active:
            self._active = False
            logger.debug("PTT: stop")
            self._on_stop()
