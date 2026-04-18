"""Oracle factory that picks the right provider implementation per ModelSpec."""

from __future__ import annotations

from typing import Any

from poker_coach.oracle.anthropic_oracle import (
    AnthropicOracle,
    real_anthropic_stream_caller,
)
from poker_coach.oracle.base import ModelSpec, Oracle
from poker_coach.oracle.openai_oracle import (
    OpenAIOracle,
    real_openai_stream_caller,
)
from poker_coach.oracle.pricing import PricingSnapshot


class DefaultOracleFactory:
    def __init__(
        self,
        pricing: PricingSnapshot,
        anthropic_client: Any | None = None,
        openai_client: Any | None = None,
    ) -> None:
        self.pricing = pricing
        self._anthropic_client = anthropic_client
        self._openai_client = openai_client

    def for_spec(self, spec: ModelSpec) -> Oracle:
        if spec.provider == "anthropic":
            if self._anthropic_client is None:
                raise RuntimeError(
                    "Anthropic client not configured. Set ANTHROPIC_API_KEY in .env."
                )
            return AnthropicOracle(
                stream_caller=real_anthropic_stream_caller(self._anthropic_client),
                pricing=self.pricing,
            )
        if spec.provider == "openai":
            if self._openai_client is None:
                raise RuntimeError("OpenAI client not configured. Set OPENAI_API_KEY in .env.")
            return OpenAIOracle(
                stream_caller=real_openai_stream_caller(self._openai_client),
                pricing=self.pricing,
            )
        raise NotImplementedError(f"provider {spec.provider!r} not wired")
