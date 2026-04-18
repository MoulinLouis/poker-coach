"""Lightweight EN→FR translation helper.

Deliberately separate from the oracle abstraction. The oracle is built
for structured tool-call streaming with event parsing; a one-shot text
translation with Haiku 4.5 is cleaner as a direct SDK call.

Cost is computed from the same PricingSnapshot used for decisions so
pricing updates propagate without code changes here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from poker_coach.oracle.pricing import PricingSnapshot, compute_cost

TRANSLATE_MODEL_ID = "claude-haiku-4-5-20251001"

TRANSLATE_SYSTEM_PROMPT = (
    "You are an EN→FR translator specialized for heads-up No-Limit Hold'em poker content. "
    "Translate the user's text to natural, fluent French. "
    "Keep these poker jargon terms EXACTLY as-is (do not translate): "
    "3-bet, 4-bet, 5-bet, check-raise, c-bet, polarized, range, board, flop, turn, river, "
    "villain, hero, BB, SB, limp, open, call, fold, raise, bet, all-in, GTO, EV, mix. "
    "Preserve punctuation, line breaks, and any markdown-like structure. "
    "Output ONLY the translation — no preamble, no commentary, no quotes."
)


class _AsyncMessages(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class _AsyncClient(Protocol):
    messages: _AsyncMessages


@dataclass(frozen=True)
class TranslationResult:
    translation: str
    cost_usd: float


async def translate_to_french(
    text: str,
    *,
    client: _AsyncClient,
    pricing: PricingSnapshot,
    max_tokens: int = 4096,
) -> TranslationResult:
    if not text.strip():
        raise ValueError("text is empty")

    message = await client.messages.create(
        model=TRANSLATE_MODEL_ID,
        max_tokens=max_tokens,
        system=TRANSLATE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )

    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    translation = "".join(parts).strip()

    cost, _ = compute_cost(
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
        model_id=TRANSLATE_MODEL_ID,
        pricing=pricing,
    )
    return TranslationResult(translation=translation, cost_usd=cost)
