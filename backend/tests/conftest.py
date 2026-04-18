"""Shared pytest fixtures for API tests.

`api_app` builds a FastAPI app wired to a throwaway SQLite DB (migrated
up to head) and a stub oracle factory. Individual tests can override
the oracle factory by setting `app.state.oracle_factory = ...` or by
passing a custom factory via the `test_app_builder` fixture.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine

from poker_coach.api.app import create_app
from poker_coach.api.deps import OracleFactory
from poker_coach.oracle.base import ModelSpec, Oracle
from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot


class _DummyOracle:
    async def advise_stream(self, rendered: Any, spec: Any) -> Any:
        if False:  # pragma: no cover - makes this an async generator signature
            yield None
        raise RuntimeError("dummy oracle should not be invoked")


class _DummyOracleFactory(OracleFactory):
    def for_spec(self, spec: ModelSpec) -> Oracle:
        return _DummyOracle()  # type: ignore[return-value]


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Engine:
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    backend_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "src/poker_coach/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return create_engine(url, future=True)


@pytest.fixture
def sample_pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_date="2026-04-18",
        snapshot_source="test",
        models={
            "claude-opus-4-7": PricingEntry(input_per_mtok=15.0, output_per_mtok=75.0),
            "claude-haiku-4-5-20251001": PricingEntry(input_per_mtok=1.0, output_per_mtok=5.0),
            "gpt-5.3-codex": PricingEntry(input_per_mtok=1.75, output_per_mtok=14.0),
            "gpt-5.4": PricingEntry(input_per_mtok=1.25, output_per_mtok=10.0),
        },
    )


class _DummyAnthropicMessages:
    async def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("dummy anthropic client should not be invoked")


class _DummyAnthropicClient:
    messages = _DummyAnthropicMessages()


@pytest.fixture
def test_app_builder(
    migrated_engine: Engine,
    sample_pricing: PricingSnapshot,
) -> Callable[..., Any]:
    def _build(
        factory: OracleFactory | None = None,
        *,
        anthropic_client: Any | None = None,
    ) -> Any:
        return create_app(
            engine=migrated_engine,
            oracle_factory=factory or _DummyOracleFactory(),
            pricing=sample_pricing,
            anthropic_client=anthropic_client or _DummyAnthropicClient(),
            sweeper_interval_seconds=0,  # disabled; tests drive sweep_once directly
        )

    return _build


@pytest.fixture
def api_app(test_app_builder: Callable[..., Any]) -> Iterator[Any]:
    yield test_app_builder(None)
