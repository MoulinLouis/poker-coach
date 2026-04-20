"""Engine-driven RTA runner.

The runner owns the frame-capture → stabilize → engine → decision-gate →
overlay pipeline.  Two entry points:

* ``run_once`` — process a single frame; designed for testing.
* ``run_loop`` — runs forever at ``profile.capture_fps`` Hz, catching all
  exceptions to keep the research-tool alive.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from poker_rta.client.coach_client import CoachClient
from poker_rta.cv.pipeline import FrameObservation
from poker_rta.profile.model import PlatformProfile
from poker_rta.state.decision_gate import should_fire_decision
from poker_rta.state.session import EngineSession
from poker_rta.state.stabilizer import FrameStabilizer

if TYPE_CHECKING:
    from poker_rta.overlay.window import AdviceOverlay


@dataclass
class RunnerDeps:
    grab: Callable[[], np.ndarray]
    observe: Callable[[np.ndarray, PlatformProfile], FrameObservation]
    coach: CoachClient
    overlay: AdviceOverlay
    bb: int
    starting_stack: int
    stable_frames: int = 3
    min_confidence: float = 0.9


@dataclass
class RunnerContext:
    stabilizer: FrameStabilizer
    session: EngineSession
    coach_session_id: str | None = None
    coach_hand_id: str | None = None
    last_fired_state_id: str | None = None


def _state_id(state: dict[str, Any]) -> str:
    return f"{state.get('hand_id')}:{state.get('street')}:{len(state.get('history') or [])}"


async def run_once(
    profile: PlatformProfile,
    deps: RunnerDeps,
    ctx: RunnerContext,
) -> None:
    frame = deps.grab()
    obs = ctx.stabilizer.ingest(deps.observe(frame, profile))
    if obs is None:
        return
    await ctx.session.ingest(obs)
    state = ctx.session.state
    if state is None:
        deps.overlay.set_status("degraded", "no engine state")
        return
    deps.overlay.update_state(state)

    sid = _state_id(state)
    gate = should_fire_decision(
        state=state,
        obs=obs,
        degraded=ctx.session.degraded,
        already_fired_for_state_id=ctx.last_fired_state_id,
        state_id=sid,
        min_confidence=deps.min_confidence,
    )
    if not gate.fire:
        if ctx.session.degraded:
            deps.overlay.set_status("degraded", ctx.session.last_error or "degraded")
        return

    ctx.coach_session_id = ctx.coach_session_id or await deps.coach.create_session(
        mode="live", notes="rta"
    )
    ctx.coach_hand_id = ctx.coach_hand_id or await deps.coach.create_hand(
        session_id=ctx.coach_session_id,
        bb=deps.bb,
        starting_stack=deps.starting_stack,
    )
    deps.overlay.clear_reasoning()
    decision_id = await deps.coach.create_decision(
        session_id=ctx.coach_session_id,
        hand_id=ctx.coach_hand_id,
        game_state=state,
    )
    async for event in deps.coach.stream_decision_events(decision_id):
        if event.type == "reasoning_delta":
            deps.overlay.append_reasoning_delta(event.payload.get("text", ""))
        elif event.type == "tool_call_complete":
            deps.overlay.show_advice(event.payload.get("advice", {}))
            deps.overlay.mark_advice_time()
            deps.overlay.set_status("ok")
        elif event.type == "oracle_error":
            deps.overlay.set_status("error", event.payload.get("message", "oracle error"))
    ctx.last_fired_state_id = sid


async def run_loop(profile: PlatformProfile, deps: RunnerDeps) -> None:
    ctx = RunnerContext(
        stabilizer=FrameStabilizer(stable_frames=deps.stable_frames),
        session=EngineSession(coach=deps.coach, bb=deps.bb),
    )
    period = 1.0 / profile.capture_fps
    while True:
        try:
            await run_once(profile, deps, ctx)
        except Exception as e:
            deps.overlay.set_status("error", f"runner: {e}")
        deps.overlay.tick_staleness()
        await asyncio.sleep(period)


__all__ = [
    "RunnerContext",
    "RunnerDeps",
    "_state_id",
    "run_loop",
    "run_once",
]
