"""Pure unit tests for confidence classification and rendering — no Qt required."""

from __future__ import annotations

import pytest

from poker_rta.overlay.confidence import classify, render_line


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.95, "ok"),
        (0.9, "ok"),
        (0.8, "warn"),
        (0.7, "warn"),
        (0.5, "bad"),
        (0.0, "bad"),
    ],
)
def test_classify(value: float, expected: str) -> None:
    assert classify(value) == expected


def test_render_line_ok_contains_green_and_label() -> None:
    result = render_line("action", 0.95)
    assert "#4f4" in result
    assert "action" in result
    assert "0.95" in result


def test_render_line_warn_contains_yellow_and_label() -> None:
    result = render_line("sizing", 0.8)
    assert "#fc4" in result
    assert "sizing" in result
    assert "0.80" in result


def test_render_line_bad_contains_red_and_label() -> None:
    result = render_line("bluff_freq", 0.5)
    assert "#f44" in result
    assert "bluff_freq" in result
    assert "0.50" in result
