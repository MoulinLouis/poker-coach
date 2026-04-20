"""Tests for AdviceOverlay status states — gated behind RTA_QT_SMOKE."""

from __future__ import annotations

import os
import time

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_set_status_ok() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.set_status("ok")
    assert win.current_status() == "ok"
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_set_status_error_overrides_ok() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.set_status("ok")
    win.set_status("error", "oops")
    assert win.current_status() == "error"
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_tick_staleness_transitions_to_stale() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.set_status("ok")
    win.mark_advice_time()
    time.sleep(0.05)
    win.tick_staleness(stale_after_s=0.01)
    assert win.current_status() == "stale"
    app.quit()
