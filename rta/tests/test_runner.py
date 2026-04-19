"""End-to-end tests for the engine-driven runner (runner.py).

Uses mocks for CoachClient and AdviceOverlay so Qt/GPU are never touched.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from poker_rta.client.coach_client import SSEEvent
from poker_rta.cv.pipeline import FrameObservation
from poker_rta.runner import RunnerContext, RunnerDeps, _state_id, run_once
from poker_rta.state.session import EngineSession
from poker_rta.state.stabilizer import FrameStabilizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_obs(**kw: Any) -> FrameObservation:
    base: dict[str, Any] = {
        "hero_cards": ("As", "Kd"),
        "board": (),
        "pot_chips": 150,
        "hero_stack_chips": 9950,
        "villain_stack_chips": 9900,
        "hero_bet_chips": 50,
        "villain_bet_chips": 100,
        "hero_is_button": True,
        "hero_to_act": True,
        "visible_buttons": frozenset({"fold", "call", "raise"}),
        "confidence": {},
    }
    base.update(kw)
    return FrameObservation(**base)  # type: ignore[arg-type]


def _make_state(**kw: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "hand_id": "h1",
        "bb": 100,
        "effective_stack": 10000,
        "button": "hero",
        "hero_hole": ["As", "Kd"],
        "villain_hole": None,
        "board": [],
        "street": "preflop",
        "stacks": {"hero": 9950, "villain": 9900},
        "committed": {"hero": 50, "villain": 100},
        "pot": 0,
        "to_act": "hero",
        "last_aggressor": "villain",
        "last_raise_size": 100,
        "raises_open": True,
        "acted_this_street": [],
        "history": [],
        "rng_seed": None,
        "deck_snapshot": None,
        "pending_reveal": None,
        "reveals": [],
    }
    state.update(kw)
    return state


def _make_fake_profile() -> MagicMock:
    profile = MagicMock()
    profile.capture_fps = 5.0
    return profile


# ---------------------------------------------------------------------------
# Test: stabilizer only emits on the 3rd identical frame
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stabilizer_gates_first_two_frames() -> None:
    """First 2 identical frames must NOT fire a decision; 3rd should."""
    obs = _make_obs()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    state = _make_state()

    # --- mock coach --------------------------------------------------------
    coach = MagicMock()
    coach.create_session = AsyncMock(return_value="sess-1")
    coach.create_hand = AsyncMock(return_value="hand-1")
    coach.create_decision = AsyncMock(return_value="dec-1")

    async def fake_stream_events(decision_id: str):  # type: ignore[return]
        yield SSEEvent(type="reasoning_delta", payload={"text": "a"})
        yield SSEEvent(type="reasoning_delta", payload={"text": "b"})
        yield SSEEvent(
            type="tool_call_complete",
            payload={"advice": {"action": "raise", "to_bb": 3.0}},
        )

    coach.stream_decision_events = fake_stream_events
    coach.engine_start = AsyncMock(return_value=MagicMock(state=state, legal_actions=[]))

    # --- mock session so ingest sets state immediately ---------------------
    session = MagicMock(spec=EngineSession)
    session.state = state
    session.degraded = False
    session.last_error = None
    session.ingest = AsyncMock()

    # --- mock overlay ------------------------------------------------------
    overlay = MagicMock()

    deps = RunnerDeps(
        grab=lambda: frame,
        observe=lambda _f, _p: obs,
        coach=coach,
        overlay=overlay,
        bb=100,
        starting_stack=10000,
        stable_frames=3,
        min_confidence=0.0,  # no confidence threshold for this test
    )
    profile = _make_fake_profile()
    ctx = RunnerContext(
        stabilizer=FrameStabilizer(stable_frames=3),
        session=session,
    )

    # Frame 1 — stabilizer returns None → should NOT reach coach calls
    await run_once(profile, deps, ctx)
    coach.create_decision.assert_not_called()

    # Frame 2 — still not stable
    await run_once(profile, deps, ctx)
    coach.create_decision.assert_not_called()

    # Frame 3 — stable; gate fires
    await run_once(profile, deps, ctx)
    coach.create_decision.assert_called_once()


# ---------------------------------------------------------------------------
# Test: full happy-path — all assertions from the spec
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_once_full_happy_path() -> None:
    """Full path: create_session, create_hand, create_decision called once;
    append_reasoning_delta called twice; show_advice called once on tool_call_complete."""

    obs = _make_obs()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    state = _make_state()

    # --- mock coach --------------------------------------------------------
    coach = MagicMock()
    coach.create_session = AsyncMock(return_value="sess-1")
    coach.create_hand = AsyncMock(return_value="hand-1")
    coach.create_decision = AsyncMock(return_value="dec-1")

    async def fake_stream_events(decision_id: str):  # type: ignore[return]
        yield SSEEvent(type="reasoning_delta", payload={"text": "a"})
        yield SSEEvent(type="reasoning_delta", payload={"text": "b"})
        yield SSEEvent(
            type="tool_call_complete",
            payload={"advice": {"action": "raise", "to_bb": 3.0}},
        )

    coach.stream_decision_events = fake_stream_events

    # --- mock session with state already populated ------------------------
    session = MagicMock(spec=EngineSession)
    session.state = state
    session.degraded = False
    session.last_error = None
    session.ingest = AsyncMock()

    # --- mock overlay ------------------------------------------------------
    overlay = MagicMock()

    deps = RunnerDeps(
        grab=lambda: frame,
        # observe always returns the same obs → stabilizer emits on 3rd call
        observe=lambda _f, _p: obs,
        coach=coach,
        overlay=overlay,
        bb=100,
        starting_stack=10000,
        stable_frames=3,
        min_confidence=0.0,
    )
    profile = _make_fake_profile()
    ctx = RunnerContext(
        stabilizer=FrameStabilizer(stable_frames=3),
        session=session,
    )

    # Pump 3 times so the stabilizer emits on the 3rd
    await run_once(profile, deps, ctx)
    await run_once(profile, deps, ctx)
    await run_once(profile, deps, ctx)

    # create_session / create_hand / create_decision each called exactly once
    coach.create_session.assert_called_once_with(mode="live", notes="rta")
    coach.create_hand.assert_called_once_with(session_id="sess-1", bb=100, starting_stack=10000)
    coach.create_decision.assert_called_once()

    # overlay received 2 reasoning deltas
    assert overlay.append_reasoning_delta.call_count == 2
    overlay.append_reasoning_delta.assert_any_call("a")
    overlay.append_reasoning_delta.assert_any_call("b")

    # show_advice called once with the advice dict
    overlay.show_advice.assert_called_once_with({"action": "raise", "to_bb": 3.0})
    overlay.mark_advice_time.assert_called_once()


# ---------------------------------------------------------------------------
# Test: second identical stable transition does NOT re-fire
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_once_no_double_fire_same_state() -> None:
    """Once a decision fires for a given state_id, repeated calls with the same
    stable obs must not fire again."""

    obs = _make_obs()
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    state = _make_state()

    coach = MagicMock()
    coach.create_session = AsyncMock(return_value="sess-1")
    coach.create_hand = AsyncMock(return_value="hand-1")
    coach.create_decision = AsyncMock(return_value="dec-1")

    async def fake_stream_events(decision_id: str):  # type: ignore[return]
        yield SSEEvent(
            type="tool_call_complete",
            payload={"advice": {"action": "call"}},
        )

    coach.stream_decision_events = fake_stream_events

    session = MagicMock(spec=EngineSession)
    session.state = state
    session.degraded = False
    session.last_error = None
    session.ingest = AsyncMock()

    overlay = MagicMock()

    deps = RunnerDeps(
        grab=lambda: frame,
        observe=lambda _f, _p: obs,
        coach=coach,
        overlay=overlay,
        bb=100,
        starting_stack=10000,
        stable_frames=3,
        min_confidence=0.0,
    )
    profile = _make_fake_profile()
    ctx = RunnerContext(
        stabilizer=FrameStabilizer(stable_frames=3),
        session=session,
    )

    # First burst: 3 frames → fires once
    await run_once(profile, deps, ctx)
    await run_once(profile, deps, ctx)
    await run_once(profile, deps, ctx)
    assert coach.create_decision.call_count == 1

    # Stabilizer won't re-emit same obs, so more calls → no more fires
    await run_once(profile, deps, ctx)
    await run_once(profile, deps, ctx)
    assert coach.create_decision.call_count == 1


# ---------------------------------------------------------------------------
# Test: _state_id helper
# ---------------------------------------------------------------------------


def test_state_id_format() -> None:
    state = _make_state(hand_id="h42", street="flop", history=["a", "b"])
    assert _state_id(state) == "h42:flop:2"


def test_state_id_no_history() -> None:
    state = _make_state(hand_id="h1", street="preflop", history=[])
    assert _state_id(state) == "h1:preflop:0"
