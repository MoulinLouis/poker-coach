"""Parity-test fixtures.

Provides:
- ``api_client`` - a synchronous FastAPI TestClient wired to a throwaway
  in-memory SQLite DB + dummy oracle factory (no LLM calls).
- ``BackendCoachClient`` - a CoachClient subclass that routes engine_* calls
  through the TestClient instead of httpx, so parity tests need no running
  server.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine

# ---------------------------------------------------------------------------
# Path: make sure backend package is importable even if not installed in this
# venv.  (When the path dep is properly installed via uv this is a no-op.)
# ---------------------------------------------------------------------------
_BACKEND_SRC = Path(__file__).resolve().parents[4] / "backend" / "src"
if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from poker_coach.api.app import create_app  # noqa: E402
from poker_coach.api.deps import OracleFactory  # noqa: E402
from poker_coach.oracle.base import ModelSpec, Oracle  # noqa: E402
from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot  # noqa: E402

from poker_rta.client.coach_client import CoachClient, EngineSnapshot  # noqa: E402

# ---------------------------------------------------------------------------
# Dummy oracle - raises if actually called (engine tests don't need LLM)
# ---------------------------------------------------------------------------


class _DummyOracle:
    async def advise_stream(self, rendered: Any, spec: Any) -> Any:
        if False:  # pragma: no cover
            yield None
        raise RuntimeError("dummy oracle must not be invoked in parity tests")


class _DummyOracleFactory(OracleFactory):
    def for_spec(self, spec: ModelSpec) -> Oracle:
        return _DummyOracle()  # type: ignore[return-value]


class _DummyAnthropicMessages:
    async def create(self, **kwargs: Any) -> Any:
        raise RuntimeError("dummy anthropic must not be invoked in parity tests")


class _DummyAnthropicClient:
    messages = _DummyAnthropicMessages()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _migrated_engine(tmp_path: Path) -> Engine:
    db_file = tmp_path / "parity_test.db"
    url = f"sqlite:///{db_file}"
    backend_root = Path(__file__).resolve().parents[4] / "backend"
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option(
        "script_location",
        str(backend_root / "src" / "poker_coach" / "db" / "migrations"),
    )
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return create_engine(url, future=True)


def _sample_pricing() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_date="2026-04-19",
        snapshot_source="parity-test",
        models={
            "gpt-5.3-codex": PricingEntry(input_per_mtok=1.75, output_per_mtok=14.0),
            "claude-haiku-4-5-20251001": PricingEntry(input_per_mtok=1.0, output_per_mtok=5.0),
        },
    )


@pytest.fixture
def api_client(tmp_path: Path) -> Iterator[TestClient]:
    """Synchronous TestClient over a fully-migrated throwaway SQLite DB."""
    db_engine = _migrated_engine(tmp_path)
    app = create_app(
        engine=db_engine,
        oracle_factory=_DummyOracleFactory(),
        pricing=_sample_pricing(),
        anthropic_client=_DummyAnthropicClient(),
        sweeper_interval_seconds=0,
    )
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# BackendCoachClient
# ---------------------------------------------------------------------------


class BackendCoachClient(CoachClient):
    """CoachClient backed by a FastAPI TestClient instead of a live httpx session.

    Only the ``engine_*`` methods are required by Task 7b.1; the rest
    delegate to stubs that raise NotImplementedError to keep the surface
    small until later tasks need them.

    Usage::

        with TestClient(app) as tc:
            client = BackendCoachClient(test_client=tc)
            snap = await client.engine_start(effective_stack=10000, bb=100, button="hero")
    """

    def __init__(self, *, test_client: TestClient) -> None:
        # Pass a dummy base_url; httpx is never used.
        super().__init__(base_url="http://testserver")
        self._tc = test_client

    # ------------------------------------------------------------------
    # engine_* overrides (synchronous TestClient, wrapped to be awaitable)
    # ------------------------------------------------------------------

    async def engine_start(
        self,
        *,
        effective_stack: int,
        bb: int,
        button: str,
        hero_hole: tuple[str, str] | None = None,
    ) -> EngineSnapshot:
        body: dict[str, Any] = {
            "effective_stack": effective_stack,
            "bb": bb,
            "button": button,
        }
        if hero_hole is not None:
            body["hero_hole"] = list(hero_hole)
        r = self._tc.post("/api/engine/start", json=body)
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    async def engine_apply(
        self,
        *,
        state: dict[str, Any],
        action: dict[str, Any],
    ) -> EngineSnapshot:
        r = self._tc.post("/api/engine/apply", json={"state": state, "action": action})
        if r.status_code == 400:
            raise ValueError(r.json().get("detail", "engine rejected"))
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    async def engine_reveal(
        self,
        *,
        state: dict[str, Any],
        cards: list[str],
    ) -> EngineSnapshot:
        r = self._tc.post("/api/engine/reveal", json={"state": state, "cards": cards})
        if r.status_code == 400:
            raise ValueError(r.json().get("detail", "engine rejected"))
        r.raise_for_status()
        d = r.json()
        return EngineSnapshot(state=d["state"], legal_actions=d["legal_actions"])

    # ------------------------------------------------------------------
    # Stubs for session/hand/decision lifecycle (not needed until 7b.3+)
    # ------------------------------------------------------------------

    async def create_session(self, mode: str = "live", notes: str | None = None) -> str:
        raise NotImplementedError("create_session stub — wire in a later task")

    async def create_hand(
        self,
        session_id: str,
        bb: int,
        starting_stack: int,
        rng_seed: int | None = None,
        deck_snapshot: list[str] | None = None,
    ) -> str:
        raise NotImplementedError("create_hand stub — wire in a later task")

    async def create_decision(
        self,
        session_id: str,
        hand_id: str | None,
        game_state: dict[str, Any],
        model_preset: str = "gpt-5.3-codex-xhigh",
        prompt_name: str = "coach",
        prompt_version: str = "v2",
        villain_profile: str = "unknown",
    ) -> str:
        raise NotImplementedError("create_decision stub — wire in a later task")
