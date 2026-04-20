"""Decision history panel — the last N advice entries.

Shows cross-street context the user loses when only the current advice
line is visible ("did the coach say to c-bet flop? what sizing?").

The pure-data primitives (`HistoryBuffer`, `format_entry_line`) live in
`history_buffer.py` so tests can hit them without importing PyQt6.
This module only provides the Qt widget.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from poker_rta.overlay.history_buffer import HistoryBuffer, format_entry_line


class HistoryPanel(QWidget):
    """Collapsible panel showing the last MAX_ENTRIES advice entries."""

    def __init__(self) -> None:
        super().__init__()
        self._buffer = HistoryBuffer()
        self._collapsed = True

        self._header = QPushButton("Decision history (0)")
        self._header.setStyleSheet(
            "QPushButton { color: #fff; background: rgba(0,0,0,160);"
            " padding: 4px; border-radius: 4px; font-family: monospace;"
            " font-size: 11px; text-align: left; }"
        )
        self._header.clicked.connect(self.toggle)

        self._body = QLabel("")
        self._body.setWordWrap(True)
        self._body.setStyleSheet(
            "color: #dde; background: rgba(0,0,0,120); padding: 6px;"
            " border-radius: 4px; font-family: monospace; font-size: 10px;"
        )
        self._body.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._header)
        layout.addWidget(self._body)

    def push(self, record: dict[str, Any]) -> None:
        """Append a record; oldest is dropped at MAX_ENTRIES."""
        self._buffer.push(record)
        self._refresh()

    def clear(self) -> None:
        self._buffer.clear()
        self._refresh()

    def records(self) -> list[dict[str, Any]]:
        return self._buffer.records()

    def toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def _refresh(self) -> None:
        self._header.setText(f"Decision history ({len(self._buffer)})")
        lines = [format_entry_line(r) for r in self._buffer.records()]
        self._body.setText("\n".join(lines))
