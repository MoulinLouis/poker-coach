"""HTTP client for the local poker_coach backend.

All calls are async (httpx). The lifecycle mirrors backend's lazy pattern:
1. create_session → session_id
2. create_hand     → hand_id
3. create_decision → decision_id (row is `in_flight`, oracle NOT called yet)
4. stream_decision → SSE; oracle fires here
"""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx


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
