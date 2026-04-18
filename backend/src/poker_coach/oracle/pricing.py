"""Per-model pricing + cost calculation.

Pricing is loaded from `config/pricing.yaml` which carries two
provenance fields alongside the rates: `snapshot_date` (ISO timestamp
of when the rates were valid) and `snapshot_source` (e.g.
`anthropic_api_docs_2026-04-18` or `manual_config`). A copy of the
relevant entry is written into every decision row so historical cost
computations survive future price changes.

Reasoning/thinking tokens are billed at the output rate on both
platforms; callers should include them in the output_tokens total.

Cache multipliers (`ANTHROPIC_CACHE_WRITE_MULTIPLIER`,
`ANTHROPIC_CACHE_READ_MULTIPLIER`) apply to Anthropic's 5-minute
ephemeral cache only. Cache-write tokens are billed at 1.25x the base
input rate; cache-read tokens at 0.1x. OpenAI's server-side auto-cache
is already discounted in the reported `input_tokens`, so OpenAI
callers pass 0 for both cache kwargs.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from poker_coach.settings import CONFIG_ROOT


class PricingEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float


class PricingSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_date: str
    snapshot_source: str
    models: dict[str, PricingEntry]


def load_pricing(path: Path | None = None) -> PricingSnapshot:
    yaml_path = path if path is not None else CONFIG_ROOT / "pricing.yaml"
    data = yaml.safe_load(yaml_path.read_text())
    return PricingSnapshot.model_validate(data)


@lru_cache(maxsize=1)
def default_pricing() -> PricingSnapshot:
    return load_pricing()


ANTHROPIC_CACHE_WRITE_MULTIPLIER = 1.25
ANTHROPIC_CACHE_READ_MULTIPLIER = 0.1


def compute_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    model_id: str,
    pricing: PricingSnapshot,
    cache_creation_input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
) -> tuple[float, dict[str, Any]]:
    """Returns (cost_usd, snapshot_dict) for logging.

    `input_tokens` is the NON-cached input (fresh tokens this request).
    Cache write/read tokens are billed separately with provider-specific
    multipliers — see module docstring. Defaults of 0 for the cache kwargs
    make this a no-op for callers that don't use caching.

    snapshot_dict is written into decisions.pricing_snapshot and includes the
    exact rates used plus the provenance fields — no need to re-read the
    pricing file to audit historical costs.
    """
    entry = pricing.models[model_id]
    effective_input_tokens = (
        input_tokens
        + cache_creation_input_tokens * ANTHROPIC_CACHE_WRITE_MULTIPLIER
        + cache_read_input_tokens * ANTHROPIC_CACHE_READ_MULTIPLIER
    )
    cost = (effective_input_tokens / 1_000_000.0) * entry.input_per_mtok + (
        output_tokens / 1_000_000.0
    ) * entry.output_per_mtok
    snapshot = {
        "snapshot_date": pricing.snapshot_date,
        "snapshot_source": pricing.snapshot_source,
        "model_id": model_id,
        "input_per_mtok": entry.input_per_mtok,
        "output_per_mtok": entry.output_per_mtok,
        "cache_write_multiplier": ANTHROPIC_CACHE_WRITE_MULTIPLIER,
        "cache_read_multiplier": ANTHROPIC_CACHE_READ_MULTIPLIER,
    }
    return cost, snapshot
