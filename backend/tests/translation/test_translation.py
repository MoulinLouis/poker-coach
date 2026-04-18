"""Translation helper tests.

Use a fake Anthropic client matching the real SDK's async surface
(``client.messages.create`` is async and returns an object with a
``content`` list and a ``usage`` block).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from poker_coach.oracle.pricing import PricingSnapshot
from poker_coach.translation import (
    TRANSLATE_MODEL_ID,
    TRANSLATE_SYSTEM_PROMPT,
    translate_to_french,
)


def _fake_message(text: str, input_tokens: int, output_tokens: int) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeMessages:
    def __init__(self, reply: SimpleNamespace) -> None:
        self._reply = reply
        self.captured: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.captured.update(kwargs)
        return self._reply


class _FakeClient:
    def __init__(self, reply: SimpleNamespace) -> None:
        self.messages = _FakeMessages(reply)


def test_translate_to_french_returns_translation_and_cost(
    sample_pricing: PricingSnapshot,
) -> None:
    client = _FakeClient(_fake_message("Coucou le monde", input_tokens=50, output_tokens=10))
    result = asyncio.run(
        translate_to_french("Hello world", client=client, pricing=sample_pricing)
    )
    assert result.translation == "Coucou le monde"
    # Haiku test pricing: $1/Mtok input, $5/Mtok output.
    # 50 * 1/1e6 + 10 * 5/1e6 = 5e-5 + 5e-5 = 1e-4
    assert result.cost_usd == pytest.approx(1e-4, rel=1e-6)
    assert client.messages.captured["model"] == TRANSLATE_MODEL_ID
    assert client.messages.captured["system"] == TRANSLATE_SYSTEM_PROMPT
    assert client.messages.captured["messages"] == [
        {"role": "user", "content": "Hello world"},
    ]


def test_translate_system_prompt_preserves_poker_jargon() -> None:
    for term in ["3-bet", "check-raise", "polarized", "villain", "hero"]:
        assert term in TRANSLATE_SYSTEM_PROMPT


def test_translate_rejects_empty_text(sample_pricing: PricingSnapshot) -> None:
    client = _FakeClient(_fake_message("", 0, 0))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(translate_to_french("", client=client, pricing=sample_pricing))


def test_translate_rejects_whitespace_only_text(sample_pricing: PricingSnapshot) -> None:
    client = _FakeClient(_fake_message("", 0, 0))
    with pytest.raises(ValueError, match="empty"):
        asyncio.run(translate_to_french("   \n\t ", client=client, pricing=sample_pricing))
