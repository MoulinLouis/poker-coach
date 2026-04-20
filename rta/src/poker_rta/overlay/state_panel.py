"""Visual mini-table state mirror.

Replaces the one-line text summary with a painted ~150x180 mini-table
that reads at a glance: villain seat on top, board in the middle, hero
seat on the bottom. A red border highlights whichever seat is `to_act`.

Pure-data helpers (`format_bb`, `classify_to_act`,
`rendered_cards_from_state`) live at module level so tests can assert
widget state without constructing Qt. The `paintEvent` implementation
is what actually draws — its correctness is covered by Qt-smoke tests.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPaintEvent, QPen
from PyQt6.QtWidgets import QWidget

from poker_rta.overlay.state_format import (
    classify_to_act,
    format_bb,
    rendered_cards_from_state,
)

CARD_RED = {"h", "d"}
_EMPTY_CARD = ""

__all__ = [
    "CARD_RED",
    "StateMirrorPanel",
    "classify_to_act",
    "format_bb",
    "rendered_cards_from_state",
]


class StateMirrorPanel(QWidget):
    """Painted mini-table summary of the live engine state."""

    def __init__(self) -> None:
        super().__init__()
        self._state: dict[str, Any] | None = None
        self.setMinimumSize(150, 180)

    # ── public API ────────────────────────────────────────────────────────

    def update_state(self, state: dict[str, Any] | None) -> None:
        self._state = state
        self.update()  # schedules a repaint

    def current_text(self) -> str:
        """Legacy accessor. Returns the fallback string when no state is
        bound, else an empty string — the panel is visual, not textual."""
        return "waiting for state\u2026" if self._state is None else ""

    def rendered_cards(self) -> tuple[str, ...]:
        return rendered_cards_from_state(self._state)

    def rendered_pot_bb(self) -> float | None:
        if self._state is None:
            return None
        bb = self._state.get("bb", 1) or 1
        return format_bb(self._state.get("pot", 0), bb)

    def rendered_to_act(self) -> str | None:
        return classify_to_act(self._state)

    def rendered_board_slots(self) -> tuple[str, ...]:
        """Always returns exactly 5 entries — empty strings for unrevealed
        slots. Lets the layout tests assert on slot count without guessing."""
        if self._state is None:
            return (_EMPTY_CARD,) * 5
        board = list(self._state.get("board") or [])
        return tuple(board + [_EMPTY_CARD] * (5 - len(board)))[:5]

    # ── paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        painter.fillRect(rect, QColor(0, 0, 0, 160))

        if self._state is None:
            painter.setPen(QColor("#aaa"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "waiting for state\u2026")
            painter.end()
            return

        to_act = self.rendered_to_act()
        bb = self._state.get("bb", 1) or 1
        hero_stack = format_bb(self._state.get("stacks", {}).get("hero", 0), bb)
        villain_stack = format_bb(self._state.get("stacks", {}).get("villain", 0), bb)
        hero_bet = format_bb(self._state.get("committed", {}).get("hero", 0), bb)
        villain_bet = format_bb(self._state.get("committed", {}).get("villain", 0), bb)
        pot_bb = self.rendered_pot_bb() or 0.0
        board = self.rendered_board_slots()
        hero_hole = self._state.get("hero_hole") or []

        row_h = rect.height() // 5
        top_row = QRect(rect.x(), rect.y(), rect.width(), row_h)
        board_row = QRect(rect.x(), rect.y() + row_h, rect.width(), row_h)
        pot_row = QRect(rect.x(), rect.y() + 2 * row_h, rect.width(), row_h // 2)
        hero_row = QRect(rect.x(), rect.y() + 3 * row_h, rect.width(), row_h)
        hero_cards_row = QRect(rect.x(), rect.y() + 4 * row_h, rect.width(), row_h)

        font = QFont("monospace", 9)
        painter.setFont(font)

        # Villain seat — highlight if to_act == villain
        if to_act == "villain":
            painter.setPen(QPen(QColor("#f44"), 2))
            painter.drawRect(top_row.adjusted(1, 1, -1, -1))
        painter.setPen(QColor("#fff"))
        painter.drawText(
            top_row,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f" villain {villain_stack}bb ",
        )
        if villain_bet > 0:
            painter.drawText(
                top_row,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{villain_bet}bb ",
            )

        # Board — 5 slots
        slot_w = board_row.width() // 5
        for i, card in enumerate(board):
            slot = QRect(
                board_row.x() + i * slot_w + 1,
                board_row.y() + 2,
                slot_w - 2,
                board_row.height() - 4,
            )
            painter.setPen(QColor("#777"))
            painter.drawRect(slot)
            if card:
                color = "#f88" if len(card) >= 2 and card[1] in CARD_RED else "#eee"
                painter.setPen(QColor(color))
                painter.drawText(slot, Qt.AlignmentFlag.AlignCenter, card)

        # Pot
        painter.setPen(QColor("#ffd"))
        painter.drawText(pot_row, Qt.AlignmentFlag.AlignCenter, f"pot {pot_bb}bb")

        # Hero seat — highlight if to_act == hero
        if to_act == "hero":
            painter.setPen(QPen(QColor("#f44"), 2))
            painter.drawRect(hero_row.adjusted(1, 1, -1, -1))
        painter.setPen(QColor("#fff"))
        painter.drawText(
            hero_row,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f" hero {hero_stack}bb ",
        )
        if hero_bet > 0:
            painter.drawText(
                hero_row,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                f"{hero_bet}bb ",
            )

        # Hero hole cards — two slots, large
        if hero_hole:
            big_font = QFont("monospace", 14, QFont.Weight.Bold)
            painter.setFont(big_font)
            slot_w = hero_cards_row.width() // 2
            for i, card in enumerate(hero_hole[:2]):
                slot = QRect(
                    hero_cards_row.x() + i * slot_w + 4,
                    hero_cards_row.y() + 2,
                    slot_w - 8,
                    hero_cards_row.height() - 4,
                )
                painter.setPen(QColor("#777"))
                painter.drawRect(slot)
                color = "#f88" if len(card) >= 2 and card[1] in CARD_RED else "#eee"
                painter.setPen(QColor(color))
                painter.drawText(slot, Qt.AlignmentFlag.AlignCenter, str(card))

        painter.end()
