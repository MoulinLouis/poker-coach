"""OpenAI Responses API oracle implementation.

Uses `client.responses.stream(...)` with a forced `submit_advice`
function call and reasoning enabled. Normalizes the SDK's typed stream
events into the provider-agnostic OracleEvent sequence.

GPT-5 reasoning models encrypt their internal chain of thought by
default; we surface the reasoning *summary* via
`reasoning={"effort": ..., "summary": "detailed"}` — summary deltas
arrive as events whose `.type` contains "reasoning" and ends with
".delta". The raw encrypted content is available on the final
response but is not human-readable, so we only log the summary.

Structured output is produced by a strict-mode `submit_advice`
function tool. The final response carries the tool call as an
`output` item of type "function_call" whose `arguments` is a JSON
string.
"""

from __future__ import annotations

import json
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
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT
from poker_coach.oracle.tool_schema import openai_tool_spec
from poker_coach.prompts.renderer import RenderedPrompt


class OpenAIStreamCaller(Protocol):
    """Callable that performs `client.responses.stream(**kwargs)`.

    Returns an async context manager that:
    - when iterated, yields typed Responses API stream events;
    - exposes `get_final_response()` after iteration completes.
    """

    def __call__(self, **kwargs: Any) -> Any: ...


class OpenAIOracle:
    def __init__(
        self,
        stream_caller: OpenAIStreamCaller,
        pricing: PricingSnapshot,
    ) -> None:
        self.stream_caller = stream_caller
        self.pricing = pricing

    async def advise_stream(
        self,
        rendered: RenderedPrompt,
        spec: ModelSpec,
        system_prompt: str | None = None,
    ) -> AsyncIterator[OracleEvent]:
        effective_system = system_prompt if system_prompt is not None else SYSTEM_PROMPT
        kwargs: dict[str, Any] = {
            "model": spec.model_id,
            "instructions": effective_system,
            "input": [{"role": "user", "content": rendered.rendered_prompt}],
            "tools": [openai_tool_spec()],
            "tool_choice": {"type": "function", "name": "submit_advice"},
        }
        if spec.reasoning_effort is not None:
            kwargs["reasoning"] = {
                "effort": spec.reasoning_effort,
                "summary": "detailed",
            }
        if spec.temperature is not None:
            kwargs["temperature"] = spec.temperature

        reasoning_chunks: list[str] = []
        response: Any = None
        try:
            async with self.stream_caller(**kwargs) as stream:
                async for event in stream:
                    etype = getattr(event, "type", "") or ""
                    if "reasoning" in etype and etype.endswith(".delta"):
                        delta = getattr(event, "delta", "") or ""
                        if delta:
                            reasoning_chunks.append(delta)
                            yield ReasoningDelta(text=delta)
                response = await stream.get_final_response()
        except Exception as exc:
            yield OracleError(
                kind="provider_error",
                message=f"{type(exc).__name__}: {exc}",
            )
            return

        if reasoning_chunks:
            yield ReasoningComplete(full_text="".join(reasoning_chunks))

        tool_call = _find_function_call(response)
        if tool_call is None:
            yield OracleError(
                kind="invalid_schema",
                message="no function_call output item in response",
            )
            return

        arguments_raw = getattr(tool_call, "arguments", None)
        try:
            raw_input = _parse_arguments(arguments_raw)
        except (json.JSONDecodeError, TypeError) as exc:
            yield OracleError(
                kind="invalid_schema",
                message=f"could not parse function_call.arguments: {exc}",
                raw_tool_input=None,
            )
            return

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

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        # OpenAI reports reasoning tokens in output_tokens_details.reasoning_tokens.
        details = getattr(usage, "output_tokens_details", None)
        reasoning_tokens = int(
            getattr(details, "reasoning_tokens", 0) or getattr(usage, "reasoning_tokens", 0) or 0
        )
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


def _find_function_call(response: Any) -> Any | None:
    output = getattr(response, "output", []) or []
    for item in output:
        if getattr(item, "type", None) == "function_call":
            return item
    return None


def _parse_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return dict(arguments)
    if isinstance(arguments, str):
        parsed = json.loads(arguments)
        if not isinstance(parsed, dict):
            raise TypeError(f"expected JSON object, got {type(parsed).__name__}")
        return parsed
    raise TypeError(f"unsupported arguments type: {type(arguments).__name__}")


def real_openai_stream_caller(client: Any) -> OpenAIStreamCaller:
    """Adapt an openai.AsyncOpenAI client to the stream_caller protocol."""

    def _call(**kwargs: Any) -> Any:
        return client.responses.stream(**kwargs)

    return _call


__all__ = [
    "OpenAIOracle",
    "OpenAIStreamCaller",
    "real_openai_stream_caller",
]
