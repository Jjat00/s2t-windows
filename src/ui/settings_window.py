"""
Settings dialog — Vercel-style dark UI.

Writes changes to .env in the project root; restart required.
"""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import pyaudio

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).parent.parent.parent / ".env"

# ── palette ───────────────────────────────────────────────────────────────
_BG      = "#000000"
_SURFACE = "#111111"
_BORDER  = "#1f1f1f"
_TEXT    = "#ededed"
_MUTED   = "#888888"
_INPUT   = "#0a0a0a"
_ACCENT  = "#ededed"
_FONT    = "Segoe UI"
_MONO    = "Consolas"

# ── options ───────────────────────────────────────────────────────────────
_ENGINES = ["deepgram", "whisper"]
_WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
_LANGUAGES = [
    ("auto",   "Auto-detect"),
    ("es",     "Español"),
    ("es-419", "Español (Latinoamérica)"),
    ("en-US",  "English (US)"),
    ("en-GB",  "English (UK)"),
    ("fr",     "Français"),
    ("pt",     "Português"),
    ("de",     "Deutsch"),
    ("it",     "Italiano"),
    ("ja",     "日本語"),
    ("zh",     "中文"),
]
_LANG_CODES   = [c for c, _ in _LANGUAGES]
_LANG_LABELS  = [f"{label}  ({code})" for code, label in _LANGUAGES]


def _read_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(env: dict[str, str]) -> None:
    lines = [f"{k}={v}" for k, v in env.items()]
    _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _list_audio_devices() -> list[tuple[int, str]]:
    pa = pyaudio.PyAudio()
    devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            devices.append((i, info["name"]))
    pa.terminate()
    return devices


# ── widget helpers ────────────────────────────────────────────────────────

def _label(parent, text: str, muted=False) -> tk.Label:
    return tk.Label(
        parent, text=text,
        font=(_FONT, 9),
        fg=_MUTED if muted else _TEXT,
        bg=_BG, anchor="w",
    )


def _dark_entry(parent, textvariable, width=30, show=None) -> tk.Entry:
    kw = dict(
        textvariable=textvariable,
        width=width,
        font=(_MONO, 10),
        fg=_TEXT,
        bg=_INPUT,
        insertbackground=_TEXT,
        relief="flat",
        highlightthickness=1,
        highlightcolor=_BORDER,
        highlightbackground=_BORDER,
    )
    if show:
        kw["show"] = show
    return tk.Entry(parent, **kw)


def _dark_combo(parent, textvariable, values, width=28) -> tk.OptionMenu:
    """OptionMenu styled dark (ttk.Combobox is hard to theme on Windows)."""
    menu = tk.OptionMenu(parent, textvariable, *values)
    menu.config(
        bg=_INPUT, fg=_TEXT,
        activebackground=_SURFACE,
        activeforeground=_TEXT,
        relief="flat",
        font=(_FONT, 9),
        highlightthickness=1,
        highlightbackground=_BORDER,
        bd=0,
        width=width,
        anchor="w",
        indicatoron=True,
    )
    menu["menu"].config(
        bg=_SURFACE, fg=_TEXT,
        activebackground=_BORDER,
        activeforeground=_TEXT,
        font=(_FONT, 9),
        relief="flat",
        bd=0,
    )
    return menu


def _section(parent, title: str) -> tk.Frame:
    frame = tk.Frame(parent, bg=_BG)
    tk.Label(
        frame, text=title.upper(),
        font=(_FONT, 8, "bold"),
        fg=_MUTED, bg=_BG,
    ).pack(anchor="w", pady=(0, 4))
    sep = tk.Frame(frame, bg=_BORDER, height=1)
    sep.pack(fill="x", pady=(0, 10))
    return frame


def _row(parent) -> tuple[tk.Frame, tk.Frame]:
    """Returns (left_cell, right_cell) in a two-column row."""
    r = tk.Frame(parent, bg=_BG)
    r.pack(fill="x", pady=4)
    left  = tk.Frame(r, bg=_BG, width=160)
    left.pack(side="left", anchor="n", pady=2)
    left.pack_propagate(False)
    right = tk.Frame(r, bg=_BG)
    right.pack(side="left", fill="x", expand=True)
    return left, right


# ── main class ────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, parent: tk.Tk | None = None) -> None:
        win = tk.Toplevel(parent) if parent else tk.Tk()
        self._win = win
        win.title("S2T — Settings")
        win.configure(bg=_BG)
        win.resizable(False, False)
        if parent:
            win.grab_set()
        win.attributes("-topmost", True)

        W = 540
        win.geometry(f"{W}x540")
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{W}x540+{(sw - W) // 2}+{(sh - 540) // 2}")

        self._build()
        self._load()

    def show(self) -> None:
        self._win.mainloop()

    # ── build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        scroll_area = tk.Frame(self._win, bg=_BG)
        scroll_area.pack(fill="both", expand=True, padx=28, pady=24)

        # ── Header ───────────────────────────────────────────────────────
        tk.Label(
            scroll_area, text="Settings",
            font=(_FONT, 16, "bold"), fg=_TEXT, bg=_BG, anchor="w",
        ).pack(fill="x", pady=(0, 4))
        tk.Label(
            scroll_area, text="Changes take effect on restart.",
            font=(_FONT, 9), fg=_MUTED, bg=_BG, anchor="w",
        ).pack(fill="x", pady=(0, 20))

        # ── Section: STT ─────────────────────────────────────────────────
        sec = _section(scroll_area, "Speech Recognition")
        sec.pack(fill="x", pady=(0, 16))

        left, right = _row(sec)
        _label(left, "Engine").pack(anchor="w")
        self._engine_var = tk.StringVar()
        _dark_combo(right, self._engine_var, _ENGINES, width=20).pack(anchor="w")

        left, right = _row(sec)
        _label(left, "Language").pack(anchor="w")
        _label(left, "Idioma / Language", muted=True).pack(anchor="w")
        self._lang_var = tk.StringVar()
        _dark_combo(right, self._lang_var, _LANG_LABELS, width=30).pack(anchor="w")

        left, right = _row(sec)
        _label(left, "Whisper Model").pack(anchor="w")
        _label(left, "Only for local engine", muted=True).pack(anchor="w")
        self._whisper_model_var = tk.StringVar()
        _dark_combo(right, self._whisper_model_var, _WHISPER_MODELS, width=20).pack(anchor="w")

        # ── Section: API ─────────────────────────────────────────────────
        sec2 = _section(scroll_area, "Deepgram API")
        sec2.pack(fill="x", pady=(0, 16))

        left, right = _row(sec2)
        _label(left, "API Key").pack(anchor="w")
        self._api_key_var = tk.StringVar()
        _dark_entry(right, self._api_key_var, width=34, show="•").pack(anchor="w")

        # ── Section: Audio ───────────────────────────────────────────────
        sec3 = _section(scroll_area, "Audio")
        sec3.pack(fill="x", pady=(0, 16))

        left, right = _row(sec3)
        _label(left, "Microphone").pack(anchor="w")
        self._devices = _list_audio_devices()
        device_opts = ["Default"] + [f"[{i}] {name}" for i, name in self._devices]
        self._device_var = tk.StringVar()
        _dark_combo(right, self._device_var, device_opts, width=32).pack(anchor="w")

        left, right = _row(sec3)
        _label(left, "Silence threshold").pack(anchor="w")
        _label(left, "Milliseconds", muted=True).pack(anchor="w")
        self._endpointing_var = tk.StringVar()
        _dark_entry(right, self._endpointing_var, width=8).pack(anchor="w")

        # ── Section: Hotkey ──────────────────────────────────────────────
        sec4 = _section(scroll_area, "Hotkey")
        sec4.pack(fill="x", pady=(0, 16))

        left, right = _row(sec4)
        _label(left, "Toggle recording").pack(anchor="w")
        _label(left, "pynput key name", muted=True).pack(anchor="w")
        self._hotkey_var = tk.StringVar()
        _dark_entry(right, self._hotkey_var, width=18).pack(anchor="w")

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(scroll_area, bg=_BG)
        btn_row.pack(fill="x", pady=(8, 0))

        cancel_btn = tk.Button(
            btn_row, text="Cancel",
            font=(_FONT, 9), fg=_MUTED, bg=_BG,
            activebackground=_SURFACE, activeforeground=_TEXT,
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._win.destroy,
        )
        cancel_btn.pack(side="right", padx=(8, 0))

        save_btn = tk.Button(
            btn_row, text="Save changes",
            font=(_FONT, 9, "bold"), fg=_BG, bg=_ACCENT,
            activebackground="#c8c8c8", activeforeground=_BG,
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._save,
        )
        save_btn.pack(side="right")

    # ── load / save ────────────────────────────────────────────────────────

    def _load(self) -> None:
        env = _read_env()
        self._engine_var.set(env.get("ENGINE", "deepgram"))
        self._api_key_var.set(env.get("DEEPGRAM_API_KEY", ""))
        self._whisper_model_var.set(env.get("WHISPER_MODEL", "small"))
        self._endpointing_var.set(env.get("ENDPOINTING_MS", "700"))
        self._hotkey_var.set(env.get("TOGGLE_HOTKEY", "<f9>"))

        # Language
        lang_code = env.get("LANGUAGE", "es")
        idx = _LANG_CODES.index(lang_code) if lang_code in _LANG_CODES else 0
        self._lang_var.set(_LANG_LABELS[idx])

        # Device
        dev_str = env.get("AUDIO_DEVICE_INDEX", "")
        if dev_str:
            idx_d = int(dev_str)
            match = next((f"[{i}] {n}" for i, n in self._devices if i == idx_d), None)
            self._device_var.set(match or "Default")
        else:
            self._device_var.set("Default")

    def _save(self) -> None:
        env = _read_env()
        env["ENGINE"] = self._engine_var.get()
        env["DEEPGRAM_API_KEY"] = self._api_key_var.get()
        env["WHISPER_MODEL"] = self._whisper_model_var.get()
        env["ENDPOINTING_MS"] = self._endpointing_var.get()
        env["TOGGLE_HOTKEY"] = self._hotkey_var.get()

        # Language — extract code from "Label  (code)"
        lang_label = self._lang_var.get()
        idx = _LANG_LABELS.index(lang_label) if lang_label in _LANG_LABELS else 0
        env["LANGUAGE"] = _LANG_CODES[idx]

        # Device
        dev_str = self._device_var.get()
        if dev_str == "Default":
            env["AUDIO_DEVICE_INDEX"] = ""
        else:
            env["AUDIO_DEVICE_INDEX"] = dev_str.split("]")[0].lstrip("[")

        _write_env(env)
        messagebox.showinfo(
            "Saved", "Settings saved.\nRestart S2T for changes to take effect.",
            parent=self._win,
        )
        self._win.destroy()
