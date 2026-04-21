"""Request/response models for the API.

Game state snapshots cross the wire as JSON; we validate them via the
engine's Pydantic GameState to keep a single source of truth.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from poker_coach.engine.models import Action, GameState
from poker_coach.prompts.context import VillainProfile

DecisionStatus = Literal[
    "in_flight",
    "ok",
    "invalid_response",
    "illegal_action",
    "provider_error",
    "cancelled",
    "abandoned",
    "timeout",
]


class CreateSessionRequest(BaseModel):
    mode: Literal["live", "spot"]
    notes: str | None = None


class CreateSessionResponse(BaseModel):
    session_id: str


class CreateHandRequest(BaseModel):
    session_id: str
    bb: int
    ante: int = 0
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
    status: DecisionStatus
    parsed_advice: dict[str, Any] | None
    cost_usd: float | None


class DecisionListRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    created_at: str
    session_id: str
    hand_id: str | None
    model_id: str
    prompt_name: str
    prompt_version: str
    villain_profile: str
    status: DecisionStatus
    parsed_advice: dict[str, Any] | None
    cost_usd: float | None
    latency_ms: int | None


class DecisionDetail(DecisionListRow):
    game_state: dict[str, Any]
    template_hash: str
    template_raw: str
    rendered_prompt: str
    system_prompt_hash: str | None
    reasoning_text: str | None
    raw_tool_input: dict[str, Any] | None
    reasoning_effort: str | None
    thinking_budget: int | None
    temperature: float | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None
    pricing_snapshot: dict[str, Any] | None
    error_message: str | None
    retry_of: str | None
