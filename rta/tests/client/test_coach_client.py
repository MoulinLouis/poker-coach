from __future__ import annotations

import httpx
import pytest
import respx

from poker_rta.client.coach_client import CoachClient


@respx.mock
@pytest.mark.asyncio
async def test_session_and_hand_bootstrap() -> None:
    respx.post("http://localhost:8000/api/sessions").mock(
        return_value=httpx.Response(200, json={"session_id": "s_abc"})
    )
    respx.post("http://localhost:8000/api/hands").mock(
        return_value=httpx.Response(200, json={"hand_id": "h_xyz"})
    )
    client = CoachClient(base_url="http://localhost:8000")
    async with client:
        session_id = await client.create_session(mode="live", notes="rta_demo")
        hand_id = await client.create_hand(session_id=session_id, bb=100, starting_stack=10000)
    assert session_id == "s_abc"
    assert hand_id == "h_xyz"
