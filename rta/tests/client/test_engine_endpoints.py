from __future__ import annotations

import httpx
import pytest
import respx

from poker_rta.client.coach_client import CoachClient, EngineSnapshot

_BASE = "http://localhost:8000"

_SNAP_RESP = {
    "state": {
        "hand_id": "h1",
        "bb": 100,
        "effective_stack": 10000,
        "button": "hero",
        "hero_hole": ["As", "Kd"],
        "villain_hole": None,
        "board": [],
        "street": "preflop",
        "stacks": {"hero": 9950, "villain": 9900},
        "committed": {"hero": 50, "villain": 100},
        "pot": 0,
        "to_act": "hero",
        "last_aggressor": "villain",
        "last_raise_size": 100,
        "raises_open": True,
        "acted_this_street": [],
        "history": [],
        "rng_seed": None,
        "deck_snapshot": None,
        "pending_reveal": None,
        "reveals": [],
    },
    "legal_actions": [
        {"type": "fold"},
        {"type": "call"},
        {"type": "raise"},
    ],
}


@respx.mock
@pytest.mark.asyncio
async def test_engine_start_sends_hero_hole_and_returns_snapshot() -> None:
    route = respx.post(f"{_BASE}/api/engine/start").mock(
        return_value=httpx.Response(200, json=_SNAP_RESP)
    )
    client = CoachClient(base_url=_BASE)
    async with client:
        snap = await client.engine_start(
            effective_stack=10000,
            bb=100,
            button="hero",
            hero_hole=("As", "Kd"),
        )

    assert isinstance(snap, EngineSnapshot)
    assert snap.state["to_act"] == "hero"
    assert snap.legal_actions[0]["type"] == "fold"

    sent_body = route.calls[0].request
    import json

    body = json.loads(sent_body.content)
    assert body["hero_hole"] == ["As", "Kd"]
    assert body["button"] == "hero"


@respx.mock
@pytest.mark.asyncio
async def test_engine_apply_400_raises_value_error() -> None:
    respx.post(f"{_BASE}/api/engine/apply").mock(
        return_value=httpx.Response(
            400, json={"detail": "IllegalAction: fold not in legal actions"}
        )
    )
    client = CoachClient(base_url=_BASE)
    async with client:
        with pytest.raises(ValueError, match="IllegalAction: fold not in legal actions"):
            await client.engine_apply(
                state=_SNAP_RESP["state"],
                action={"actor": "hero", "type": "fold", "to_amount": None},
            )
