"""Tests for EngineSession — the engine-driven state driver."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from poker_rta.client.coach_client import EngineSnapshot
from poker_rta.state.session import EngineSession


def _make_snap(snap_factory, **overrides):
    """Helper: build an EngineSnapshot from the snap fixture."""
    raw = snap_factory(**overrides)
    return EngineSnapshot(state=raw.state, legal_actions=raw.legal_actions)


# ---------------------------------------------------------------------------
# Test 1: First obs with blinds → engine_start called with correct button/hole
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_obs_with_blinds_calls_engine_start(obs, snap):
    """A first frame with matching blind amounts triggers engine_start with correct params."""
    coach = MagicMock()
    # hero_bet_chips=50 (SB), villain_bet_chips=100 (BB), hero is button
    observation = obs(
        hero_bet_chips=50,
        villain_bet_chips=100,
        hero_stack_chips=9950,
        villain_stack_chips=9900,
        hero_cards=("As", "Kd"),
        board=(),
    )
    returned_snap = _make_snap(snap)
    coach.engine_start = AsyncMock(return_value=returned_snap)

    session = EngineSession(coach=coach, bb=100)
    await session.ingest(observation)

    coach.engine_start.assert_called_once()
    call_kwargs = coach.engine_start.call_args.kwargs
    # hero committed SB (50) → hero is button
    assert call_kwargs["button"] == "hero"
    assert call_kwargs["hero_hole"] == ("As", "Kd")
    assert call_kwargs["bb"] == 100
    assert session.state is not None
    assert not session.degraded


# ---------------------------------------------------------------------------
# Test 2: New board cards observed → engine_reveal called with new cards only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_new_board_cards_calls_engine_reveal(obs, snap):
    """When board grows from 0 to 3 cards, engine_reveal is called with the 3 new cards."""
    coach = MagicMock()

    # Start session with an existing preflop state (no board)
    preflop_snap = _make_snap(snap, board=[], street="preflop")
    flop_snap = _make_snap(snap, board=["Ah", "7c", "2d"], street="flop")

    coach.engine_reveal = AsyncMock(return_value=flop_snap)
    coach.engine_apply = AsyncMock()

    session = EngineSession(coach=coach, bb=100)
    session.state = preflop_snap.state
    session.legal_actions = preflop_snap.legal_actions
    # Prev obs had no board; now we see flop cards
    session._prev_obs = obs(board=())

    flop_obs = obs(
        board=("Ah", "7c", "2d"),
        hero_bet_chips=0,
        villain_bet_chips=0,
    )
    await session.ingest(flop_obs)

    coach.engine_reveal.assert_called_once()
    reveal_kwargs = coach.engine_reveal.call_args.kwargs
    # Only the 3 new cards should be passed (had 0, now 3)
    assert reveal_kwargs["cards"] == ["Ah", "7c", "2d"]


# ---------------------------------------------------------------------------
# Test 3: engine_apply raising ValueError → session degraded, last_error set
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_engine_apply_value_error_degrades_session(obs, snap):
    """If engine_apply raises ValueError, the session is marked degraded with last_error set."""
    coach = MagicMock()

    # Session has state with hero to act
    active_snap = _make_snap(
        snap,
        to_act="hero",
        committed={"hero": 100, "villain": 100},
        street="flop",
    )
    coach.engine_apply = AsyncMock(side_effect=ValueError("illegal action: fold not available"))

    session = EngineSession(coach=coach, bb=100)
    session.state = active_snap.state
    session.legal_actions = active_snap.legal_actions
    session._prev_obs = obs(hero_bet_chips=100, villain_bet_chips=100, board=())

    # Observation with hero committing more (triggers infer_action → call/raise)
    bad_obs = obs(
        hero_bet_chips=200,
        villain_bet_chips=100,
        hero_stack_chips=9750,
        villain_stack_chips=9900,
        board=(),
    )
    await session.ingest(bad_obs)

    assert session.degraded
    assert session.last_error == "illegal action: fold not available"


# ---------------------------------------------------------------------------
# Test 4: Moving to new hand while prior state was mid-action → fold fires first
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fold_emitted_before_engine_start_on_hand_boundary(obs, snap):
    """When a new hand is detected while a hand is in progress, a terminal fold fires first."""
    coach = MagicMock()

    # Existing mid-hand state: hero to act on flop
    mid_hand_snap = _make_snap(
        snap,
        street="flop",
        to_act="hero",
        committed={"hero": 50, "villain": 100},
    )
    fold_snap = _make_snap(snap, street="complete", to_act=None)
    new_hand_snap = _make_snap(
        snap,
        hand_id="h2",
        street="preflop",
        committed={"hero": 50, "villain": 100},
    )

    call_order: list[str] = []

    async def fake_apply(**kwargs):
        call_order.append("apply")
        return fold_snap

    async def fake_start(**kwargs):
        call_order.append("start")
        return new_hand_snap

    coach.engine_apply = AsyncMock(side_effect=fake_apply)
    coach.engine_start = AsyncMock(side_effect=fake_start)

    session = EngineSession(coach=coach, bb=100)
    session.state = mid_hand_snap.state
    session.legal_actions = mid_hand_snap.legal_actions
    # prev_obs had no board and same hero cards (so same hand detection won't fire on it)
    session._prev_obs = None

    # New hand observation: different hole cards (Qh Jd), fresh blinds
    new_hand_obs = obs(
        hero_cards=("Qh", "Jd"),
        hero_bet_chips=50,
        villain_bet_chips=100,
        hero_stack_chips=9950,
        villain_stack_chips=9900,
        board=(),
    )
    await session.ingest(new_hand_obs)

    # fold (engine_apply) must come before engine_start
    assert "apply" in call_order
    assert "start" in call_order
    assert call_order.index("apply") < call_order.index("start")

    # The fold action sent to engine_apply should be a fold
    apply_kwargs = coach.engine_apply.call_args_list[0].kwargs
    assert apply_kwargs["action"]["type"] == "fold"
    assert apply_kwargs["action"]["actor"] == "hero"
