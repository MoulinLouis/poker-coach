"""Ctrl+R replay tests.

Qt-smoke tests (gated by RTA_QT_SMOKE) assert that the overlay caches
the last completed advice and restores it on `replay_last()`. Also
asserts the cache is cleared by `begin_new_decision` so a mid-stream
replay doesn't resurrect the previous hand's advice.
"""

from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_replay_last_restores_previous_advice() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.append_reasoning_delta("value + protection on the Ah flop")
    win.show_advice({"action": "raise", "to_bb": 3.0, "rationale": "value"})
    baseline_text = win.current_text()
    baseline_reasoning = win.current_reasoning()
    assert "RAISE" in baseline_text

    # User manually clears the reasoning panel (simulates scroll-away).
    win.clear_reasoning()
    assert win.current_reasoning() == ""

    win.replay_last()
    assert win.current_text() == baseline_text
    assert win.current_reasoning() == baseline_reasoning
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_replay_after_begin_new_decision_is_noop() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    win.show_advice({"action": "bet", "to_bb": 2.5, "rationale": "thin value"})
    assert win.has_cached_advice() is True

    win.begin_new_decision()
    assert win.has_cached_advice() is False

    before = win.current_text()
    win.replay_last()  # no-op because cache was cleared
    assert win.current_text() == before
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_replay_with_no_advice_ever_is_noop() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.window import AdviceOverlay

    app = QApplication.instance() or QApplication([])
    win = AdviceOverlay()
    assert win.has_cached_advice() is False
    initial = win.current_text()
    win.replay_last()
    assert win.current_text() == initial
    app.quit()
