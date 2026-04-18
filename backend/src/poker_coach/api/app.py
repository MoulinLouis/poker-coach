"""FastAPI app factory.

create_app() accepts all required resources explicitly so tests can wire
a throwaway SQLite DB + fake oracle factory + a sweeper that's either
disabled (interval=0) or driven manually via sweep_once.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from sqlalchemy import Engine

from poker_coach.api.deps import OracleFactory
from poker_coach.api.routes import (
    actions,
    cost,
    decisions,
    hands,
    health,
    presets,
    sessions,
    stream,
)
from poker_coach.api.routes import (
    engine as engine_routes,
)
from poker_coach.api.routes import (
    prompts as prompt_routes,
)
from poker_coach.api.sweeper import run_sweeper
from poker_coach.db.engine import default_engine
from poker_coach.oracle.pricing import PricingSnapshot, default_pricing
from poker_coach.settings import PROMPTS_ROOT


def create_app(
    *,
    engine: Engine | None = None,
    oracle_factory: OracleFactory | None = None,
    pricing: PricingSnapshot | None = None,
    prompts_root: Path | None = None,
    sweeper_interval_seconds: float = 30.0,
    abandoned_threshold_seconds: float = 30.0,
    timeout_threshold_seconds: float = 180.0,
) -> FastAPI:
    _engine = engine or default_engine()
    _pricing = pricing or default_pricing()
    _prompts_root = prompts_root or PROMPTS_ROOT

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = _engine
        app.state.pricing = _pricing
        app.state.prompts_root = _prompts_root
        if oracle_factory is None:
            raise RuntimeError(
                "oracle_factory must be supplied to create_app; production "
                "wiring should build a DefaultOracleFactory."
            )
        app.state.oracle_factory = oracle_factory

        sweeper_task: asyncio.Task[Any] | None = None
        if sweeper_interval_seconds > 0:
            sweeper_task = asyncio.create_task(
                run_sweeper(
                    _engine,
                    interval_seconds=sweeper_interval_seconds,
                    abandoned_seconds=abandoned_threshold_seconds,
                    timeout_seconds=timeout_threshold_seconds,
                )
            )
        app.state.sweeper_task = sweeper_task

        try:
            yield
        finally:
            if sweeper_task is not None:
                sweeper_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await sweeper_task

    app = FastAPI(title="poker-coach", version="0.0.0", lifespan=lifespan)
    app.include_router(health.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(hands.router, prefix="/api")
    app.include_router(decisions.router, prefix="/api")
    app.include_router(actions.router, prefix="/api")
    app.include_router(stream.router, prefix="/api")
    app.include_router(engine_routes.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    app.include_router(cost.router, prefix="/api")
    app.include_router(prompt_routes.router, prefix="/api")
    return app
