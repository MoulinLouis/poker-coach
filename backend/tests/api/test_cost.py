from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from poker_coach.db.tables import decisions, sessions


def _seed_decision(
    engine: Engine,
    *,
    session_id: str,
    decision_id: str,
    model_id: str,
    reasoning_effort: str | None,
    cost_usd: float,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(decisions).values(
                decision_id=decision_id,
                session_id=session_id,
                game_state={},
                prompt_name="coach",
                prompt_version="v1",
                template_hash="x" * 64,
                template_raw="---\nname: coach\nversion: v1\n---\nbody",
                rendered_prompt="body",
                variables={},
                provider="anthropic" if "claude" in model_id else "openai",
                model_id=model_id,
                reasoning_effort=reasoning_effort,
                status="ok",
                cost_usd=cost_usd,
            )
        )


def test_cost_zero_on_empty_db(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.get("/api/cost")
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_usd"] == 0.0
        assert body["all_time_usd"] == 0.0
        assert body["by_model"] == []


def test_cost_aggregates_by_model_and_effort(api_app: Any, migrated_engine: Engine) -> None:
    with migrated_engine.begin() as conn:
        conn.execute(insert(sessions).values(session_id="s1", mode="live"))
        conn.execute(insert(sessions).values(session_id="s2", mode="live"))

    _seed_decision(
        migrated_engine,
        session_id="s1",
        decision_id="d1",
        model_id="gpt-5.3-codex",
        reasoning_effort="xhigh",
        cost_usd=0.10,
    )
    _seed_decision(
        migrated_engine,
        session_id="s1",
        decision_id="d2",
        model_id="gpt-5.3-codex",
        reasoning_effort="xhigh",
        cost_usd=0.05,
    )
    _seed_decision(
        migrated_engine,
        session_id="s2",
        decision_id="d3",
        model_id="claude-haiku-4-5-20251001",
        reasoning_effort=None,
        cost_usd=0.02,
    )

    with TestClient(api_app) as client:
        resp = client.get("/api/cost")
        body = resp.json()

    assert round(body["all_time_usd"], 4) == 0.17
    by_model = {(r["model_id"], r["reasoning_effort"]): r for r in body["by_model"]}
    assert by_model[("gpt-5.3-codex", "xhigh")]["decision_count"] == 2
    assert round(by_model[("gpt-5.3-codex", "xhigh")]["cost_usd"], 4) == 0.15
    assert by_model[("claude-haiku-4-5-20251001", "none")]["decision_count"] == 1
    assert round(by_model[("claude-haiku-4-5-20251001", "none")]["cost_usd"], 4) == 0.02

    # Scoped by session
    with TestClient(api_app) as client:
        resp = client.get("/api/cost?session_id=s1")
        body = resp.json()
    assert round(body["session_usd"], 4) == 0.15
    assert round(body["all_time_usd"], 4) == 0.17
