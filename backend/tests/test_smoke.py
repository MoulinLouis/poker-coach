from fastapi.testclient import TestClient


def test_health(api_app) -> None:  # type: ignore[no-untyped-def]
    with TestClient(api_app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
