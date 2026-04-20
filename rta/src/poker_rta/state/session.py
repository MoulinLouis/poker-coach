from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from poker_rta.client.coach_client import CoachClient, EngineSnapshot
from poker_rta.cv.pipeline import FrameObservation
from poker_rta.state.action_infer import infer_action
from poker_rta.state.hand_start import detect_hand_start

Seat = Literal["hero", "villain"]


@dataclass
class EngineSession:
    coach: CoachClient
    bb: int
    state: dict[str, Any] | None = None
    legal_actions: list[dict[str, Any]] = field(default_factory=list)
    degraded: bool = False
    last_error: str | None = None
    _prev_obs: FrameObservation | None = None

    async def ingest(self, obs: FrameObservation) -> None:
        start = detect_hand_start(prev=self._prev_obs, current=obs, bb=self.bb)
        if start is not None:
            await self._maybe_emit_terminal_fold()
            snap = await self.coach.engine_start(
                effective_stack=start.effective_stack,
                bb=start.bb,
                button=start.button,
                hero_hole=start.hero_hole,
            )
            self._apply(snap)
            self._prev_obs, self.degraded, self.last_error = obs, False, None
            return
        if self.state is None or self.degraded:
            self._prev_obs = obs
            return
        # Reveal new board cards, if any
        seen = list(obs.board)
        have = list(self.state.get("board") or [])
        if len(seen) > len(have):
            try:
                snap = await self.coach.engine_reveal(state=self.state, cards=seen[len(have) :])
                self._apply(snap)
            except ValueError as e:
                self._degrade(str(e))
                return
        # Infer action for whoever is to_act
        actor = self.state.get("to_act")
        if actor not in ("hero", "villain"):
            self._prev_obs = obs
            return
        action = infer_action(
            prev_state=self.state,
            actor=actor,
            obs_committed={"hero": obs.hero_bet_chips or 0, "villain": obs.villain_bet_chips or 0},
            obs_stacks={"hero": obs.hero_stack_chips or 0, "villain": obs.villain_stack_chips or 0},
        )
        if action is not None:
            try:
                snap = await self.coach.engine_apply(state=self.state, action=action)
                self._apply(snap)
            except ValueError as e:
                self._degrade(str(e))
                return
        self._prev_obs = obs

    async def _maybe_emit_terminal_fold(self) -> None:
        """When leaving mid-hand into a new hand, attribute fold to the to_act player."""
        if self.state is None or self.degraded:
            return
        if self.state.get("street") in (None, "complete", "showdown"):
            return
        actor = self.state.get("to_act")
        if actor not in ("hero", "villain"):
            return
        try:
            snap = await self.coach.engine_apply(
                state=self.state,
                action={"actor": actor, "type": "fold", "to_amount": None},
            )
            self._apply(snap)
        except ValueError:
            pass  # couldn't reconstruct — prior hand log incomplete; new hand still starts clean

    def _apply(self, snap: EngineSnapshot) -> None:
        self.state, self.legal_actions = snap.state, snap.legal_actions

    def _degrade(self, msg: str) -> None:
        self.degraded, self.last_error = True, msg
