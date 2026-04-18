import pytest

from poker_coach.engine.models import Action, GameState
from poker_coach.engine.rules import (
    IllegalAction,
    apply_action,
    apply_reveal,
    legal_actions,
    start_hand,
)


def fresh_hand(
    *,
    effective_stack: int = 10_000,
    bb: int = 100,
    button: str = "hero",
    rng_seed: int | None = 1,
) -> GameState:
    return start_hand(
        effective_stack=effective_stack,
        bb=bb,
        button=button,  # type: ignore[arg-type]
        rng_seed=rng_seed,
    )


class TestStartHand:
    def test_blinds_posted_and_stacks_correct(self) -> None:
        s = fresh_hand()
        assert s.committed == {"hero": 50, "villain": 100}
        assert s.stacks == {"hero": 9_950, "villain": 9_900}
        assert s.pot == 0
        assert s.street == "preflop"
        assert s.to_act == "hero"
        assert s.last_aggressor == "villain"
        assert s.last_raise_size == 100

    def test_button_can_be_villain(self) -> None:
        s = fresh_hand(button="villain")
        assert s.committed == {"hero": 100, "villain": 50}
        assert s.to_act == "villain"
        assert s.last_aggressor == "hero"

    def test_deck_snapshot_and_hole_cards_dealt(self) -> None:
        s = fresh_hand()
        assert s.deck_snapshot is not None
        assert len(s.deck_snapshot) == 52
        assert s.hero_hole == (s.deck_snapshot[0], s.deck_snapshot[1])
        assert s.villain_hole == (s.deck_snapshot[2], s.deck_snapshot[3])

    def test_explicit_hero_hole_used(self) -> None:
        s = start_hand(
            effective_stack=1_000,
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
            villain_hole=("Qc", "Qh"),
        )
        assert s.hero_hole == ("As", "Kd")
        assert s.villain_hole == ("Qc", "Qh")
        assert s.deck_snapshot is None

    def test_invalid_bb_rejected(self) -> None:
        with pytest.raises(ValueError):
            start_hand(effective_stack=1_000, bb=101, button="hero", hero_hole=("As", "Kd"))

    def test_effective_stack_must_exceed_bb(self) -> None:
        with pytest.raises(ValueError):
            start_hand(effective_stack=100, bb=100, button="hero", hero_hole=("As", "Kd"))


class TestPreflop:
    def test_sb_fold_ends_hand(self) -> None:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="fold"))
        assert s.street == "complete"
        assert s.stacks["villain"] == 10_050  # 9900 + pot 150
        assert s.stacks["hero"] == 9_950

    def test_limp_check_to_flop(self) -> None:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.street == "preflop"
        assert s.committed == {"hero": 100, "villain": 100}
        assert s.to_act == "villain"
        s = apply_action(s, Action(actor="villain", type="check"))
        assert s.street == "flop"
        assert len(s.board) == 3
        assert s.pot == 200
        assert s.committed == {"hero": 0, "villain": 0}
        assert s.to_act == "villain"  # non-button acts first postflop

    def test_open_raise_call_to_flop(self) -> None:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        assert s.last_aggressor == "hero"
        assert s.last_raise_size == 200
        assert s.to_act == "villain"
        s = apply_action(s, Action(actor="villain", type="call"))
        assert s.street == "flop"
        assert s.pot == 600

    def test_open_raise_fold_ends_hand(self) -> None:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        s = apply_action(s, Action(actor="villain", type="fold"))
        assert s.street == "complete"
        # Hero: started 10_000, committed 300, won pot (300 + 100) = 10_100.
        assert s.stacks["hero"] == 10_100
        assert s.stacks["villain"] == 9_900

    def test_three_bet_call(self) -> None:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        s = apply_action(s, Action(actor="villain", type="raise", to_amount=900))
        assert s.last_aggressor == "villain"
        assert s.last_raise_size == 600
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.street == "flop"
        assert s.pot == 1_800

    def test_min_raise_enforced(self) -> None:
        s = fresh_hand()
        # SB opens to 300 — min-raise to 500 required from BB.
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        with pytest.raises(IllegalAction):
            apply_action(s, Action(actor="villain", type="raise", to_amount=499))

    def test_check_when_facing_bet_illegal(self) -> None:
        s = fresh_hand()
        with pytest.raises(IllegalAction):
            apply_action(s, Action(actor="hero", type="check"))

    def test_acting_out_of_turn_illegal(self) -> None:
        s = fresh_hand()
        with pytest.raises(IllegalAction):
            apply_action(s, Action(actor="villain", type="call"))


class TestPostflop:
    def _to_flop(self) -> GameState:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="call"))
        s = apply_action(s, Action(actor="villain", type="check"))
        assert s.street == "flop"
        return s

    def test_check_check_advances_street(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="check"))
        s = apply_action(s, Action(actor="hero", type="check"))
        assert s.street == "turn"
        assert len(s.board) == 4

    def test_bet_call_advances_street(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.street == "turn"
        assert s.pot == 600
        assert s.committed == {"hero": 0, "villain": 0}

    def test_bet_fold_ends_hand(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="fold"))
        assert s.street == "complete"

    def test_bet_raise_call(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=600))
        s = apply_action(s, Action(actor="villain", type="call"))
        assert s.street == "turn"
        assert s.pot == 1_400

    def test_min_bet_is_one_bb(self) -> None:
        s = self._to_flop()
        with pytest.raises(IllegalAction):
            apply_action(s, Action(actor="villain", type="bet", to_amount=50))


class TestAllIn:
    def test_short_allin_preflop_closes_raises(self) -> None:
        # Tiny stack so hero's all-in preflop is less than a full 2bb raise.
        s = start_hand(
            effective_stack=150,
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
            villain_hole=("Qc", "Qh"),
        )
        # stacks: hero 100 (eff 150 - 50 SB), villain 50 (eff 150 - 100 BB).
        # hero all-in: commits 50 + 100 = 150 total. prior_bet was 100. raise_size = 50 < bb.
        s = apply_action(s, Action(actor="hero", type="allin"))
        # Villain can only fold or call — no raise option.
        legal = {la.type for la in legal_actions(s)}
        assert legal == {"fold", "call"}

    def test_allin_call_fast_forwards_to_showdown(self) -> None:
        s = start_hand(effective_stack=1_000, bb=100, button="hero", rng_seed=3)
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        s = apply_action(s, Action(actor="villain", type="allin"))
        assert s.to_act == "hero"
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.pot == 2_000
        assert s.stacks == {"hero": 0, "villain": 0}
        assert s.street == "showdown"
        assert len(s.board) == 5

    def test_allin_both_equal_stacks(self) -> None:
        s = start_hand(effective_stack=500, bb=100, button="villain", rng_seed=5)
        # villain is SB, hero is BB. villain to_act first preflop.
        s = apply_action(s, Action(actor="villain", type="allin"))
        assert s.to_act == "hero"
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.pot == 1_000
        assert s.stacks == {"hero": 0, "villain": 0}
        assert s.street == "showdown"


class TestApplyReveal:
    def _state_with_pending(self, pending: str, board: list[str]) -> GameState:
        """Build a state in a pending_reveal mid-hand posture."""
        deck = [
            # hero, villain holes
            "As","Kd","Qc","Qh",
            # positions 4..8: initial flop/turn/river from seeded deck
            "2c","3d","4h","5s","6c",
            # rest irrelevant
            "7h","8d","9s","Tc","Jd","Qs","Kh","Ac","2s","3h","4d","5c","6d","7c",
            "8s","9h","Th","Jh","Qd","Kc","Ah","2h","3s","4c","5h","6h","7s","8h",
            "9d","Tc","Js","Jc","Kh","Ad","2d","3c",
        ][:52]
        s = start_hand(
            effective_stack=10_000,
            bb=100,
            button="hero",
            hero_hole=("As","Kd"),
            villain_hole=("Qc","Qh"),
            deck_snapshot=deck,
        )
        return s.model_copy(update={
            "pending_reveal": pending,
            "board": list(board),
            "street": {"flop":"flop","turn":"turn","river":"river","runout":"showdown"}[pending],
            "to_act": None,
        })

    def test_reveal_flop_sets_board_and_clears_flag(self) -> None:
        s = self._state_with_pending("flop", [])
        out = apply_reveal(s, ["Ah","Kh","2h"])
        assert out.board == ["Ah","Kh","2h"]
        assert out.pending_reveal is None
        assert out.reveals == [["Ah","Kh","2h"]]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:7] == ["Ah","Kh","2h"]

    def test_reveal_turn_appends_one_card(self) -> None:
        s = self._state_with_pending("turn", ["Ah","Kh","Qh"])
        out = apply_reveal(s, ["2s"])
        assert out.board == ["Ah","Kh","Qh","2s"]
        assert out.pending_reveal is None
        assert out.reveals == [["2s"]]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:8] == ["Ah","Kh","Qh","2s"]

    def test_reveal_runout_from_preflop_allin(self) -> None:
        s = self._state_with_pending("runout", [])
        out = apply_reveal(s, ["Ah","Kh","2h","2s","3s"])
        assert out.board == ["Ah","Kh","2h","2s","3s"]
        assert out.pending_reveal is None
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:9] == ["Ah","Kh","2h","2s","3s"]

    def test_reveal_runout_from_flop_allin_expects_two_cards(self) -> None:
        s = self._state_with_pending("runout", ["Ah","Kh","Qh"])
        out = apply_reveal(s, ["2s","3s"])
        assert out.board == ["Ah","Kh","Qh","2s","3s"]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:9] == ["Ah","Kh","Qh","2s","3s"]

    def test_reveal_rejects_wrong_length(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Kh"])  # need 3
        s2 = self._state_with_pending("runout", ["Ah","Kh","Qh"])
        with pytest.raises(IllegalAction):
            apply_reveal(s2, ["2s","3s","4s"])  # need 2, got 3

    def test_reveal_rejects_duplicate_with_hero_hole(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["As","Kh","Qh"])  # As is hero_hole[0]

    def test_reveal_rejects_duplicate_with_villain_hole(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Qc","Kh","2s"])  # Qc is villain_hole[0]

    def test_reveal_rejects_duplicate_within_cards(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Ah","Qh"])

    def test_reveal_rejects_when_no_pending(self) -> None:
        s = fresh_hand()  # preflop, no pending_reveal
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Kh","Qh"])
