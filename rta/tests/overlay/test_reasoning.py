from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_reasoning_accumulates() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.append_reasoning_delta("a")
    win.append_reasoning_delta("b")
    win.append_reasoning_delta("c")
    assert win.current_reasoning() == "abc"
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_reasoning_truncates_long_delta() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.append_reasoning_delta("x" * 1000)
    result = win.current_reasoning()
    assert len(result) == 601
    assert result.startswith("\u2026")
    app.quit()
