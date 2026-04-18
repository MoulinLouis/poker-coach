from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from poker_coach.engine.models import Action, GameState, Seat
from poker_coach.engine.rules import (
    IllegalAction,
    apply_action,
    apply_reveal,
    initial_state,
    legal_actions,
    replay,
    start_hand,
)

STREET_ORDER = ["preflop", "flop", "turn", "river", "showdown", "complete"]
_RUNOUT_POOL = ["2c","3d","5s","6h","7c","8d","9h","Tc","Jd","Qs","Kh","Ac","2s","3h","4d","5c","6d","7c",
                "8s","9d","Th","Jh","Qd","Kc","Ah","2h","4c","5h","6c","7s","8h","Ts","Js","Qc","Ks","Ad"]


def _initial_total_chips(state: GameState) -> int:
    return 2 * state.effective_stack


def _chips_accounted(state: GameState) -> int:
    return sum(state.stacks.values()) + state.pot + sum(state.committed.values())


def _pick_action(draw: st.DrawFn, state: GameState) -> Action:
    legal = legal_actions(state)
    assert legal, "legal_actions must be non-empty when to_act is set"
    la = draw(st.sampled_from(legal))
    actor: Seat = state.to_act  # type: ignore[assignment]
    if la.type in ("bet", "raise"):
        assert la.min_to is not None and la.max_to is not None
        amount = draw(st.integers(min_value=la.min_to, max_value=la.max_to))
        return Action(actor=actor, type=la.type, to_amount=amount)
    return Action(actor=actor, type=la.type)


def _safe_runout_cards(state: GameState, n: int) -> list[str]:
    """Pick n distinct cards not already in state.hero_hole / villain_hole / board."""
    excluded: set[str] = set(state.hero_hole)
    if state.villain_hole is not None:
        excluded.update(state.villain_hole)
    excluded.update(state.board)
    picked: list[str] = []
    for card in _RUNOUT_POOL:
        if len(picked) == n:
            break
        if card not in excluded and card not in picked:
            picked.append(card)
    if len(picked) < n:
        raise AssertionError("runout pool exhausted; add more cards")
    return picked


@st.composite
def played_hand(draw: st.DrawFn) -> list[GameState]:
    """Strategy: play a full hand using only legal actions, returning the
    sequence of states visited (including start and terminal).
    """
    effective_stack = draw(st.integers(min_value=200, max_value=50_000))
    bb = draw(st.sampled_from([100, 200, 1_000]))
    if effective_stack <= bb:
        effective_stack = bb + bb
    button: Seat = draw(st.sampled_from(["hero", "villain"]))
    rng_seed = draw(st.integers(min_value=0, max_value=2**30))

    state = start_hand(
        effective_stack=effective_stack,
        bb=bb,
        button=button,
        rng_seed=rng_seed,
    )
    visited = [state]
    for _ in range(100):
        if state.street in ("showdown", "complete") and state.pending_reveal is None:
            break
        if state.pending_reveal is not None:
            need = 5 - len(state.board) if state.pending_reveal == "runout" else {
                "flop": 3, "turn": 1, "river": 1,
            }[state.pending_reveal]
            state = apply_reveal(state, _safe_runout_cards(state, need))
            visited.append(state)
            continue
        action = _pick_action(draw, state)
        state = apply_action(state, action)
        visited.append(state)
    return visited


settings.register_profile(
    "engine",
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile("engine")


@given(states=played_hand())
def test_chip_conservation(states: list[GameState]) -> None:
    total = _initial_total_chips(states[0])
    for state in states:
        assert _chips_accounted(state) == total, (
            f"chip mismatch: expected {total}, got {_chips_accounted(state)} at {state.street}"
        )


@given(states=played_hand())
def test_street_monotonicity(states: list[GameState]) -> None:
    prev_idx = -1
    for state in states:
        idx = STREET_ORDER.index(state.street)
        assert idx >= prev_idx, f"street regressed from {STREET_ORDER[prev_idx]} to {state.street}"
        prev_idx = idx


@given(states=played_hand())
def test_to_act_consistency(states: list[GameState]) -> None:
    for state in states:
        if state.street in ("showdown", "complete") or state.pending_reveal is not None:
            assert state.to_act is None
            assert legal_actions(state) == []
        else:
            assert state.to_act is not None
            assert legal_actions(state), f"no legal actions for {state.to_act} at {state.street}"


@given(states=played_hand())
def test_illegal_action_unreachable(states: list[GameState]) -> None:
    """Any action not in legal_actions must raise IllegalAction."""
    for state in states:
        if state.street in ("showdown", "complete") or state.pending_reveal is not None:
            continue
        legal_types = {la.type for la in legal_actions(state)}
        all_types = {"fold", "check", "call", "bet", "raise", "allin"}
        for illegal_type in all_types - legal_types:
            try:
                apply_action(
                    state,
                    Action(actor=state.to_act, type=illegal_type),  # type: ignore[arg-type]
                )
            except IllegalAction:
                continue
            raise AssertionError(f"illegal action {illegal_type} was accepted at {state.street}")


@given(states=played_hand())
def test_replay_idempotency(states: list[GameState]) -> None:
    final = states[-1]
    assert replay(final) == final


@given(states=played_hand())
def test_deck_snapshot_matches_board(states: list[GameState]) -> None:
    for state in states:
        if state.deck_snapshot is None:
            continue
        board_len = len(state.board)
        assert state.deck_snapshot[4 : 4 + board_len] == state.board, (
            f"deck_snapshot[4:{4+board_len}] != state.board at {state.street}"
        )
