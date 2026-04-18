"""Production entrypoint: `uvicorn poker_coach.main:app`."""

from __future__ import annotations

import anthropic
import openai

from poker_coach.api.app import create_app
from poker_coach.api.oracle_factory import DefaultOracleFactory
from poker_coach.oracle.pricing import default_pricing
from poker_coach.settings import settings


def _build_anthropic_client() -> anthropic.AsyncAnthropic | None:
    if settings.anthropic_api_key:
        return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return None


def _build_oracle_factory(
    anthropic_client: anthropic.AsyncAnthropic | None,
) -> DefaultOracleFactory:
    openai_client: openai.AsyncOpenAI | None = None
    if settings.openai_api_key:
        openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
    return DefaultOracleFactory(
        pricing=default_pricing(),
        anthropic_client=anthropic_client,
        openai_client=openai_client,
    )


_anthropic_client = _build_anthropic_client()

app = create_app(
    oracle_factory=_build_oracle_factory(_anthropic_client),
    anthropic_client=_anthropic_client,
)
