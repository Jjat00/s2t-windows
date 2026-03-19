"""
Floating recording HUD — minimal glass pill.

Fully transparent body, only a glass border visible.
Waveform and text contrast against whatever is behind.
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Callable

import tkinter as tk

_KEY = "#fe01fe"

# ── minimal glass palette ─────────────────────────────────────────────────
_BORDER    = "#55557a"     # glass rim — subtle, not white
_TEXT      = "#ffffff"
_PREVIEW   = "#ddddff"
_DOT_ON    = "#ff3344"
_DOT_OFF   = "#663333"
_DOT_GLOW  = "#ff334466"
_STOP_TXT  = "#ccccee"
_STOP_HOV  = "#ffffff"

_FONT = "Segoe UI"
_MONO = "Consolas"

# ── geometry ──────────────────────────────────────────────────────────────
_W, _H = 250, 46
_R     = 20

# ── waveform ──────────────────────────────────────────────────────────────
_BAR_COUNT = 40
_WF_X1, _WF_X2 = 76, 194
_WF_CY     = 20
_WF_MAX_H  = 11

_UPDATE_MS   = 30
_MAX_PREVIEW = 48


def _pill(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    pts = [
        x1 + r, y1,    x2 - r, y1,
        x2,     y1,    x2,     y1 + r,
        x2,     y2 - r, x2,    y2,
        x2 - r, y2,    x1 + r, y2,
        x1,     y2,    x1,     y2 - r,
        x1,     y1 + r, x1,    y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


class RecordingWindow:

    def __init__(self, on_stop: Callable[[], None]) -> None:
        self._on_stop    = on_stop
        self._amp_queue  = queue.Queue(maxsize=300)
        self._text_queue = queue.Queue(maxsize=50)
        self._amplitudes = deque([0.0] * _BAR_COUNT, maxlen=_BAR_COUNT)
        self._start_time = 0.0
        self._root: tk.Tk | None = None
        self._canvas: tk.Canvas | None = None
        self._alive      = False
        self._drag_x     = 0
        self._drag_y     = 0
        self._preview    = ""

    def show(self) -> None:
        self._start_time = time.monotonic()
        self._alive = True
        threading.Thread(target=self._run, daemon=True, name="rec-window").start()

    def hide(self) -> None:
        self._alive = False
        if self._root:
            try:
                self._root.after(0, self._destroy)
            except Exception:
                pass

    def push_amplitude(self, rms: float) -> None:
        try:
            self._amp_queue.put_nowait(rms)
        except queue.Full:
            pass

    def push_text(self, text: str) -> None:
        try:
            while not self._text_queue.empty():
                self._text_queue.get_nowait()
            self._text_queue.put_nowait(text)
        except queue.Empty:
            pass

    def _run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.overrideredirect(True)
        root.configure(bg=_KEY)
        root.attributes("-topmost", True)
        root.wm_attributes("-transparentcolor", _KEY)

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{_W}x{_H}+{(sw - _W) // 2}+{sh - _H - 52}")

        c = tk.Canvas(root, width=_W, height=_H, bg=_KEY, highlightthickness=0)
        c.pack()
        self._canvas = c

        # Glass depth: outer shadow → mid body → inner highlight
        # Outer rim (dark, simulates shadow/depth behind the glass)
        _pill(c, 0, 0, _W, _H, _R + 1,
              fill="", outline="#222233", width=3)
        # Main glass edge
        _pill(c, 1, 1, _W - 1, _H - 1, _R,
              fill="", outline="#55557a", width=1)
        # Inner highlight (top-biased specular — light hitting the glass rim)
        c.create_line(_R + 8, 3, _W - _R - 8, 3,
                      fill="#8888bb", width=1, smooth=True)
        # Bottom subtle reflection
        c.create_line(_R + 14, _H - 3, _W - _R - 14, _H - 3,
                      fill="#333355", width=1, smooth=True)

        # Stop — just text, no button box
        sx = _W - 24
        c.create_text(sx, 20, text="✕", font=(_FONT, 11), fill=_STOP_TXT, tags="stop")
        c.tag_bind("stop", "<Button-1>",
                   lambda _: threading.Thread(target=self._on_stop, daemon=True).start())
        c.tag_bind("stop", "<Enter>", lambda _: c.itemconfig("stop", fill=_STOP_HOV))
        c.tag_bind("stop", "<Leave>", lambda _: c.itemconfig("stop", fill=_STOP_TXT))

        c.bind("<ButtonPress-1>", self._drag_start)
        c.bind("<B1-Motion>",     self._drag_move)

        root.after(_UPDATE_MS, self._tick)
        root.mainloop()

    def _tick(self) -> None:
        if not self._root or not self._alive:
            return

        c = self._canvas

        while True:
            try:
                self._amplitudes.append(self._amp_queue.get_nowait())
            except queue.Empty:
                break

        while True:
            try:
                self._preview = self._text_queue.get_nowait()
            except queue.Empty:
                break

        elapsed    = time.monotonic() - self._start_time
        mins, secs = divmod(int(elapsed), 60)
        time_str   = f"{mins:02d}:{secs:02d}"
        dot_on     = int(elapsed * 2) % 2 == 0

        c.delete("dyn")

        # ── dot ──────────────────────────────────────────────────────────
        dx, dy = 15, 20
        c.create_oval(dx - 3, dy - 3, dx + 3, dy + 3,
                      fill=_DOT_ON if dot_on else _DOT_OFF, outline="", tags="dyn")

        # ── timer ────────────────────────────────────────────────────────
        c.create_text(25, 20, text=time_str, anchor="w",
                      font=(_MONO, 9, "bold"), fill=_TEXT, tags="dyn")

        # ── waveform ─────────────────────────────────────────────────────
        n     = len(self._amplitudes)
        avail = _WF_X2 - _WF_X1
        bar_w = avail / n

        for i, amp in enumerate(self._amplitudes):
            x       = _WF_X1 + i * bar_w + bar_w / 2
            boosted = min(1.0, amp ** 0.45 * 2.0)
            h       = max(1.0, boosted * _WF_MAX_H)
            v       = int(140 + min(115, boosted * 150))
            b       = min(255, v + int(boosted * 40))
            color   = f"#{v:02x}{v:02x}{b:02x}"
            half    = max(0.5, bar_w * 0.22)
            c.create_rectangle(
                x - half, _WF_CY - h,
                x + half, _WF_CY + h,
                fill=color, outline="", tags="dyn",
            )

        # ── preview ──────────────────────────────────────────────────────
        if self._preview:
            txt = self._preview
            if len(txt) > _MAX_PREVIEW:
                txt = "…" + txt[-(_MAX_PREVIEW - 1):]
            c.create_text(12, 38, text=txt, anchor="w",
                          font=(_FONT, 7), fill=_PREVIEW, tags="dyn")

        self._root.after(_UPDATE_MS, self._tick)

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._root.winfo_x()
        self._drag_y = event.y_root - self._root.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        self._root.geometry(
            f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}"
        )

    def _destroy(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
