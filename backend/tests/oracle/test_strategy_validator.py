import pytest

from poker_coach.engine.models import LegalAction
from poker_coach.oracle.strategy_validator import normalize_strategy


def _la(type_: str, min_to_bb: float | None = None, max_to_bb: float | None = None) -> LegalAction:
    # Engine LegalAction uses integer chips for min_to/max_to, but the
    # validator works in BB (already converted upstream). Build a shim
    # that exposes the same fields the validator reads.
    return LegalAction(
        type=type_,  # type: ignore[arg-type]
        min_to=int(min_to_bb * 100) if min_to_bb is not None else None,
        max_to=int(max_to_bb * 100) if max_to_bb is not None else None,
    )


def test_valid_mix_sums_to_one() -> None:
    out = normalize_strategy(
        [
            {"action": "check", "to_amount_bb": None, "frequency": 0.35},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.65},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 2
    # Sorted desc by frequency
    assert out[0].action == "bet"
    assert out[0].frequency == pytest.approx(0.65)
    assert out[1].action == "check"


def test_normalizes_within_tolerance_band() -> None:
    # Sum = 0.99 → normalized to exactly 1.0
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.30},
            {"action": "call", "to_amount_bb": None, "frequency": 0.69},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    total = sum(e.frequency for e in out)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_rejects_sum_below_tolerance() -> None:
    with pytest.raises(ValueError, match="frequencies sum"):
        normalize_strategy(
            [
                {"action": "fold", "to_amount_bb": None, "frequency": 0.50},
                {"action": "call", "to_amount_bb": None, "frequency": 0.47},
            ],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_sum_above_tolerance() -> None:
    with pytest.raises(ValueError, match="frequencies sum"):
        normalize_strategy(
            [
                {"action": "fold", "to_amount_bb": None, "frequency": 0.60},
                {"action": "call", "to_amount_bb": None, "frequency": 0.45},
            ],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_illegal_action() -> None:
    with pytest.raises(ValueError, match="not legal"):
        normalize_strategy(
            [{"action": "raise", "to_amount_bb": 6.0, "frequency": 1.0}],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_sizing_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        normalize_strategy(
            [{"action": "bet", "to_amount_bb": 200.0, "frequency": 1.0}],
            legal_actions=[_la("bet", 1.0, 100.0)],
            bb_chips=100,
        )


def test_rejects_missing_sizing_on_bet() -> None:
    with pytest.raises(ValueError, match="sizing required"):
        normalize_strategy(
            [{"action": "bet", "to_amount_bb": None, "frequency": 1.0}],
            legal_actions=[_la("bet", 1.0, 100.0)],
            bb_chips=100,
        )


def test_rejects_sizing_on_non_sizing_action() -> None:
    with pytest.raises(ValueError, match="must be null"):
        normalize_strategy(
            [{"action": "check", "to_amount_bb": 3.0, "frequency": 1.0}],
            legal_actions=[_la("check")],
            bb_chips=100,
        )


def test_merges_duplicate_action_sizing() -> None:
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.40},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.25},
            {"action": "check", "to_amount_bb": None, "frequency": 0.35},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 2
    bet_entry = next(e for e in out if e.action == "bet")
    assert bet_entry.frequency == pytest.approx(0.65)


def test_drops_zero_frequency_entries() -> None:
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.0},
            {"action": "call", "to_amount_bb": None, "frequency": 1.0},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    assert [e.action for e in out] == ["call"]


def test_rejects_empty_after_drop() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_strategy(
            [{"action": "fold", "to_amount_bb": None, "frequency": 0.0}],
            legal_actions=[_la("fold")],
            bb_chips=100,
        )


def test_argmax_tiebreak_prefers_fold_over_call_on_tie() -> None:
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.5},
            {"action": "call", "to_amount_bb": None, "frequency": 0.5},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    # Conservatism: on a tie, fold is the argmax, not call.
    assert out[0].action == "fold"


def test_argmax_tiebreak_prefers_smaller_bet_sizing_on_tie() -> None:
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 8.0, "frequency": 0.5},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.5},
        ],
        legal_actions=[_la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert out[0].to_amount_bb == 3.0


def test_argmax_tiebreak_full_ordering() -> None:
    # All six actions tied at equal frequency — argmax must be fold.
    out = normalize_strategy(
        [
            {"action": "allin", "to_amount_bb": None, "frequency": 1 / 6},
            {"action": "raise", "to_amount_bb": 10.0, "frequency": 1 / 6},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 1 / 6},
            {"action": "call", "to_amount_bb": None, "frequency": 1 / 6},
            {"action": "check", "to_amount_bb": None, "frequency": 1 / 6},
            {"action": "fold", "to_amount_bb": None, "frequency": 1 / 6},
        ],
        legal_actions=[
            _la("allin", 100.0, 100.0),
            _la("raise", 2.0, 100.0),
            _la("bet", 1.0, 100.0),
            _la("call"),
            _la("check"),
            _la("fold"),
        ],
        bb_chips=100,
    )
    assert out[0].action == "fold"


def test_polarized_sizing_preserved() -> None:
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.40},
            {"action": "bet", "to_amount_bb": 7.0, "frequency": 0.20},
            {"action": "check", "to_amount_bb": None, "frequency": 0.40},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 3
    sizings = sorted(e.to_amount_bb for e in out if e.to_amount_bb is not None)
    assert sizings == [3.0, 7.0]


import math


def test_rejects_nan_frequency() -> None:
    with pytest.raises(ValueError, match="finite"):
        normalize_strategy(
            [{"action": "fold", "to_amount_bb": None, "frequency": float("nan")}],
            legal_actions=[_la("fold")],
            bb_chips=100,
        )


def test_rejects_nan_frequency_hidden_in_mix_that_sums_to_one() -> None:
    # The dangerous silent-corruption case: fold=0.5 + check=NaN + call=0.5.
    # Without the finite guard, NaN is silently dropped, fold+call sum to 1,
    # tolerance passes, `check` disappears without warning.
    with pytest.raises(ValueError, match="finite"):
        normalize_strategy(
            [
                {"action": "fold", "to_amount_bb": None, "frequency": 0.5},
                {"action": "check", "to_amount_bb": None, "frequency": float("nan")},
                {"action": "call", "to_amount_bb": None, "frequency": 0.5},
            ],
            legal_actions=[_la("fold"), _la("check"), _la("call")],
            bb_chips=100,
        )


def test_rejects_infinite_frequency() -> None:
    with pytest.raises(ValueError, match="finite"):
        normalize_strategy(
            [{"action": "fold", "to_amount_bb": None, "frequency": math.inf}],
            legal_actions=[_la("fold")],
            bb_chips=100,
        )


def test_argmax_non_tie_uses_frequency_not_conservatism() -> None:
    """Sanity: when frequencies differ (even slightly), higher-freq wins.

    Conservatism tie-break must NOT override a real frequency margin —
    otherwise fold would always win everything.
    """
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.51},
            {"action": "fold", "to_amount_bb": None, "frequency": 0.49},
        ],
        legal_actions=[_la("fold"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert out[0].action == "bet", "higher frequency wins, conservatism is only a tiebreaker"


def test_argmax_near_tie_still_follows_frequency() -> None:
    """A 0.5001 vs 0.4999 split is NOT an exact tie — frequency decides."""
    out = normalize_strategy(
        [
            {"action": "call", "to_amount_bb": None, "frequency": 0.5001},
            {"action": "fold", "to_amount_bb": None, "frequency": 0.4999},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    assert out[0].action == "call"


def test_argmax_three_way_tie_full_ordering() -> None:
    """fold/call/bet three-way tie resolves fold -> call -> bet (conservatism)."""
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.333},
            {"action": "call", "to_amount_bb": None, "frequency": 0.334},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.333},
        ],
        legal_actions=[_la("fold"), _la("call"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    # call has 0.001 more → it wins first on frequency. fold and bet truly tie
    # at 0.333, conservatism picks fold next.
    assert [e.action for e in out] == ["call", "fold", "bet"]


def test_argmax_exact_three_way_tie_full_ordering() -> None:
    """Three-way exact tie must resolve by conservatism across ALL positions."""
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 1 / 3},
            {"action": "fold", "to_amount_bb": None, "frequency": 1 / 3},
            {"action": "call", "to_amount_bb": None, "frequency": 1 / 3},
        ],
        legal_actions=[_la("fold"), _la("call"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert [e.action for e in out] == ["fold", "call", "bet"]
