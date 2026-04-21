"""Oracle protocol and event types — provider-agnostic interface.

Each provider implementation streams a normalized OracleEvent sequence.
The backend re-emits these as SSE frames to the frontend. Reasoning
streams first; the tool call lands as ToolCallComplete; UsageComplete
is the final event on a successful run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from poker_coach.engine.models import ActionType
from poker_coach.prompts.renderer import RenderedPrompt

ProviderName = Literal["openai", "anthropic"]
ReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh"]
Confidence = Literal["low", "medium", "high"]


class StrategyEntry(BaseModel):
    """One entry in a mixed strategy output.

    Multiple entries with the same `action` but different `to_amount_bb`
    are allowed (polarized sizings). `to_amount_bb` is `None` for
    fold / check / call / allin.
    """

    model_config = ConfigDict(frozen=True)

    action: ActionType
    to_amount_bb: float | None = None
    frequency: float


class Advice(BaseModel):
    """Parsed output of the submit_advice tool call."""

    model_config = ConfigDict(frozen=True)

    action: ActionType
    to_amount_bb: float | None = None
    reasoning: str
    confidence: Confidence
    strategy: list[StrategyEntry] | None = None


ThinkingMode = Literal["enabled", "adaptive"]


class ModelSpec(BaseModel):
    """A (provider, model, effort) preset selected from the UI.

    Anthropic has two thinking API shapes:

    - `thinking_mode="enabled"`: legacy, takes `thinking_budget` tokens.
      Used by Haiku 4.5 (no thinking) and Sonnet 4.6.
    - `thinking_mode="adaptive"`: Opus 4.7 and forward. Effort level
      comes via `output_config.effort`; `reasoning_effort` on the spec
      maps to that value. `thinking_budget` is ignored.
    """

    model_config = ConfigDict(frozen=True)

    selector_id: str
    provider: ProviderName
    model_id: str
    reasoning_effort: ReasoningEffort | None = None
    thinking_budget: int | None = None
    thinking_mode: ThinkingMode | None = None
    temperature: float | None = None


class ReasoningDelta(BaseModel):
    type: Literal["reasoning_delta"] = "reasoning_delta"
    text: str


class ReasoningComplete(BaseModel):
    type: Literal["reasoning_complete"] = "reasoning_complete"
    full_text: str


class ToolCallComplete(BaseModel):
    type: Literal["tool_call_complete"] = "tool_call_complete"
    advice: Advice
    raw_tool_input: dict[str, Any]


class UsageComplete(BaseModel):
    type: Literal["usage_complete"] = "usage_complete"
    input_tokens: int  # total billable input = uncached + cache_write + cache_read
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    cost_usd: float
    pricing_snapshot: dict[str, Any]
    # Anthropic prompt-cache breakdown; both zero on providers/sessions without cache.
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


OracleErrorKind = Literal[
    "provider_error",
    "invalid_schema",
    "illegal_action",
    "internal",
]


class OracleError(BaseModel):
    type: Literal["oracle_error"] = "oracle_error"
    kind: OracleErrorKind
    message: str
    raw_tool_input: dict[str, Any] | None = None


OracleEvent = ReasoningDelta | ReasoningComplete | ToolCallComplete | UsageComplete | OracleError


class Oracle(Protocol):
    def advise_stream(
        self,
        rendered: RenderedPrompt,
        spec: ModelSpec,
        system_prompt: str | None = None,
    ) -> AsyncIterator[OracleEvent]: ...
