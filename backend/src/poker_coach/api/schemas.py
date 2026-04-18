"""Request/response models for the API.

Game state snapshots cross the wire as JSON; we validate them via the
engine's Pydantic GameState to keep a single source of truth.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from poker_coach.engine.models import Action, GameState
from poker_coach.prompts.context import VillainProfile


class CreateSessionRequest(BaseModel):
    mode: Literal["live", "spot"]
    notes: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str


class CreateHandRequest(BaseModel):
    session_id: str
    bb: int
    effective_stack_start: int
    rng_seed: int | None = None
    deck_snapshot: list[str] | None = None


class CreateHandResponse(BaseModel):
    hand_id: str


class CreateDecisionRequest(BaseModel):
    session_id: str
    hand_id: str | None = None
    model_preset: str
    prompt_name: str
    prompt_version: str
    game_state: GameState
    retry_of: str | None = None
    villain_profile: VillainProfile = "unknown"


class CreateDecisionResponse(BaseModel):
    decision_id: str


class RecordActionRequest(BaseModel):
    decision_id: str
    action: Action


class RecordActionResponse(BaseModel):
    id: int


class DecisionSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    decision_id: str
    status: str
    parsed_advice: dict[str, Any] | None
    cost_usd: float | None
