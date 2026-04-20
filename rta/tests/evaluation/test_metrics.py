from __future__ import annotations

from poker_rta.evaluation.metrics import (
    CVAccuracy,
    evaluate_card_accuracy,
)


def test_card_accuracy_all_correct() -> None:
    got = [("As", "Kd"), ("Qc", "Jh")]
    gold = [("As", "Kd"), ("Qc", "Jh")]
    acc = evaluate_card_accuracy(got, gold)
    assert acc == CVAccuracy(correct=4, total=4, rate=1.0)


def test_card_accuracy_partial() -> None:
    got = [("As", "Kd"), ("Qc", "Jh")]
    gold = [("As", "Kd"), ("Qc", "Jc")]
    acc = evaluate_card_accuracy(got, gold)
    assert acc == CVAccuracy(correct=3, total=4, rate=0.75)
