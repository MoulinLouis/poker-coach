from __future__ import annotations

import httpx
import pytest
import respx

from poker_rta.client.coach_client import CoachClient, SSEEvent, StreamedAdvice

_TOOL_DATA = b'{"parsed": {"action": "raise", "to_bb": 3.0, "rationale": "value"}}'
_SSE_BODY = (
    b'event: reasoning_delta\ndata: {"text": "think"}\n\n'
    b'event: reasoning_complete\ndata: {"text": "thinking done"}\n\n'
    b"event: tool_call_complete\ndata: " + _TOOL_DATA + b"\n\n"
    b'event: usage_complete\ndata: {"input_tokens": 1200, "output_tokens": 400}\n\n'
)


@respx.mock
@pytest.mark.asyncio
async def test_stream_collects_reasoning_and_advice() -> None:
    respx.get("http://localhost:8000/api/decisions/d_1/stream").mock(
        return_value=httpx.Response(
            200, content=_SSE_BODY, headers={"Content-Type": "text/event-stream"}
        )
    )
    client = CoachClient(base_url="http://localhost:8000")
    async with client:
        result = await client.stream_decision("d_1")
    assert isinstance(result, StreamedAdvice)
    assert result.parsed_advice == {"action": "raise", "to_bb": 3.0, "rationale": "value"}
    assert result.reasoning_text == "thinking done"
    assert result.usage == {"input_tokens": 1200, "output_tokens": 400}


@respx.mock
@pytest.mark.asyncio
async def test_stream_events_iterator() -> None:
    respx.get("http://localhost:8000/api/decisions/d_2/stream").mock(
        return_value=httpx.Response(
            200, content=_SSE_BODY, headers={"Content-Type": "text/event-stream"}
        )
    )
    client = CoachClient(base_url="http://localhost:8000")
    events: list[SSEEvent] = []
    async with client:
        async for event in client.stream_decision_events("d_2"):
            events.append(event)

    assert len(events) == 4
    assert events[0] == SSEEvent(type="reasoning_delta", payload={"text": "think"})
    assert events[1] == SSEEvent(type="reasoning_complete", payload={"text": "thinking done"})
    assert events[2] == SSEEvent(
        type="tool_call_complete",
        payload={"parsed": {"action": "raise", "to_bb": 3.0, "rationale": "value"}},
    )
    assert events[3] == SSEEvent(
        type="usage_complete", payload={"input_tokens": 1200, "output_tokens": 400}
    )
