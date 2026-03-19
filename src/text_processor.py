"""
Text post-processing: deduplication and cleanup.

Prevents the same phrase from being typed twice due to:
- Overlapping VAD windows
- Whisper hallucinations repeated across chunks
- Deepgram sending the same phrase in multiple final results

Strategy:
1. Normalize text (strip, collapse whitespace, fix capitalisation boundaries).
2. Check if the new text is substantially contained in the recent history
   using a simple sliding-window Levenshtein similarity check.
3. If duplicate detected, skip; otherwise, append to history and return text.
"""
from __future__ import annotations

import logging
import re

from src import config
from src.emoji_map import replace_emojis

logger = logging.getLogger(__name__)


def _levenshtein_ratio(a: str, b: str) -> float:
    """Return similarity ratio in [0, 1] between two strings."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    # Simple DP — sufficient for short strings
    la, lb = len(a), len(b)
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    dist = prev[lb]
    return 1.0 - dist / max(la, lb)


def _normalize(text: str) -> str:
    """Collapse whitespace and strip leading/trailing spaces."""
    return re.sub(r"\s+", " ", text).strip()


class TextProcessor:
    """
    Stateful deduplication buffer.

    Keeps a rolling window of recently typed text (last N chars).
    Before typing new text, checks if it already appears in the window.
    """

    def __init__(
        self,
        lookback_chars: int = config.DEDUP_LOOKBACK_CHARS,
        ratio_threshold: float = config.DEDUP_RATIO_THRESHOLD,
    ) -> None:
        self._lookback = lookback_chars
        self._threshold = ratio_threshold
        self._history: str = ""   # last N characters of typed output

    def process(self, raw_text: str) -> str | None:
        """
        Clean and deduplicate `raw_text`.

        Returns the text to type, or None if it should be suppressed.
        """
        text = _normalize(raw_text)
        if not text:
            return None

        text = replace_emojis(text)

        if self._is_duplicate(text):
            logger.debug("Dedup: suppressed %r", text)
            return None

        self._add_to_history(text)
        return text

    def reset(self) -> None:
        """Clear history (call when stopping/starting a new session)."""
        self._history = ""

    # ── private ────────────────────────────────────────────────────────────

    def _is_duplicate(self, text: str) -> bool:
        if not self._history:
            return False

        # Check if text is a substring of recent history (exact)
        if text.lower() in self._history.lower():
            return True

        # Check fuzzy similarity against a window at the end of history
        window = self._history[-len(text) * 2 :]  # look at ~2x the new text len
        if window:
            ratio = _levenshtein_ratio(text.lower(), window.lower())
            if ratio >= self._threshold:
                return True

        return False

    def _add_to_history(self, text: str) -> None:
        self._history = (self._history + " " + text)[-self._lookback :]
