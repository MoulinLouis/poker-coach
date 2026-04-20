"""Pure-data primitives for the history panel.

Separated from history_panel.py so tests can exercise buffer + format
logic without pulling in PyQt6 (which fails to import on headless CI
without libGL).
"""

from __future__ import annotations

from collections import deque
from typing import Any

MAX_ENTRIES = 6
MAX_REASONING_CHARS = 80


def format_entry_line(record: dict[str, Any]) -> str:
    """Render one history row as a single-line string.

    Format: `[street]  action sizing  · confidence  · "reasoning…"`.
    Reasoning is truncated to MAX_REASONING_CHARS - 1 so the ellipsis
    lands at the cap instead of past it.
    """
    street = record.get("street", "?")
    action = record.get("action", "?")
    to_bb = record.get("to_bb")
    confidence = record.get("confidence", "?")
    reasoning = record.get("reasoning", "") or ""
    if len(reasoning) > MAX_REASONING_CHARS:
        reasoning = reasoning[: MAX_REASONING_CHARS - 1].rstrip() + "\u2026"
    action_str = f"{action} {to_bb}bb" if to_bb is not None else str(action)
    return f'[{street}]  {action_str}  \u00b7 {confidence}  \u00b7 "{reasoning}"'


class HistoryBuffer:
    """Pure-data ring buffer of advice records. Qt-free so tests can
    assert behavior without instantiating QApplication. HistoryPanel
    holds one and delegates to it."""

    def __init__(self, maxlen: int = MAX_ENTRIES) -> None:
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def push(self, record: dict[str, Any]) -> None:
        self._records.append(dict(record))

    def clear(self) -> None:
        self._records.clear()

    def records(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._records]

    def __len__(self) -> int:
        return len(self._records)
