"""HTTP client for the local poker_coach backend.

All calls are async (httpx). The lifecycle mirrors backend's lazy pattern:
1. create_session → session_id
2. create_hand     → hand_id
3. create_decision → decision_id (row is `in_flight`, oracle NOT called yet)
4. stream_decision → SSE; oracle fires here
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, NamedTuple

import httpx


class SSEEvent(NamedTuple):
    type: str
    payload: dict[str, Any]


@dataclass
class StreamedAdvice:
    parsed_advice: dict[str, Any] | None = None
    reasoning_text: str | None = None
    reasoning_stream: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class EngineSnapshot:
    state: dict[str, Any]
    legal_actions: list[dict[str, Any]]


@dataclass
class CoachClient:
    base_url: str
    timeout: float = 180.0

    def __post_init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> CoachClient:
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _required(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("CoachClient must be used as an async context manager")
        return self._client

    async def create_session(self, mode: str = "live", notes: str | None = None) -> str:
        r = await self._required().post("/api/sessions", json={"mode": mode, "notes": notes})
        r.raise_for_status()
        return str(r.json()["session_id"])

    async def create_hand(
        self,
        session_id: str,
        bb: int,
        starting_stack: int,
        rng_seed: int | None = None,
        deck_snapshot: list[str] | None = None,
    ) -> str:
        r = await self._required().post(
            "/api/hands",
            json={
                "session_id": session_id,
                "bb": bb,
                "effective_stack_start": starting_stack,
                "rng_seed": rng_seed,
                "deck_snapshot": deck_snapshot,
            },
        )
        r.raise_for_status()
        return str(r.json()["hand_id"])

    async def engine_start(
        self,
        *,
        effective_stack: int,
        bb: int,
        button: str,
        hero_hole: tuple[str, str] | None = None,
    ) -> EngineSnapshot:
        body: dict[str, Any] = {"effective_stack": effective_stack, "bb": bb, "button": button}
        if hero_hole is not None:
            body["hero_hole"] = list(hero_hole)
        r = await self._required().post("/api/engine/start", json=body)
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    async def engine_apply(
        self,
        *,
        state: dict[str, Any],
        action: dict[str, Any],
    ) -> EngineSnapshot:
        r = await self._required().post(
            "/api/engine/apply", json={"state": state, "action": action}
        )
        if r.status_code == 400:
            raise ValueError(r.json().get("detail", "engine rejected"))
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    async def engine_reveal(
        self,
        *,
        state: dict[str, Any],
        cards: list[str],
    ) -> EngineSnapshot:
        r = await self._required().post("/api/engine/reveal", json={"state": state, "cards": cards})
        if r.status_code == 400:
            raise ValueError(r.json().get("detail", "engine rejected"))
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    async def create_decision(
        self,
        session_id: str,
        hand_id: str | None,
        game_state: dict[str, Any],
        model_preset: str = "gpt-5.3-codex-xhigh",
        prompt_name: str = "coach",
        prompt_version: str = "v2",
        villain_profile: str = "unknown",
    ) -> str:
        r = await self._required().post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": model_preset,
                "prompt_name": prompt_name,
                "prompt_version": prompt_version,
                "game_state": game_state,
                "villain_profile": villain_profile,
            },
        )
        r.raise_for_status()
        return str(r.json()["decision_id"])

    async def stream_decision_events(self, decision_id: str) -> AsyncIterator[SSEEvent]:
        client = self._required()
        async with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            resp.raise_for_status()
            event_name: str | None = None
            async for raw_line in resp.aiter_lines():
                if not raw_line:
                    event_name = None
                    continue
                if raw_line.startswith("event:"):
                    event_name = raw_line[6:].strip()
                elif raw_line.startswith("data:") and event_name is not None:
                    data_str = raw_line[5:].strip()
                    payload: dict[str, Any] = json.loads(data_str) if data_str else {}
                    yield SSEEvent(type=event_name, payload=payload)
                    event_name = None

    async def stream_decision(self, decision_id: str) -> StreamedAdvice:
        result = StreamedAdvice()
        async for event in self.stream_decision_events(decision_id):
            if event.type == "reasoning_delta":
                result.reasoning_stream.append(event.payload.get("text", ""))
            elif event.type == "reasoning_complete":
                result.reasoning_text = event.payload.get("text")
            elif event.type == "tool_call_complete":
                result.parsed_advice = event.payload.get("parsed")
            elif event.type == "usage_complete":
                result.usage = dict(event.payload)
            elif event.type == "error":
                result.error = event.payload.get("message")
        return result
