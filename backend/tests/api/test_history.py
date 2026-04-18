from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, insert

from poker_coach.db.tables import decisions, sessions


def _seed(
    engine: Engine,
    *,
    decision_id: str,
    session_id: str,
    model_id: str,
    status: str = "ok",
) -> None:
    with engine.begin() as conn:
        conn.execute(
            insert(decisions).values(
                decision_id=decision_id,
                session_id=session_id,
                game_state={"street": "preflop"},
                prompt_name="coach",
                prompt_version="v1",
                template_hash="x" * 64,
                template_raw="---\nname: coach\nversion: v1\n---\nbody",
                rendered_prompt=f"prompt for {decision_id}",
                variables={},
                provider="anthropic",
                model_id=model_id,
                status=status,
            )
        )


def test_list_returns_most_recent_first(api_app: Any, migrated_engine: Engine) -> None:
    with migrated_engine.begin() as conn:
        conn.execute(insert(sessions).values(session_id="s", mode="live"))
    _seed(migrated_engine, decision_id="d1", session_id="s", model_id="claude-opus-4-7")
    _seed(migrated_engine, decision_id="d2", session_id="s", model_id="claude-haiku-4-5-20251001")

    with TestClient(api_app) as client:
        resp = client.get("/api/decisions?limit=10")
    assert resp.status_code == 200
    ids = [r["decision_id"] for r in resp.json()]
    assert set(ids) == {"d1", "d2"}


def test_list_filters_by_model(api_app: Any, migrated_engine: Engine) -> None:
    with migrated_engine.begin() as conn:
        conn.execute(insert(sessions).values(session_id="s", mode="live"))
    _seed(migrated_engine, decision_id="d1", session_id="s", model_id="claude-opus-4-7")
    _seed(migrated_engine, decision_id="d2", session_id="s", model_id="claude-haiku-4-5-20251001")

    with TestClient(api_app) as client:
        resp = client.get("/api/decisions?model_id=claude-opus-4-7")
    body = resp.json()
    assert [r["decision_id"] for r in body] == ["d1"]


def test_detail_returns_full_row(api_app: Any, migrated_engine: Engine) -> None:
    with migrated_engine.begin() as conn:
        conn.execute(insert(sessions).values(session_id="s", mode="live"))
    _seed(migrated_engine, decision_id="d1", session_id="s", model_id="claude-opus-4-7")

    with TestClient(api_app) as client:
        resp = client.get("/api/decisions/d1/detail")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rendered_prompt"] == "prompt for d1"
    assert body["game_state"] == {"street": "preflop"}
    assert body["template_hash"] == "x" * 64


def test_detail_missing_returns_404(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.get("/api/decisions/nope/detail")
    assert resp.status_code == 404
