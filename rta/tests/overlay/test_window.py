from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_overlay_window_constructs() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.show_advice({"action": "raise", "to_bb": 3.0, "rationale": "value"})
    assert "raise" in win.current_text().lower()
    app.quit()
