import pytest

from poker_coach.engine.models import GameState
from poker_coach.engine.showdown import classify, resolve_showdown


def make_state(
    hero_hole: tuple[str, str], villain_hole: tuple[str, str], board: list[str]
) -> GameState:
    return GameState(
        hand_id="test",
        bb=100,
        effective_stack=10_000,
        hero_stack_start=10_000,
        villain_stack_start=10_000,
        button="hero",
        hero_hole=hero_hole,
        villain_hole=villain_hole,
        board=board,
        street="showdown",
        stacks={"hero": 0, "villain": 0},
        committed={"hero": 0, "villain": 0},
        pot=20_000,
    )


class TestClassify:
    def test_rank_thresholds(self) -> None:
        assert classify(1) == "royal flush"
        assert classify(10) == "straight flush"
        assert classify(11) == "four of a kind"
        assert classify(166) == "four of a kind"
        assert classify(167) == "full house"
        assert classify(322) == "full house"
        assert classify(323) == "flush"
        assert classify(1599) == "flush"
        assert classify(1600) == "straight"
        assert classify(1609) == "straight"
        assert classify(1610) == "three of a kind"
        assert classify(2467) == "three of a kind"
        assert classify(2468) == "two pair"
        assert classify(3325) == "two pair"
        assert classify(3326) == "pair"
        assert classify(6185) == "pair"
        assert classify(6186) == "high card"
        assert classify(7462) == "high card"


class TestShowdown:
    def test_royal_flush_beats_full_house(self) -> None:
        s = make_state(
            hero_hole=("As", "Ks"),
            villain_hole=("Kh", "Kd"),
            board=["Qs", "Js", "Ts", "Kc", "2d"],
        )
        r = resolve_showdown(s)
        assert r.winner == "hero"
        assert r.hero_label == "royal flush"
        assert r.villain_label in {"four of a kind", "full house", "three of a kind"}

    def test_flush_beats_straight(self) -> None:
        s = make_state(
            hero_hole=("Ah", "2h"),
            villain_hole=("8c", "9d"),
            board=["5h", "7h", "Jh", "6s", "Tc"],
        )
        r = resolve_showdown(s)
        assert r.winner == "hero"
        assert r.hero_label == "flush"
        assert r.villain_label == "straight"

    def test_higher_pair_wins(self) -> None:
        s = make_state(
            hero_hole=("As", "Ah"),
            villain_hole=("Ks", "Kh"),
            board=["2c", "5d", "7s", "9h", "Jc"],
        )
        r = resolve_showdown(s)
        assert r.winner == "hero"
        assert r.hero_label == "pair"
        assert r.villain_label == "pair"

    def test_chopped_board_is_tie(self) -> None:
        s = make_state(
            hero_hole=("2c", "3d"),
            villain_hole=("2h", "3s"),
            board=["As", "Ks", "Qs", "Js", "Ts"],  # straight on board, both play it
        )
        r = resolve_showdown(s)
        assert r.winner == "tie"
        assert r.hero_rank == r.villain_rank

    def test_requires_five_board_cards(self) -> None:
        s = make_state(
            hero_hole=("As", "Ks"),
            villain_hole=("Qs", "Js"),
            board=["Ts", "9s", "8s"],
        )
        with pytest.raises(ValueError):
            resolve_showdown(s)

    def test_requires_villain_hole(self) -> None:
        s = GameState(
            hand_id="test",
            bb=100,
            effective_stack=10_000,
            hero_stack_start=10_000,
            villain_stack_start=10_000,
            button="hero",
            hero_hole=("As", "Ks"),
            villain_hole=None,
            board=["Qs", "Js", "Ts", "2d", "3c"],
            street="showdown",
            stacks={"hero": 0, "villain": 0},
            committed={"hero": 0, "villain": 0},
            pot=20_000,
        )
        with pytest.raises(ValueError):
            resolve_showdown(s)
