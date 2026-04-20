from __future__ import annotations

import pytest

from poker_rta.detection.gto import convergence_score


def test_identical_actions_score_one() -> None:
    assert convergence_score(["raise"] * 100, ["raise"] * 100) == 1.0


def test_no_overlap_scores_zero() -> None:
    assert convergence_score(["fold"] * 100, ["raise"] * 100) == 0.0


def test_partial_agreement() -> None:
    played = ["raise", "fold", "raise"]
    baseline = ["raise", "raise", "raise"]
    assert convergence_score(played, baseline) == pytest.approx(2 / 3)
