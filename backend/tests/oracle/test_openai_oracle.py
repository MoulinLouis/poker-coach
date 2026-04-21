from dataclasses import dataclass, field
from typing import Any

import pytest

from poker_coach.oracle.base import (
    Advice,
    ModelSpec,
    OracleError,
    ReasoningComplete,
    ReasoningDelta,
    ToolCallComplete,
    UsageComplete,
)
from poker_coach.oracle.openai_oracle import OpenAIOracle
from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot
from poker_coach.prompts.renderer import RenderedPrompt


@dataclass
class FakeEvent:
    type: str
    delta: str = ""


@dataclass
class FakeFunctionCall:
    type: str
    name: str
    arguments: str


@dataclass
class FakeUsageDetails:
    reasoning_tokens: int = 0


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    output_tokens_details: FakeUsageDetails = field(default_factory=FakeUsageDetails)


@dataclass
class FakeResponse:
    output: list[Any]
    usage: FakeUsage


class FakeStream:
    def __init__(self, events: list[FakeEvent], response: FakeResponse) -> None:
        self._events = events
        self._response = response

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def __aiter__(self) -> "FakeStream":
        self._index = 0
        return self

    async def __anext__(self) -> FakeEvent:
        if self._index >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._index]
        self._index += 1
        return event

    async def get_final_response(self) -> FakeResponse:
        return self._response


def fake_stream_caller(events: list[FakeEvent], response: FakeResponse) -> Any:
    def _call(**kwargs: Any) -> FakeStream:
        return FakeStream(events, response)

    return _call


def sample_pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_date="2026-04-18",
        snapshot_source="test",
        models={
            "gpt-5.3-codex": PricingEntry(input_per_mtok=1.75, output_per_mtok=14.0),
        },
    )


def sample_spec() -> ModelSpec:
    return ModelSpec(
        selector_id="gpt-5.3-codex-xhigh",
        provider="openai",
        model_id="gpt-5.3-codex",
        reasoning_effort="xhigh",
    )


def sample_rendered() -> RenderedPrompt:
    return RenderedPrompt(
        pack="coach",
        version="v1",
        template_hash="a" * 64,
        template_raw="---\nname: coach\nversion: v1\n---\nbody",
        rendered_prompt="body",
        variables={},
    )


async def collect(oracle: OpenAIOracle) -> list[Any]:
    return [event async for event in oracle.advise_stream(sample_rendered(), sample_spec())]


@pytest.mark.asyncio
async def test_happy_path_streams_reasoning_then_tool_then_usage() -> None:
    events = [
        FakeEvent(type="response.reasoning_summary_text.delta", delta="First "),
        FakeEvent(type="response.reasoning_summary_text.delta", delta="thought."),
        FakeEvent(type="response.output_item.done"),
    ]
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments=(
            '{"action":"call","to_amount_bb":null,'
            '"reasoning":"Getting the right price.","confidence":"medium"}'
        ),
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(
            input_tokens=800,
            output_tokens=320,
            output_tokens_details=FakeUsageDetails(reasoning_tokens=200),
        ),
    )
    oracle = OpenAIOracle(fake_stream_caller(events, response), sample_pricing())
    emitted = await collect(oracle)

    kinds = [type(e).__name__ for e in emitted]
    assert kinds == [
        "ReasoningDelta",
        "ReasoningDelta",
        "ReasoningComplete",
        "ToolCallComplete",
        "UsageComplete",
    ]
    assert isinstance(emitted[0], ReasoningDelta) and emitted[0].text == "First "
    assert isinstance(emitted[2], ReasoningComplete)
    assert emitted[2].full_text == "First thought."

    tool = emitted[3]
    assert isinstance(tool, ToolCallComplete)
    assert tool.advice == Advice(
        action="call",
        to_amount_bb=None,
        reasoning="Getting the right price.",
        confidence="medium",
    )

    usage = emitted[4]
    assert isinstance(usage, UsageComplete)
    assert usage.input_tokens == 800
    assert usage.output_tokens == 320
    assert usage.reasoning_tokens == 200
    # 800/1M*1.75 + 320/1M*14 = 0.0014 + 0.00448 = 0.00588
    assert round(usage.cost_usd, 6) == 0.00588


@pytest.mark.asyncio
async def test_missing_function_call_emits_invalid_schema() -> None:
    response = FakeResponse(
        output=[],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    oracle = OpenAIOracle(fake_stream_caller([], response), sample_pricing())
    emitted = await collect(oracle)
    assert len(emitted) == 1
    err = emitted[0]
    assert isinstance(err, OracleError)
    assert err.kind == "invalid_schema"


@pytest.mark.asyncio
async def test_malformed_json_emits_invalid_schema() -> None:
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments='{"action": "raise", broken}',
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    oracle = OpenAIOracle(fake_stream_caller([], response), sample_pricing())
    emitted = await collect(oracle)
    assert len(emitted) == 1
    assert isinstance(emitted[0], OracleError)
    assert emitted[0].kind == "invalid_schema"


@pytest.mark.asyncio
async def test_schema_violation_preserves_raw_input() -> None:
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments='{"action":"jump","reasoning":"x","confidence":"low"}',
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    oracle = OpenAIOracle(fake_stream_caller([], response), sample_pricing())
    emitted = await collect(oracle)
    err = emitted[0]
    assert isinstance(err, OracleError)
    assert err.kind == "invalid_schema"
    assert err.raw_tool_input == {
        "action": "jump",
        "reasoning": "x",
        "confidence": "low",
    }


@pytest.mark.asyncio
async def test_provider_exception_emits_oracle_error() -> None:
    def broken(**kwargs: Any) -> Any:
        raise RuntimeError("rate limit")

    oracle = OpenAIOracle(broken, sample_pricing())
    emitted = await collect(oracle)
    assert isinstance(emitted[0], OracleError)
    assert emitted[0].kind == "provider_error"


def _v3_rendered(legal: list[dict[str, Any]], bb_chips: int = 100) -> RenderedPrompt:
    return RenderedPrompt(
        pack="coach",
        version="v3",
        template_hash="a" * 64,
        template_raw="---\nname: coach\nversion: v3\n---\nbody",
        rendered_prompt="body",
        variables={"bb_chips": bb_chips, "legal_actions": legal},
    )


@pytest.mark.asyncio
async def test_v3_parses_strategy_and_derives_argmax() -> None:
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments=(
            '{"action":null,"to_amount_bb":null,'
            '"reasoning":"Polarized c-bet.","confidence":"medium",'
            '"strategy":['
            '{"action":"check","to_amount_bb":null,"frequency":0.35},'
            '{"action":"bet","to_amount_bb":3.0,"frequency":0.65}'
            "]}"
        ),
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=100, output_tokens=100),
    )
    rendered = _v3_rendered(
        [
            {"type": "check", "min_to_bb": None, "max_to_bb": None},
            {"type": "bet", "min_to_bb": 1.0, "max_to_bb": 97.0},
        ]
    )
    oracle = OpenAIOracle(fake_stream_caller([], response), sample_pricing())

    emitted = [e async for e in oracle.advise_stream(rendered, sample_spec())]
    tool_events = [e for e in emitted if isinstance(e, ToolCallComplete)]
    assert len(tool_events) == 1

    advice = tool_events[0].advice
    assert advice.strategy is not None
    assert len(advice.strategy) == 2
    assert advice.strategy[0].action == "bet"
    assert advice.strategy[0].frequency == pytest.approx(0.65)
    assert advice.action == "bet"
    assert advice.to_amount_bb == 3.0


@pytest.mark.asyncio
async def test_v3_rejects_invalid_strategy() -> None:
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments=(
            '{"action":null,"to_amount_bb":null,'
            '"reasoning":"Invalid.","confidence":"low",'
            '"strategy":['
            '{"action":"check","to_amount_bb":null,"frequency":0.3},'
            '{"action":"bet","to_amount_bb":3.0,"frequency":0.3}'
            "]}"
        ),
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=100, output_tokens=100),
    )
    rendered = _v3_rendered(
        [
            {"type": "check", "min_to_bb": None, "max_to_bb": None},
            {"type": "bet", "min_to_bb": 1.0, "max_to_bb": 97.0},
        ]
    )
    oracle = OpenAIOracle(fake_stream_caller([], response), sample_pricing())

    emitted = [e async for e in oracle.advise_stream(rendered, sample_spec())]
    assert not any(isinstance(e, ToolCallComplete) for e in emitted)
    errors = [e for e in emitted if isinstance(e, OracleError) and e.kind == "invalid_schema"]
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_openai_oracle_passes_system_prompt_as_instructions() -> None:
    from poker_coach.oracle.system_prompt import SYSTEM_PROMPT

    captured: dict[str, Any] = {}
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments='{"action":"fold","to_amount_bb":null,"reasoning":"x","confidence":"low"}',
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    inner = fake_stream_caller([], response)

    def capturing(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return inner(**kwargs)

    oracle = OpenAIOracle(capturing, sample_pricing())
    async for _ in oracle.advise_stream(sample_rendered(), sample_spec()):
        pass

    assert captured["instructions"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_openai_oracle_uses_explicit_system_prompt_when_passed() -> None:
    captured: dict[str, Any] = {}
    function_call = FakeFunctionCall(
        type="function_call",
        name="submit_advice",
        arguments='{"action":"fold","to_amount_bb":null,"reasoning":"x","confidence":"low"}',
    )
    response = FakeResponse(
        output=[function_call],
        usage=FakeUsage(input_tokens=10, output_tokens=10),
    )
    inner = fake_stream_caller([], response)

    def capturing(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return inner(**kwargs)

    oracle = OpenAIOracle(capturing, sample_pricing())
    custom = "CUSTOM SYSTEM PROMPT"
    async for _ in oracle.advise_stream(sample_rendered(), sample_spec(), system_prompt=custom):
        pass

    assert captured["instructions"] == custom
