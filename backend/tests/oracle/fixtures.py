"""Test fixtures emulating the Anthropic SDK streaming surface.

FakeStream implements the `async with ... as stream:` / `async for event in stream`
/ `stream.get_final_message()` protocol the oracle relies on. Events and the
final message are plain objects with the attributes the oracle reads
(`type`, `delta.type`, `delta.thinking`, `content`, `usage`, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeDelta:
    type: str
    thinking: str = ""


@dataclass
class FakeStreamEvent:
    type: str
    delta: FakeDelta | None = None


@dataclass
class FakeContentBlock:
    type: str
    input: dict[str, Any] | None = None


@dataclass
class FakeUsage:
    input_tokens: int
    output_tokens: int
    thinking_tokens: int = 0


@dataclass
class FakeMessage:
    content: list[FakeContentBlock]
    usage: FakeUsage


class FakeStream:
    def __init__(self, events: list[FakeStreamEvent], final_message: FakeMessage) -> None:
        self._events = events
        self._final = final_message

    async def __aenter__(self) -> FakeStream:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def __aiter__(self) -> FakeStream:
        self._index = 0
        return self

    async def __anext__(self) -> FakeStreamEvent:
        if self._index >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._index]
        self._index += 1
        return event

    async def get_final_message(self) -> FakeMessage:
        return self._final


def fake_stream_caller(events: list[FakeStreamEvent], final_message: FakeMessage) -> Any:
    def _call(**kwargs: Any) -> FakeStream:
        return FakeStream(events, final_message)

    return _call


def thinking_event(text: str) -> FakeStreamEvent:
    return FakeStreamEvent(type="content_block_delta", delta=FakeDelta("thinking_delta", text))


def tool_use_block(payload: dict[str, Any]) -> FakeContentBlock:
    return FakeContentBlock(type="tool_use", input=payload)
