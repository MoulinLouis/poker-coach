"""Session-level ICM fields (payout_structure, blind_level_label) end-to-end."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient


def test_create_session_accepts_payout_structure(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.post(
            "/api/sessions",
            json={
                "mode": "live",
                "payout_structure": [0.65, 0.35],
                "blind_level_label": "50/100 + 100 ante",
            },
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        detail = client.get(f"/api/sessions/{session_id}").json()
        assert detail["payout_structure"] == [0.65, 0.35]
        assert detail["blind_level_label"] == "50/100 + 100 ante"


def test_create_session_without_icm_fields_works(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.post("/api/sessions", json={"mode": "live"})
        assert resp.status_code == 200


def test_payout_structure_must_sum_to_one(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.post(
            "/api/sessions",
            json={"mode": "live", "payout_structure": [0.5, 0.3]},
        )
        assert resp.status_code in (400, 422)
        assert "sum" in resp.text.lower()


def test_payout_structure_entries_must_be_non_negative(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.post(
            "/api/sessions",
            json={"mode": "live", "payout_structure": [1.2, -0.2]},
        )
        assert resp.status_code in (400, 422)
