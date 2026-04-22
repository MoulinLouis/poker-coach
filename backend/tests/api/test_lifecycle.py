"""Decision lifecycle end-to-end tests driven against the FastAPI app.

Uses the TestClient to cover: session/hand/decision creation, atomic
SSE claim semantics (409 on double-open), full stream forwarding of
oracle events into SSE frames, terminal DB state, record-action
persistence, and the sweeper's abandoned/timeout transitions.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update

from poker_coach.api.deps import OracleFactory
from poker_coach.api.sweeper import sweep_once
from poker_coach.db.tables import decisions
from poker_coach.engine.rules import start_hand
from poker_coach.oracle.base import (
    Advice,
    ModelSpec,
    Oracle,
    OracleError,
    OracleEvent,
    ReasoningComplete,
    ReasoningDelta,
    ToolCallComplete,
    UsageComplete,
)


class FakeOracle:
    def __init__(self, events: list[OracleEvent]) -> None:
        self._events = events

    async def advise_stream(
        self,
        rendered: Any,
        spec: ModelSpec,
        system_prompt: str | None = None,
    ) -> AsyncIterator[OracleEvent]:
        for event in self._events:
            yield event


class FakeOracleFactory(OracleFactory):
    def __init__(self, events: list[OracleEvent]) -> None:
        self._events = events

    def for_spec(self, spec: ModelSpec) -> Oracle:
        return FakeOracle(self._events)  # type: ignore[return-value]


def _happy_events() -> list[OracleEvent]:
    return [
        ReasoningDelta(text="Considering "),
        ReasoningDelta(text="pot odds..."),
        ReasoningComplete(full_text="Considering pot odds..."),
        ToolCallComplete(
            advice=Advice(
                action="raise",
                to_amount_bb=7.5,
                reasoning="Value raise with strong combo.",
                confidence="high",
            ),
            raw_tool_input={
                "action": "raise",
                "to_amount_bb": 7.5,
                "reasoning": "Value raise with strong combo.",
                "confidence": "high",
            },
        ),
        UsageComplete(
            input_tokens=1_000,
            output_tokens=400,
            reasoning_tokens=250,
            total_tokens=1_400,
            cost_usd=0.045,
            pricing_snapshot={"snapshot_date": "2026-04-18", "snapshot_source": "test"},
        ),
    ]


def _sample_game_state() -> dict[str, Any]:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    return state.model_dump(mode="json")


def _sse_events(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    event = None
    for line in body.split("\n"):
        if line.startswith("event: "):
            event = line[len("event: ") :]
        elif line.startswith("data: ") and event is not None:
            out.append((event, line[len("data: ") :]))
            event = None
    return out


@pytest.fixture
def happy_factory() -> FakeOracleFactory:
    return FakeOracleFactory(_happy_events())


@pytest.fixture
def app_with_factory(
    test_app_builder: Callable[[OracleFactory | None], Any],
    happy_factory: FakeOracleFactory,
) -> Any:
    return test_app_builder(happy_factory)


def test_happy_path_lifecycle(app_with_factory: Any, migrated_engine: Engine) -> None:
    with TestClient(app_with_factory) as client:
        # 1. Session
        resp = client.post("/api/sessions", json={"mode": "live"})
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]

        # 2. Hand
        resp = client.post(
            "/api/hands",
            json={
                "session_id": session_id,
                "bb": 100,
                "effective_stack_start": 10_000,
            },
        )
        assert resp.status_code == 200
        hand_id = resp.json()["hand_id"]

        # 3. Decision (does not invoke oracle)
        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        )
        assert resp.status_code == 200
        decision_id = resp.json()["decision_id"]

        # Verify in_flight row, no stream_opened_at
        with migrated_engine.connect() as conn:
            row = conn.execute(
                select(decisions.c.status, decisions.c.stream_opened_at).where(
                    decisions.c.decision_id == decision_id
                )
            ).one()
        assert row.status == "in_flight"
        assert row.stream_opened_at is None

        # 4. SSE stream
        with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            assert resp.status_code == 200
            body = resp.read().decode()

        parsed = _sse_events(body)
        event_types = [etype for etype, _ in parsed]
        assert event_types == [
            "reasoning_delta",
            "reasoning_delta",
            "reasoning_complete",
            "tool_call_complete",
            "usage_complete",
            "done",
        ]

        # Verify terminal DB state
        with migrated_engine.connect() as conn:
            row = conn.execute(
                select(
                    decisions.c.status,
                    decisions.c.stream_opened_at,
                    decisions.c.parsed_advice,
                    decisions.c.reasoning_text,
                    decisions.c.cost_usd,
                    decisions.c.latency_ms,
                ).where(decisions.c.decision_id == decision_id)
            ).one()
        assert row.status == "ok"
        assert row.stream_opened_at is not None
        assert row.parsed_advice["action"] == "raise"
        assert row.parsed_advice["to_amount_bb"] == 7.5
        assert row.reasoning_text == "Considering pot odds..."
        assert row.cost_usd == 0.045
        assert row.latency_ms is not None

        # 5. Record the human's actual action
        resp = client.post(
            "/api/actions",
            json={
                "decision_id": decision_id,
                "action": {"actor": "hero", "type": "call"},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["id"] >= 1


def test_double_open_returns_409(
    app_with_factory: Any,
) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]
        decision_id = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        ).json()["decision_id"]

        # First open succeeds
        with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            assert resp.status_code == 200
            resp.read()

        # Second open is 409
        resp = client.get(f"/api/decisions/{decision_id}/stream")
        assert resp.status_code == 409


def test_stream_missing_decision_404(app_with_factory: Any) -> None:
    with TestClient(app_with_factory) as client:
        resp = client.get("/api/decisions/does-not-exist/stream")
        assert resp.status_code == 404


def test_bad_model_preset_400(app_with_factory: Any) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]
        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "nope",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        )
        assert resp.status_code == 400


def test_oracle_error_sets_provider_error_status(
    test_app_builder: Callable[[OracleFactory | None], Any],
    migrated_engine: Engine,
) -> None:
    bad_events: list[OracleEvent] = [
        OracleError(kind="provider_error", message="upstream hiccup"),
    ]
    app = test_app_builder(FakeOracleFactory(bad_events))
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]
        decision_id = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        ).json()["decision_id"]

        with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            body = resp.read().decode()
        assert "oracle_error" in body

    with migrated_engine.connect() as conn:
        row = conn.execute(
            select(decisions.c.status, decisions.c.error_message).where(
                decisions.c.decision_id == decision_id
            )
        ).one()
    assert row.status == "provider_error"
    assert row.error_message == "upstream hiccup"


def test_sweeper_abandoned_and_timeout(app_with_factory: Any, migrated_engine: Engine) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]

        # Decision A: never opens a stream → abandoned
        decision_a = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        ).json()["decision_id"]

        # Decision B: opens stream but we manually pin stream_opened_at
        # way in the past + status still in_flight → timeout
        decision_b = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        ).json()["decision_id"]

    # Simulate elapsed time: backdate rows via direct DB update
    long_ago = datetime.now(UTC) - timedelta(minutes=10)
    with migrated_engine.begin() as conn:
        conn.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision_a)
            .values(created_at=long_ago)
        )
        conn.execute(
            update(decisions)
            .where(decisions.c.decision_id == decision_b)
            .values(stream_opened_at=long_ago)
        )

    abandoned, timed_out = sweep_once(migrated_engine, abandoned_seconds=30, timeout_seconds=180)
    assert abandoned == 1
    assert timed_out == 1

    with migrated_engine.connect() as conn:
        status_a = conn.execute(
            select(decisions.c.status).where(decisions.c.decision_id == decision_a)
        ).scalar()
        status_b = conn.execute(
            select(decisions.c.status).where(decisions.c.decision_id == decision_b)
        ).scalar()
    assert status_a == "abandoned"
    assert status_b == "timeout"


def test_latency_ms_is_reasonable(app_with_factory: Any, migrated_engine: Engine) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]
        decision_id = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v1",
                "game_state": _sample_game_state(),
            },
        ).json()["decision_id"]
        start = time.monotonic()
        with client.stream("GET", f"/api/decisions/{decision_id}/stream") as resp:
            resp.read()
        wall = (time.monotonic() - start) * 1000

    with migrated_engine.connect() as conn:
        latency = conn.execute(
            select(decisions.c.latency_ms).where(decisions.c.decision_id == decision_id)
        ).scalar()
    # Logged latency should be <= actual wall time and non-negative.
    assert latency is not None
    assert 0 <= latency <= wall + 100  # some headroom for scheduling jitter


def test_v2_decision_persists_villain_profile_and_system_prompt(
    app_with_factory: Any, migrated_engine: Engine
) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "live"}).json()["session_id"]
        hand_id = client.post(
            "/api/hands",
            json={"session_id": session_id, "bb": 100, "effective_stack_start": 10_000},
        ).json()["hand_id"]

        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v2",
                "game_state": _sample_game_state(),
                "villain_profile": "reg",
            },
        )
        assert resp.status_code == 200
        decision_id = resp.json()["decision_id"]

        with migrated_engine.connect() as conn:
            row = conn.execute(
                select(
                    decisions.c.villain_profile,
                    decisions.c.system_prompt,
                    decisions.c.system_prompt_hash,
                    decisions.c.rendered_prompt,
                ).where(decisions.c.decision_id == decision_id)
            ).one()
        assert row.villain_profile == "reg"
        assert row.system_prompt is not None
        assert "solid human regular" in row.system_prompt
        assert len(row.system_prompt_hash) == 64
        assert "reg" in row.rendered_prompt


def test_v3_decision_persists_v3_system_prompt(
    app_with_factory: Any, migrated_engine: Engine
) -> None:
    """POST /api/decisions with prompt_version=v3 must store the v3 system prompt.

    Regression guard for the v3 system-prompt split (commit ee0687f):
    - decisions.system_prompt must NOT contain "Never randomize" (that's a v2-ism)
    - decisions.system_prompt MUST contain mixed-strategy framing
    Purely checking `system_prompt_for` in isolation is not enough — the route
    must actually wire it.
    """
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "live"}).json()["session_id"]
        hand_id = client.post(
            "/api/hands",
            json={"session_id": session_id, "bb": 100, "effective_stack_start": 10_000},
        ).json()["hand_id"]

        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v3",
                "game_state": _sample_game_state(),
                "villain_profile": "reg",
            },
        )
        assert resp.status_code == 200
        decision_id = resp.json()["decision_id"]

        with migrated_engine.connect() as conn:
            row = conn.execute(
                select(decisions.c.system_prompt).where(
                    decisions.c.decision_id == decision_id
                )
            ).one()

        assert row.system_prompt is not None
        # v3 dropped "Never randomize" and "Never output two actions"
        assert "Never randomize" not in row.system_prompt
        assert "Never output two actions" not in row.system_prompt
        # v3 explicitly mentions mixed strategy output
        assert "mixed strategy" in row.system_prompt.lower()


def test_v2_decision_rejects_invalid_villain_profile(app_with_factory: Any) -> None:
    with TestClient(app_with_factory) as client:
        session_id = client.post("/api/sessions", json={"mode": "spot"}).json()["session_id"]
        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v2",
                "game_state": _sample_game_state(),
                "villain_profile": "whale",
            },
        )
        assert resp.status_code == 422
