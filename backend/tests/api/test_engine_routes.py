from typing import Any

from fastapi.testclient import TestClient


def test_start_returns_state_and_legal(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.post(
            "/api/engine/start",
            json={
                "effective_stack": 10_000,
                "bb": 100,
                "button": "hero",
                "hero_hole": ["As", "Kd"],
                "villain_hole": ["Qc", "Qh"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"]["street"] == "preflop"
        assert body["state"]["to_act"] == "hero"
        assert body["state"]["committed"] == {"hero": 50, "villain": 100}
        legal_types = {la["type"] for la in body["legal_actions"]}
        assert {"fold", "call", "raise"} <= legal_types


def test_apply_rejects_illegal(api_app: Any) -> None:
    with TestClient(api_app) as client:
        start_resp = client.post(
            "/api/engine/start",
            json={
                "effective_stack": 10_000,
                "bb": 100,
                "button": "hero",
                "hero_hole": ["As", "Kd"],
                "villain_hole": ["Qc", "Qh"],
            },
        )
        state = start_resp.json()["state"]
        # check is illegal when facing a bet
        resp = client.post(
            "/api/engine/apply",
            json={"state": state, "action": {"actor": "hero", "type": "check"}},
        )
        assert resp.status_code == 400


def test_apply_advances_state(api_app: Any) -> None:
    with TestClient(api_app) as client:
        start = client.post(
            "/api/engine/start",
            json={
                "effective_stack": 10_000,
                "bb": 100,
                "button": "hero",
                "hero_hole": ["As", "Kd"],
                "villain_hole": ["Qc", "Qh"],
            },
        ).json()
        resp = client.post(
            "/api/engine/apply",
            json={
                "state": start["state"],
                "action": {"actor": "hero", "type": "raise", "to_amount": 300},
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"]["to_act"] == "villain"
        assert body["state"]["last_aggressor"] == "hero"


def test_reveal_flop_returns_updated_snapshot(api_app: Any) -> None:
    with TestClient(api_app) as client:
        start = client.post("/api/engine/start", json={
            "effective_stack": 10_000, "bb": 100, "button": "hero",
            "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
        }).json()
        s = client.post("/api/engine/apply", json={
            "state": start["state"], "action": {"actor":"hero","type":"call"},
        }).json()
        s = client.post("/api/engine/apply", json={
            "state": s["state"], "action": {"actor":"villain","type":"check"},
        }).json()
        assert s["state"]["pending_reveal"] == "flop"

        r = client.post("/api/engine/reveal", json={
            "state": s["state"], "cards": ["2c","3d","5s"],
        })
        assert r.status_code == 200
        body = r.json()
        assert body["state"]["pending_reveal"] is None
        assert body["state"]["board"] == ["2c","3d","5s"]
        assert len(body["legal_actions"]) > 0


def test_reveal_rejects_wrong_length(api_app: Any) -> None:
    with TestClient(api_app) as client:
        start = client.post("/api/engine/start", json={
            "effective_stack": 10_000, "bb": 100, "button": "hero",
            "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
        }).json()
        s = client.post("/api/engine/apply", json={
            "state": start["state"], "action": {"actor":"hero","type":"call"},
        }).json()
        s = client.post("/api/engine/apply", json={
            "state": s["state"], "action": {"actor":"villain","type":"check"},
        }).json()
        r = client.post("/api/engine/reveal", json={
            "state": s["state"], "cards": ["2c","3d"],
        })
        assert r.status_code == 400


def test_reveal_rejects_when_no_pending(api_app: Any) -> None:
    with TestClient(api_app) as client:
        start = client.post("/api/engine/start", json={
            "effective_stack": 10_000, "bb": 100, "button": "hero",
            "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
        }).json()
        r = client.post("/api/engine/reveal", json={
            "state": start["state"], "cards": ["2c","3d","5s"],
        })
        assert r.status_code == 400


def test_presets_list(api_app: Any) -> None:
    with TestClient(api_app) as client:
        resp = client.get("/api/presets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["default"] == "gpt-5.3-codex-xhigh"
        ids = {p["selector_id"] for p in body["presets"]}
        assert {
            "gpt-5.3-codex-xhigh",
            "gpt-5.4-medium",
            "claude-opus-4-7-deep",
            "claude-haiku-4-5-min",
        } <= ids
