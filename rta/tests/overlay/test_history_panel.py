"""History panel tests.

Pure-data tests cover the records buffer and line formatter without
Qt. Qt-smoke tests (gated by RTA_QT_SMOKE) exercise construction,
push-through, and collapse-toggle behavior.
"""

from __future__ import annotations

import os

import pytest

from poker_rta.overlay.history_buffer import (
    MAX_ENTRIES,
    MAX_REASONING_CHARS,
    HistoryBuffer,
    format_entry_line,
)

# ── pure-data tests ──────────────────────────────────────────────────────────


def test_format_entry_line_includes_street_action_and_confidence() -> None:
    line = format_entry_line(
        {
            "street": "flop",
            "action": "raise",
            "to_bb": 3.0,
            "confidence": "high",
            "reasoning": "value + protection, continue turn",
        }
    )
    assert "[flop]" in line
    assert "raise 3.0bb" in line
    assert "high" in line
    assert "value + protection" in line


def test_format_entry_line_truncates_long_reasoning() -> None:
    long = "x" * 200
    line = format_entry_line(
        {"street": "river", "action": "call", "confidence": "low", "reasoning": long}
    )
    # MAX_REASONING_CHARS - 1 chars + ellipsis → total length caps at MAX_REASONING_CHARS
    assert "\u2026" in line
    body = line.split('"')[-2]
    assert len(body) == MAX_REASONING_CHARS


def test_format_entry_line_omits_sizing_when_to_bb_is_none() -> None:
    line = format_entry_line(
        {"street": "turn", "action": "check", "to_bb": None, "confidence": "medium"}
    )
    assert "check" in line
    assert "bb" not in line.split("·")[0]


def test_history_buffer_caps_at_max_entries() -> None:
    buf = HistoryBuffer()
    for i in range(MAX_ENTRIES + 3):
        buf.push({"street": "preflop", "action": f"a{i}", "confidence": "high"})
    records = buf.records()
    assert len(records) == MAX_ENTRIES
    # Oldest entries dropped; latest MAX_ENTRIES retained in push order.
    assert records[0]["action"] == f"a{3}"
    assert records[-1]["action"] == f"a{MAX_ENTRIES + 2}"


def test_history_buffer_clear_empties() -> None:
    buf = HistoryBuffer()
    buf.push({"street": "flop", "action": "bet", "confidence": "medium"})
    buf.push({"street": "turn", "action": "call", "confidence": "low"})
    buf.clear()
    assert buf.records() == []
    assert len(buf) == 0


# ── Qt smoke tests (gated) ───────────────────────────────────────────────────


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_history_panel_push_populates_records_and_starts_collapsed() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.history_panel import HistoryPanel

    app = QApplication.instance() or QApplication([])
    panel = HistoryPanel()
    assert panel.is_collapsed() is True
    panel.push(
        {
            "street": "flop",
            "action": "raise",
            "to_bb": 3.0,
            "confidence": "high",
            "reasoning": "value + protection",
        }
    )
    records = panel.records()
    assert len(records) == 1
    assert records[0]["street"] == "flop"
    app.quit()


@pytest.mark.skipif(not os.environ.get("RTA_QT_SMOKE"), reason="requires display")
def test_history_panel_toggle_flips_collapsed_state() -> None:
    from PyQt6.QtWidgets import QApplication

    from poker_rta.overlay.history_panel import HistoryPanel

    app = QApplication.instance() or QApplication([])
    panel = HistoryPanel()
    assert panel.is_collapsed() is True
    panel.toggle()
    assert panel.is_collapsed() is False
    panel.toggle()
    assert panel.is_collapsed() is True
    app.quit()
