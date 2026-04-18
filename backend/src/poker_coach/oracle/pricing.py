"""Per-model pricing + cost calculation.

Pricing is loaded from `config/pricing.yaml` which carries two
provenance fields alongside the rates: `snapshot_date` (ISO timestamp
of when the rates were valid) and `snapshot_source` (e.g.
`anthropic_api_docs_2026-04-18` or `manual_config`). A copy of the
relevant entry is written into every decision row so historical cost
computations survive future price changes.

Reasoning/thinking tokens are billed at the output rate on both
platforms; callers should include them in the output_tokens total.
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


def compute_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    model_id: str,
    pricing: PricingSnapshot,
) -> tuple[float, dict[str, Any]]:
    """Returns (cost_usd, snapshot_dict) for logging.

    snapshot_dict is written into decisions.pricing_snapshot and includes the
    exact rates used plus the provenance fields — no need to re-read the
    pricing file to audit historical costs.
    """
    entry = pricing.models[model_id]
    cost = (input_tokens / 1_000_000.0) * entry.input_per_mtok + (
        output_tokens / 1_000_000.0
    ) * entry.output_per_mtok
    snapshot = {
        "snapshot_date": pricing.snapshot_date,
        "snapshot_source": pricing.snapshot_source,
        "model_id": model_id,
        "input_per_mtok": entry.input_per_mtok,
        "output_per_mtok": entry.output_per_mtok,
    }
    return cost, snapshot
