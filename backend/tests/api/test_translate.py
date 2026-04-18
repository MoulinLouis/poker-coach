"""Tests for POST /api/translate."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient


def _fake_reply(text: str, input_tokens: int = 100, output_tokens: int = 20) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeMessages:
    def __init__(self, reply_text: str) -> None:
        self._reply_text = reply_text
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return _fake_reply(self._reply_text)


class _FakeAnthropic:
    def __init__(self, reply_text: str = "bonjour le monde") -> None:
        self.messages = _FakeMessages(reply_text)


class _RaisingMessages:
    async def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("sdk boom")


class _RaisingAnthropic:
    messages = _RaisingMessages()


def test_translate_returns_translation_and_cost(
    test_app_builder: Callable[..., Any],
) -> None:
    fake = _FakeAnthropic("bonjour le monde")
    app = test_app_builder(None, anthropic_client=fake)
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": "hello world"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["translation"] == "bonjour le monde"
    assert body["cost_usd"] > 0
    assert fake.messages.calls[0]["messages"] == [
        {"role": "user", "content": "hello world"},
    ]


def test_translate_rejects_empty_text(test_app_builder: Callable[..., Any]) -> None:
    app = test_app_builder(None, anthropic_client=_FakeAnthropic())
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": ""})
    assert resp.status_code == 422


def test_translate_rejects_oversize_text(test_app_builder: Callable[..., Any]) -> None:
    app = test_app_builder(None, anthropic_client=_FakeAnthropic())
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": "x" * 50_001})
    assert resp.status_code == 413


def test_translate_rejects_unsupported_lang(test_app_builder: Callable[..., Any]) -> None:
    app = test_app_builder(None, anthropic_client=_FakeAnthropic())
    with TestClient(app) as client:
        resp = client.post(
            "/api/translate",
            json={"text": "hello", "target_lang": "es"},
        )
    assert resp.status_code == 400


def test_translate_surfaces_sdk_error_as_502(test_app_builder: Callable[..., Any]) -> None:
    app = test_app_builder(None, anthropic_client=_RaisingAnthropic())
    with TestClient(app) as client:
        resp = client.post("/api/translate", json={"text": "hello"})
    assert resp.status_code == 502
    assert "sdk boom" in resp.json()["detail"]
