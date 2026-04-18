from pathlib import Path

from poker_coach.oracle.presets import MODEL_PRESETS
from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot, compute_cost, load_pricing


def test_default_pricing_yaml_loads() -> None:
    pricing = load_pricing()
    assert pricing.snapshot_date
    assert pricing.snapshot_source
    # Every preset must have a pricing entry
    for spec in MODEL_PRESETS.values():
        assert spec.model_id in pricing.models, f"missing pricing for {spec.model_id}"


def test_compute_cost_formula() -> None:
    pricing = PricingSnapshot(
        snapshot_date="2026-04-18",
        snapshot_source="test",
        models={"example": PricingEntry(input_per_mtok=2.0, output_per_mtok=10.0)},
    )
    cost, snapshot = compute_cost(
        input_tokens=500_000,
        output_tokens=100_000,
        model_id="example",
        pricing=pricing,
    )
    # 0.5 * 2.0 + 0.1 * 10.0 = 1.0 + 1.0 = 2.0
    assert cost == 2.0
    assert snapshot["snapshot_date"] == "2026-04-18"
    assert snapshot["snapshot_source"] == "test"
    assert snapshot["model_id"] == "example"
    assert snapshot["input_per_mtok"] == 2.0
    assert snapshot["output_per_mtok"] == 10.0


def test_compute_cost_on_real_pricing(tmp_path: Path) -> None:
    pricing = load_pricing()
    cost, _ = compute_cost(
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        model_id="gpt-5.3-codex",
        pricing=pricing,
    )
    # From config: 1.75 + 14.00 = 15.75 per 1M+1M
    assert cost == 15.75
