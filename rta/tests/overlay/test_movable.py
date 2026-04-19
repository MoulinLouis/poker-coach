from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_overlay_current_position() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    overlay = AdviceOverlay()
    overlay.move(137, 42)
    assert overlay.current_position() == (137, 42)
    app.quit()
