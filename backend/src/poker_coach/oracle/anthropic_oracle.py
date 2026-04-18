"""Anthropic Messages API oracle implementation.

Uses `client.messages.stream(...)` with thinking enabled and forced
`submit_advice` tool use. Normalizes the SDK's typed stream events
into the provider-agnostic OracleEvent sequence.

The oracle takes a `stream_caller` callable rather than a client so
tests can inject a fake that yields pre-constructed events. In
production wire it via `real_anthropic_stream_caller(client)`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

from pydantic import ValidationError

from poker_coach.oracle.base import (
    Advice,
    ModelSpec,
    OracleError,
    OracleEvent,
    ReasoningComplete,
    ReasoningDelta,
    ToolCallComplete,
    UsageComplete,
)
from poker_coach.oracle.pricing import PricingSnapshot, compute_cost
from poker_coach.oracle.tool_schema import anthropic_tool_spec
from poker_coach.prompts.renderer import RenderedPrompt


class AnthropicStreamCaller(Protocol):
    """Callable that performs `client.messages.stream(**kwargs)`.

    Returns an async context manager that:
    - when iterated, yields typed stream events from the Anthropic SDK;
    - exposes `get_final_message()` after iteration completes.
    """

    def __call__(self, **kwargs: Any) -> Any: ...


class AnthropicOracle:
    def __init__(
        self,
        stream_caller: AnthropicStreamCaller,
        pricing: PricingSnapshot,
        max_output_tokens: int = 4096,
    ) -> None:
        self.stream_caller = stream_caller
        self.pricing = pricing
        self.max_output_tokens = max_output_tokens

    async def advise_stream(
        self, rendered: RenderedPrompt, spec: ModelSpec
    ) -> AsyncIterator[OracleEvent]:
        # Anthropic requires max_tokens > thinking.budget_tokens (thinking
        # tokens count against max_tokens). Give the tool-call output
        # enough headroom beyond the thinking budget.
        tool_headroom = 2048
        max_tokens = self.max_output_tokens
        if spec.thinking_budget is not None:
            max_tokens = max(max_tokens, spec.thinking_budget + tool_headroom)

        request_kwargs: dict[str, Any] = {
            "model": spec.model_id,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": rendered.rendered_prompt}],
            "tools": [anthropic_tool_spec()],
        }
        # Anthropic rejects tool_choice={"type": "tool"} / "any" when thinking
        # is enabled. With a single tool + an explicit prompt instruction to
        # call it, "auto" gets the tool call in practice without the 400.
        if spec.thinking_budget is not None:
            request_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": spec.thinking_budget,
            }
            request_kwargs["tool_choice"] = {"type": "auto"}
        else:
            request_kwargs["tool_choice"] = {"type": "tool", "name": "submit_advice"}
        if spec.temperature is not None:
            request_kwargs["temperature"] = spec.temperature

        thinking_chunks: list[str] = []
        message: Any = None
        try:
            async with self.stream_caller(**request_kwargs) as stream:
                async for event in stream:
                    if getattr(event, "type", None) != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    if delta is None:
                        continue
                    if getattr(delta, "type", None) == "thinking_delta":
                        text = getattr(delta, "thinking", "")
                        if text:
                            thinking_chunks.append(text)
                            yield ReasoningDelta(text=text)
                message = stream.get_final_message()
        except Exception as exc:
            yield OracleError(
                kind="provider_error",
                message=f"{type(exc).__name__}: {exc}",
            )
            return

        if thinking_chunks:
            yield ReasoningComplete(full_text="".join(thinking_chunks))

        tool_use_block = _find_tool_use(message)
        if tool_use_block is None:
            yield OracleError(kind="invalid_schema", message="no tool_use block in response")
            return

        raw_input = _coerce_tool_input(tool_use_block)
        try:
            advice = Advice.model_validate(raw_input)
        except ValidationError as exc:
            yield OracleError(
                kind="invalid_schema",
                message=str(exc),
                raw_tool_input=raw_input,
            )
            return

        yield ToolCallComplete(advice=advice, raw_tool_input=raw_input)

        usage = getattr(message, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        # Anthropic bills thinking tokens as part of output_tokens; we surface
        # the thinking slice separately when available but still count it
        # against output for cost.
        reasoning_tokens = int(getattr(usage, "thinking_tokens", 0) or 0)
        total_tokens = input_tokens + output_tokens
        cost, snapshot = compute_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_id=spec.model_id,
            pricing=self.pricing,
        )
        yield UsageComplete(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            pricing_snapshot=snapshot,
        )


def _find_tool_use(message: Any) -> Any | None:
    content = getattr(message, "content", []) or []
    for block in content:
        if getattr(block, "type", None) == "tool_use":
            return block
    return None


def _coerce_tool_input(block: Any) -> dict[str, Any]:
    raw = getattr(block, "input", {}) or {}
    if isinstance(raw, dict):
        return dict(raw)
    # Some SDK shapes return a pydantic model for input; coerce to dict.
    if hasattr(raw, "model_dump"):
        return dict(raw.model_dump())
    return dict(raw)


def real_anthropic_stream_caller(client: Any) -> AnthropicStreamCaller:
    """Adapt an anthropic.AsyncAnthropic client to the stream_caller protocol."""

    def _call(**kwargs: Any) -> Any:
        return client.messages.stream(**kwargs)

    return _call


__all__ = [
    "AnthropicOracle",
    "AnthropicStreamCaller",
    "real_anthropic_stream_caller",
]
