"""Transparent always-on-top advice overlay.

Design: frameless window with a semi-transparent dark background, renders the
latest advice in large text. The user sees it over their game client; no input
is ever injected — they click themselves. This is the cinematic piece of the
research demo.
"""

from __future__ import annotations

import time
from typing import Any, Literal

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from poker_rta.overlay.confidence import render_line
from poker_rta.overlay.state_panel import StateMirrorPanel

_MAX_REASONING_CHARS = 600

_STATUS_COLORS: dict[str, str] = {
    "ok": "#0f0",
    "stale": "#555",
    "degraded": "#fa0",
    "error": "#f44",
}


class AdviceOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._label = QLabel("RTA ready.")
        self._label.setStyleSheet(
            "color: #fff; background: rgba(0,0,0,180); padding: 12px;"
            " border-radius: 8px; font-family: monospace; font-size: 18px;"
        )
        self._reasoning = QLabel("")
        self._reasoning.setWordWrap(True)
        self._reasoning.setMaximumHeight(180)
        self._reasoning.setStyleSheet(
            "color: #adf; background: rgba(0,0,0,140); padding: 8px;"
            " border-radius: 6px; font-family: monospace; font-size: 12px;"
        )
        self._reasoning_text: str = ""
        self._confidence = QLabel("")
        self._confidence.setTextFormat(Qt.TextFormat.RichText)
        self._confidence.setWordWrap(True)
        self._confidence.setStyleSheet(
            "color: #fff; background: rgba(0,0,0,140); padding: 6px;"
            " border-radius: 6px; font-family: monospace; font-size: 11px;"
        )
        self._state_panel = StateMirrorPanel()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._reasoning)
        layout.addWidget(self._confidence)
        layout.addWidget(self._state_panel)
        self.resize(420, 180)
        self._status: str = "ok"
        self._last_advice_at: float | None = None

    def show_advice(self, advice: dict[str, Any]) -> None:
        lines = [
            f"{str(advice.get('action', '?')).upper()}"
            + (f"  →  {advice['to_bb']} bb" if "to_bb" in advice else ""),
        ]
        if advice.get("rationale"):
            lines.append(str(advice["rationale"]))
        self._label.setText("\n".join(lines))

    def current_text(self) -> str:
        return self._label.text()

    def clear_reasoning(self) -> None:
        self._reasoning_text = ""
        self._reasoning.setText("")

    def append_reasoning_delta(self, delta: str) -> None:
        combined = self._reasoning_text + delta
        if len(combined) > _MAX_REASONING_CHARS:
            combined = "\u2026" + combined[-_MAX_REASONING_CHARS:]
        self._reasoning_text = combined
        self._reasoning.setText(self._reasoning_text)

    def current_reasoning(self) -> str:
        return self._reasoning_text

    def update_confidence(self, conf: dict[str, float]) -> None:
        lines = [render_line(k, conf[k]) for k in sorted(conf)]
        self._confidence.setText("<br>".join(lines))

    def update_state(self, state: dict[str, Any] | None) -> None:
        self._state_panel.update_state(state)

    def set_status(
        self,
        status: Literal["ok", "stale", "degraded", "error"],
        message: str | None = None,
    ) -> None:
        self._status = status
        color = _STATUS_COLORS[status]
        self.setStyleSheet(f"border: 2px solid {color};")

    def mark_advice_time(self) -> None:
        self._last_advice_at = time.monotonic()

    def tick_staleness(self, stale_after_s: float = 30.0) -> None:
        if (
            self._status == "ok"
            and self._last_advice_at is not None
            and time.monotonic() - self._last_advice_at > stale_after_s
        ):
            self.set_status("stale")

    def current_status(self) -> str:
        return self._status
