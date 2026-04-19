"""Server-side engine endpoints.

Client owns the current game state as a React prop; when the user takes
an action it POSTs the state + action here, the backend runs the
authoritative apply_action, and returns (new_state, legal_actions).
Keeps the HU NLHE rules single-sourced in Python — no TypeScript
re-implementation to drift.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from poker_coach.engine.models import Action, GameState, LegalAction, Seat
from poker_coach.engine.rules import (
    IllegalAction,
    apply_action,
    apply_reveal,
    legal_actions,
    start_hand,
)

router = APIRouter()


class StartHandRequest(BaseModel):
    effective_stack: int
    bb: int
    button: Seat
    hero_hole: tuple[str, str] | None = None
    villain_hole: tuple[str, str] | None = None
    rng_seed: int | None = None
    deck_snapshot: list[str] | None = None


class EngineSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: GameState
    legal_actions: list[LegalAction]


class ApplyActionRequest(BaseModel):
    state: GameState
    action: Action


@router.post("/engine/start", response_model=EngineSnapshot)
def start(body: StartHandRequest) -> EngineSnapshot:
    state = start_hand(
        effective_stack=body.effective_stack,
        bb=body.bb,
        button=body.button,
        hero_hole=body.hero_hole,
        villain_hole=body.villain_hole,
        rng_seed=body.rng_seed,
        deck_snapshot=body.deck_snapshot,
    )
    return EngineSnapshot(state=state, legal_actions=legal_actions(state))


class RevealRequest(BaseModel):
    state: GameState
    cards: list[str]


@router.post("/engine/reveal", response_model=EngineSnapshot)
def reveal(body: RevealRequest) -> EngineSnapshot:
    try:
        new_state = apply_reveal(body.state, body.cards)
    except IllegalAction as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineSnapshot(state=new_state, legal_actions=legal_actions(new_state))


@router.post("/engine/apply", response_model=EngineSnapshot)
def apply(body: ApplyActionRequest) -> EngineSnapshot:
    try:
        new_state = apply_action(body.state, body.action)
    except IllegalAction as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineSnapshot(state=new_state, legal_actions=legal_actions(new_state))
