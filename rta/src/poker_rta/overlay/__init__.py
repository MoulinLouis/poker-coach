from __future__ import annotations

from poker_rta.overlay.confidence import classify, render_line

__all__ = ["AdviceOverlay", "StateMirrorPanel", "classify", "render_line"]


def __getattr__(name: str) -> object:
    if name == "AdviceOverlay":
        from poker_rta.overlay.window import AdviceOverlay

        return AdviceOverlay
    if name == "StateMirrorPanel":
        from poker_rta.overlay.state_panel import StateMirrorPanel

        return StateMirrorPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
