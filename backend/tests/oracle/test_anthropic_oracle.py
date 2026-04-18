from typing import Any

import pytest

from poker_coach.oracle.anthropic_oracle import AnthropicOracle
from poker_coach.oracle.base import (
    Advice,
    ModelSpec,
    OracleError,
    ReasoningComplete,
    ReasoningDelta,
    ToolCallComplete,
    UsageComplete,
)
from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot
from poker_coach.prompts.renderer import RenderedPrompt

from .fixtures import (
    FakeContentBlock,
    FakeMessage,
    FakeStreamEvent,
    FakeUsage,
    fake_stream_caller,
    thinking_event,
    tool_use_block,
)


def sample_pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_date="2026-04-18",
        snapshot_source="test",
        models={
            "claude-opus-4-7": PricingEntry(input_per_mtok=15.0, output_per_mtok=75.0),
        },
    )


def sample_spec() -> ModelSpec:
    return ModelSpec(
        selector_id="claude-opus-4-7-deep",
        provider="anthropic",
        model_id="claude-opus-4-7",
        thinking_budget=4096,
        temperature=1.0,
    )


def sample_rendered() -> RenderedPrompt:
    return RenderedPrompt(
        pack="coach",
        version="v1",
        template_hash="a" * 64,
        template_raw="---\nname: coach\nversion: v1\n---\nprompt body",
        rendered_prompt="prompt body",
        variables={},
    )


async def collect(oracle: AnthropicOracle) -> list[Any]:
    return [event async for event in oracle.advise_stream(sample_rendered(), sample_spec())]


@pytest.mark.asyncio
async def test_happy_path_streams_reasoning_then_tool_then_usage() -> None:
    events = [
        thinking_event("First I "),
        thinking_event("consider pot odds."),
    ]
    message = FakeMessage(
        content=[
            FakeContentBlock(type="thinking", input=None),
            tool_use_block(
                {
                    "action": "raise",
                    "to_amount_bb": 8.0,
                    "reasoning": "Value raise with top pair, strong kicker.",
                    "confidence": "high",
                }
            ),
        ],
        usage=FakeUsage(input_tokens=1_200, output_tokens=450, thinking_tokens=300),
    )
    oracle = AnthropicOracle(fake_stream_caller(events, message), sample_pricing())

    emitted = await collect(oracle)

    kinds = [type(e).__name__ for e in emitted]
    assert kinds == [
        "ReasoningDelta",
        "ReasoningDelta",
        "ReasoningComplete",
        "ToolCallComplete",
        "UsageComplete",
    ]

    assert isinstance(emitted[0], ReasoningDelta) and emitted[0].text == "First I "
    assert isinstance(emitted[1], ReasoningDelta) and emitted[1].text == "consider pot odds."
    assert isinstance(emitted[2], ReasoningComplete)
    assert emitted[2].full_text == "First I consider pot odds."

    tool = emitted[3]
    assert isinstance(tool, ToolCallComplete)
    assert tool.advice == Advice(
        action="raise",
        to_amount_bb=8.0,
        reasoning="Value raise with top pair, strong kicker.",
        confidence="high",
    )

    usage = emitted[4]
    assert isinstance(usage, UsageComplete)
    assert usage.input_tokens == 1_200
    assert usage.output_tokens == 450
    assert usage.reasoning_tokens == 300
    assert usage.total_tokens == 1_650
    # 1200/1M * 15 + 450/1M * 75 = 0.018 + 0.03375 = 0.05175
    assert round(usage.cost_usd, 5) == 0.05175
    assert usage.pricing_snapshot["model_id"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_missing_tool_block_emits_invalid_schema() -> None:
    message = FakeMessage(
        content=[FakeContentBlock(type="text", input=None)],
        usage=FakeUsage(input_tokens=100, output_tokens=100),
    )
    oracle = AnthropicOracle(fake_stream_caller([], message), sample_pricing())

    emitted = await collect(oracle)
    assert len(emitted) == 1
    err = emitted[0]
    assert isinstance(err, OracleError)
    assert err.kind == "invalid_schema"


@pytest.mark.asyncio
async def test_bad_tool_input_emits_invalid_schema_with_raw() -> None:
    message = FakeMessage(
        content=[tool_use_block({"action": "bluff", "reasoning": "x", "confidence": "low"})],
        usage=FakeUsage(input_tokens=50, output_tokens=50),
    )
    oracle = AnthropicOracle(fake_stream_caller([], message), sample_pricing())

    emitted = await collect(oracle)
    assert len(emitted) == 1
    err = emitted[0]
    assert isinstance(err, OracleError)
    assert err.kind == "invalid_schema"
    assert err.raw_tool_input == {"action": "bluff", "reasoning": "x", "confidence": "low"}


@pytest.mark.asyncio
async def test_provider_exception_emits_oracle_error() -> None:
    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("network blew up")

    oracle = AnthropicOracle(broken, sample_pricing())

    emitted = await collect(oracle)
    assert len(emitted) == 1
    err = emitted[0]
    assert isinstance(err, OracleError)
    assert err.kind == "provider_error"
    assert "network blew up" in err.message


@pytest.mark.asyncio
async def test_anthropic_oracle_uses_default_system_prompt() -> None:
    from poker_coach.oracle.system_prompt import SYSTEM_PROMPT

    captured: dict[str, Any] = {}
    message = FakeMessage(
        content=[
            tool_use_block({"action": "fold", "reasoning": "Too weak.", "confidence": "medium"})
        ],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    inner = fake_stream_caller([], message)

    def capturing(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return inner(**kwargs)

    oracle = AnthropicOracle(capturing, sample_pricing())
    async for _ in oracle.advise_stream(sample_rendered(), sample_spec()):
        pass

    assert captured["system"] == [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


@pytest.mark.asyncio
async def test_anthropic_oracle_uses_explicit_system_prompt_when_passed() -> None:
    captured: dict[str, Any] = {}
    message = FakeMessage(
        content=[
            tool_use_block({"action": "fold", "reasoning": "Too weak.", "confidence": "medium"})
        ],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    inner = fake_stream_caller([], message)

    def capturing(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return inner(**kwargs)

    oracle = AnthropicOracle(capturing, sample_pricing())
    custom = "OVERRIDE SYSTEM PROMPT FOR TEST"
    async for _ in oracle.advise_stream(sample_rendered(), sample_spec(), system_prompt=custom):
        pass

    assert captured["system"] == [
        {
            "type": "text",
            "text": custom,
            "cache_control": {"type": "ephemeral"},
        }
    ]


@pytest.mark.asyncio
async def test_anthropic_oracle_parses_cache_tokens_and_applies_multipliers() -> None:
    # Cache-hit scenario: 50 fresh input + 800 read from cache + 0 writes.
    # Effective input tokens for cost = 50 + 800*0.1 = 130.
    # 130/1M * 15 + 200/1M * 75 = 0.00195 + 0.015 = 0.01695.
    # Reported input_tokens on the event = uncached + write + read = 850.
    message = FakeMessage(
        content=[
            tool_use_block(
                {"action": "check", "reasoning": "Weak but realized.", "confidence": "low"}
            )
        ],
        usage=FakeUsage(
            input_tokens=50,
            output_tokens=200,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=800,
        ),
    )
    oracle = AnthropicOracle(fake_stream_caller([], message), sample_pricing())

    emitted = await collect(oracle)
    usage = emitted[-1]
    assert isinstance(usage, UsageComplete)
    assert usage.input_tokens == 850
    assert usage.cache_read_input_tokens == 800
    assert usage.cache_creation_input_tokens == 0
    assert usage.output_tokens == 200
    assert usage.total_tokens == 1050
    assert round(usage.cost_usd, 5) == 0.01695
    assert usage.pricing_snapshot["cache_read_multiplier"] == 0.1
    assert usage.pricing_snapshot["cache_write_multiplier"] == 1.25


@pytest.mark.asyncio
async def test_anthropic_oracle_applies_cache_write_premium_on_first_call() -> None:
    # Cache-miss/first-call scenario: 50 fresh + 1000 being written to cache.
    # Effective input tokens for cost = 50 + 1000*1.25 = 1300.
    # 1300/1M * 15 + 100/1M * 75 = 0.0195 + 0.0075 = 0.027.
    message = FakeMessage(
        content=[
            tool_use_block(
                {
                    "action": "bet",
                    "to_amount_bb": 3.0,
                    "reasoning": "Value.",
                    "confidence": "high",
                }
            )
        ],
        usage=FakeUsage(
            input_tokens=50,
            output_tokens=100,
            cache_creation_input_tokens=1000,
            cache_read_input_tokens=0,
        ),
    )
    oracle = AnthropicOracle(fake_stream_caller([], message), sample_pricing())

    emitted = await collect(oracle)
    usage = emitted[-1]
    assert isinstance(usage, UsageComplete)
    assert usage.cache_creation_input_tokens == 1000
    assert usage.cache_read_input_tokens == 0
    assert round(usage.cost_usd, 5) == 0.027


@pytest.mark.asyncio
async def test_ignores_non_thinking_deltas() -> None:
    events = [
        FakeStreamEvent(type="content_block_start"),
        thinking_event("ok"),
        FakeStreamEvent(type="message_delta"),
        FakeStreamEvent(type="content_block_stop"),
    ]
    message = FakeMessage(
        content=[
            tool_use_block(
                {"action": "fold", "reasoning": "Too weak to continue.", "confidence": "medium"}
            )
        ],
        usage=FakeUsage(input_tokens=300, output_tokens=60),
    )
    oracle = AnthropicOracle(fake_stream_caller(events, message), sample_pricing())

    emitted = await collect(oracle)
    kinds = [type(e).__name__ for e in emitted]
    assert kinds == [
        "ReasoningDelta",  # only the thinking_delta survives
        "ReasoningComplete",
        "ToolCallComplete",
        "UsageComplete",
    ]
