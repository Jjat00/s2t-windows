"""
Floating recording HUD — Vercel-style design.

Borderless, draggable panel with:
  - Elapsed timer
  - Live waveform that reacts to microphone volume
  - Live transcription preview (interim results — not typed, just shown)
  - Stop button

Runs in its own daemon thread (separate tkinter event loop).
"""
from __future__ import annotations

import queue
import threading
import time
from collections import deque
from typing import Callable

import tkinter as tk

# ── palette (Vercel dark) ──────────────────────────────────────────────────
_BG       = "#000000"
_SURFACE  = "#0a0a0a"
_BORDER   = "#1f1f1f"
_TEXT     = "#ededed"
_MUTED    = "#666666"
_PREVIEW  = "#999999"   # interim text — slightly brighter than muted
_DOT_ON   = "#ff4444"
_DOT_OFF  = "#2a0a0a"
_BTN_BG   = "#ededed"
_BTN_FG   = "#000000"
_BTN_HOV  = "#c8c8c8"

_FONT     = "Segoe UI"
_MONO     = "Consolas"

_BAR_COUNT = 52
_UPDATE_MS = 35   # ~28 fps
_MAX_PREVIEW_CHARS = 72


class RecordingWindow:
    """Small borderless floating HUD shown while recording."""

    def __init__(self, on_stop: Callable[[], None]) -> None:
        self._on_stop = on_stop
        self._amp_queue:  queue.Queue[float] = queue.Queue(maxsize=300)
        self._text_queue: queue.Queue[str]   = queue.Queue(maxsize=50)
        self._amplitudes: deque[float] = deque([0.0] * _BAR_COUNT, maxlen=_BAR_COUNT)
        self._start_time: float = 0.0
        self._root: tk.Tk | None = None
        self._thread: threading.Thread | None = None
        self._alive = False
        self._drag_x = 0
        self._drag_y = 0

    # ── public ────────────────────────────────────────────────────────────

    def show(self) -> None:
        self._start_time = time.monotonic()
        self._alive = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="rec-window")
        self._thread.start()

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
        """Update the live transcription preview (call from any thread)."""
        try:
            # Drain old pending updates — only the latest matters
            while not self._text_queue.empty():
                self._text_queue.get_nowait()
            self._text_queue.put_nowait(text)
        except queue.Empty:
            pass

    # ── window ────────────────────────────────────────────────────────────

    def _run(self) -> None:
        root = tk.Tk()
        self._root = root

        root.overrideredirect(True)
        root.configure(bg=_BORDER)
        root.attributes("-topmost", True)

        W, H = 420, 160
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{W}x{H}+{(sw - W) // 2}+{sh - H - 60}")

        inner = tk.Frame(root, bg=_BG, padx=0, pady=0)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._build_widgets(inner)

        for w in (root, inner):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)

        root.after(_UPDATE_MS, self._tick)
        root.mainloop()

    def _build_widgets(self, parent: tk.Frame) -> None:
        # ── row 1: indicator + timer ────────────────────────────────────
        top = tk.Frame(parent, bg=_BG)
        top.pack(fill="x", padx=16, pady=(12, 0))

        self._dot = tk.Label(top, text="●", font=(_FONT, 10), fg=_DOT_ON, bg=_BG)
        self._dot.pack(side="left")

        tk.Label(top, text="  Recording",
                 font=(_FONT, 11), fg=_MUTED, bg=_BG).pack(side="left")

        self._timer = tk.Label(top, text="00:00",
                               font=(_MONO, 13, "bold"), fg=_TEXT, bg=_BG)
        self._timer.pack(side="right")

        for w in top.winfo_children():
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_move)
        top.bind("<ButtonPress-1>", self._drag_start)
        top.bind("<B1-Motion>",     self._drag_move)

        # ── row 2: waveform ──────────────────────────────────────────────
        canvas_frame = tk.Frame(parent, bg=_BG)
        canvas_frame.pack(fill="x", padx=16, pady=(8, 0))

        self._canvas = tk.Canvas(canvas_frame, bg=_SURFACE, height=40,
                                 highlightthickness=0)
        self._canvas.pack(fill="x")

        # ── row 3: live transcription preview ────────────────────────────
        self._preview_var = tk.StringVar(value="")
        self._preview_label = tk.Label(
            parent,
            textvariable=self._preview_var,
            font=(_FONT, 9),
            fg=_PREVIEW,
            bg=_BG,
            anchor="w",
            justify="left",
        )
        self._preview_label.pack(fill="x", padx=16, pady=(6, 0))

        # ── row 4: lang pill + stop button ──────────────────────────────
        bot = tk.Frame(parent, bg=_BG)
        bot.pack(fill="x", padx=16, pady=(6, 10))

        from src import config as _cfg
        tk.Label(bot, text=_cfg.LANGUAGE.upper(),
                 font=(_MONO, 8), fg=_MUTED, bg="#111111",
                 padx=6, pady=2).pack(side="left")

        self._stop_btn = tk.Button(
            bot, text="Stop",
            font=(_FONT, 9, "bold"),
            fg=_BTN_FG, bg=_BTN_BG,
            activebackground=_BTN_HOV, activeforeground=_BTN_FG,
            relief="flat", padx=14, pady=4, cursor="hand2",
            command=self._on_stop_clicked,
        )
        self._stop_btn.pack(side="right")
        self._stop_btn.bind("<Enter>", lambda e: self._stop_btn.config(bg=_BTN_HOV))
        self._stop_btn.bind("<Leave>", lambda e: self._stop_btn.config(bg=_BTN_BG))

    # ── update loop ───────────────────────────────────────────────────────

    def _tick(self) -> None:
        if not self._root or not self._alive:
            return

        # Drain amplitude queue
        while True:
            try:
                self._amplitudes.append(self._amp_queue.get_nowait())
            except queue.Empty:
                break

        # Drain text queue (latest wins)
        latest_text: str | None = None
        while True:
            try:
                latest_text = self._text_queue.get_nowait()
            except queue.Empty:
                break
        if latest_text is not None:
            display = latest_text
            if len(display) > _MAX_PREVIEW_CHARS:
                display = "…" + display[-((_MAX_PREVIEW_CHARS - 1)):]
            self._preview_var.set(display)

        # Timer
        elapsed = time.monotonic() - self._start_time
        mins, secs = divmod(int(elapsed), 60)
        self._timer.config(text=f"{mins:02d}:{secs:02d}")

        # Blink dot
        self._dot.config(fg=_DOT_ON if int(elapsed * 2) % 2 == 0 else _DOT_OFF)

        self._draw_waveform()
        self._root.after(_UPDATE_MS, self._tick)

    def _draw_waveform(self) -> None:
        c = self._canvas
        c.delete("all")
        cw = c.winfo_width()
        ch = c.winfo_height()
        if cw < 4:
            return

        n = len(self._amplitudes)
        bar_w = cw / n
        cy = ch / 2

        for i, amp in enumerate(self._amplitudes):
            x = i * bar_w + bar_w / 2
            bar_h = max(2.0, amp * ch * 0.9)
            brightness = int(60 + min(195, amp * 400))
            color = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
            half = bar_w * 0.35
            c.create_rectangle(x - half, cy - bar_h / 2,
                                x + half, cy + bar_h / 2,
                                fill=color, outline="")

    # ── drag ─────────────────────────────────────────────────────────────

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self._root.winfo_x()
        self._drag_y = event.y_root - self._root.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self._root.geometry(f"+{x}+{y}")

    # ── stop ─────────────────────────────────────────────────────────────

    def _on_stop_clicked(self) -> None:
        self._alive = False
        self._destroy()
        threading.Thread(target=self._on_stop, daemon=True).start()

    def _destroy(self) -> None:
        if self._root:
            try:
                self._root.destroy()
            except Exception:
                pass
            self._root = None
