"""
System tray application using pystray.

Provides:
- System tray icon with status indication (recording / idle)
- Start / Stop recording menu items
- Settings dialog
- Exit
"""
from __future__ import annotations

import logging
import threading
from typing import Callable

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as Item, Menu

logger = logging.getLogger(__name__)

# Icon sizes
_ICON_SIZE = (64, 64)


def _make_icon(recording: bool) -> Image.Image:
    """Draw a simple coloured circle icon."""
    img = Image.new("RGBA", _ICON_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = (220, 50, 50) if recording else (80, 160, 80)  # red=recording, green=idle
    draw.ellipse([8, 8, 56, 56], fill=color, outline=(255, 255, 255), width=3)
    return img


class TrayApp:
    """
    Manages the system tray icon and menu.

    Parameters
    ----------
    on_start     : called when user clicks Start or toggles on
    on_stop      : called when user clicks Stop or toggles off
    on_settings  : called when user opens Settings
    on_exit      : called when user clicks Exit
    """

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_settings: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_settings = on_settings
        self._on_exit = on_exit
        self._recording = False
        self._icon: pystray.Icon | None = None

    # ── public ────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the tray icon (blocks until exit)."""
        self._icon = pystray.Icon(
            "s2t",
            icon=_make_icon(False),
            title="S2T — Idle",
            menu=self._build_menu(),
        )
        self._icon.run()

    def set_recording(self, recording: bool) -> None:
        """Update icon and menu to reflect recording state."""
        self._recording = recording
        if self._icon:
            self._icon.icon = _make_icon(recording)
            self._icon.title = "S2T — Recording…" if recording else "S2T — Idle"
            self._icon.menu = self._build_menu()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()

    # ── private ────────────────────────────────────────────────────────────

    def _build_menu(self) -> Menu:
        if self._recording:
            toggle_item = Item("Stop Recording", self._click_stop, default=True)
        else:
            toggle_item = Item("Start Recording", self._click_start, default=True)

        return Menu(
            toggle_item,
            Menu.SEPARATOR,
            Item("Settings", self._click_settings),
            Menu.SEPARATOR,
            Item("Exit", self._click_exit),
        )

    def _click_start(self, icon, item) -> None:
        self._on_start()

    def _click_stop(self, icon, item) -> None:
        self._on_stop()

    def _click_settings(self, icon, item) -> None:
        # Open settings in a separate thread to avoid blocking tray
        threading.Thread(target=self._on_settings, daemon=True).start()

    def _click_exit(self, icon, item) -> None:
        self._on_exit()
