"""Transparent always-on-top advice overlay.

Design: frameless window with a semi-transparent dark background, renders the
latest advice in large text. The user sees it over their game client; no input
is ever injected — they click themselves. This is the cinematic piece of the
research demo.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        self.resize(420, 140)

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
