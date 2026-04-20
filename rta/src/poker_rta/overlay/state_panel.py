"""State mirror panel — renders a compact one-liner summary of the current
game state for the overlay so the operator can verify the CV pipeline is
reading the table correctly.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


def _fmt(chips: int | float, bb: int | float) -> str:
    return f"{chips / bb}bb"


def _render(state: dict) -> str:  # type: ignore[type-arg]
    bb: int | float = state["bb"]

    hero_hole: list[str] = state.get("hero_hole") or []
    board: list[str] = state.get("board") or []

    hero_stack = state["stacks"]["hero"]
    hero_committed = state["committed"]["hero"]
    villain_stack = state["stacks"]["villain"]
    villain_committed = state["committed"]["villain"]

    pot = state.get("pot", 0)
    to_act = state.get("to_act") or "—"
    street = state.get("street") or "—"

    hero_cards = "".join(hero_hole) if hero_hole else "??"
    board_str = " ".join(board) if board else "—"

    line = (
        f"hero {hero_cards}  board {board_str}"
        f" / pot {_fmt(pot, bb)}"
        f"  hero {_fmt(hero_stack, bb)} (in {_fmt(hero_committed, bb)})"
        f" / villain {_fmt(villain_stack, bb)} (in {_fmt(villain_committed, bb)})"
        f" / to act: {to_act}  street: {street}"
    )
    return line


class StateMirrorPanel(QWidget):
    """Compact read-only state summary displayed in the overlay."""

    def __init__(self) -> None:
        super().__init__()
        self._label = QLabel("—")
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            "color: #cfc; background: rgba(0,0,0,130); padding: 6px;"
            " border-radius: 5px; font-family: monospace; font-size: 11px;"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    def update_state(self, state: dict | None) -> None:  # type: ignore[type-arg]
        if state is None:
            self._label.setText("—")
            return
        self._label.setText(_render(state))

    def current_text(self) -> str:
        return self._label.text()
