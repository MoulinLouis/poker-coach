import pytest
from pydantic import ValidationError

from poker_coach.oracle.base import Advice, StrategyEntry


def test_advice_without_strategy_round_trips() -> None:
    a = Advice(
        action="raise",
        to_amount_bb=3.0,
        reasoning="Value raise on a wet board.",
        confidence="high",
    )
    payload = a.model_dump(mode="json")
    assert payload["strategy"] is None
    restored = Advice.model_validate(payload)
    assert restored == a


def test_advice_with_strategy_round_trips() -> None:
    a = Advice(
        action="bet",
        to_amount_bb=3.0,
        reasoning="Polarized c-bet.",
        confidence="medium",
        strategy=[
            StrategyEntry(action="bet", to_amount_bb=3.0, frequency=0.65),
            StrategyEntry(action="check", to_amount_bb=None, frequency=0.35),
        ],
    )
    payload = a.model_dump(mode="json")
    assert isinstance(payload["strategy"], list)
    assert len(payload["strategy"]) == 2
    restored = Advice.model_validate(payload)
    assert restored == a


def test_strategy_entry_is_frozen() -> None:
    e = StrategyEntry(action="check", to_amount_bb=None, frequency=1.0)
    with pytest.raises(ValidationError):
        e.action = "fold"
