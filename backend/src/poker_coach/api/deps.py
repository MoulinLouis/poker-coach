"""FastAPI dependency helpers.

Resources (DB engine, pricing, oracle factory, sweeper task) live on
app.state. Tests override them by writing the fakes they want before
the test client is spun up.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import Request
from sqlalchemy import Engine

from poker_coach.oracle.base import ModelSpec, Oracle
from poker_coach.oracle.pricing import PricingSnapshot


class OracleFactory(Protocol):
    def for_spec(self, spec: ModelSpec) -> Oracle: ...


def get_engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def get_oracle_factory(request: Request) -> OracleFactory:
    factory: OracleFactory = request.app.state.oracle_factory
    return factory


def get_pricing(request: Request) -> PricingSnapshot:
    pricing: PricingSnapshot = request.app.state.pricing
    return pricing


def get_prompts_root(request: Request) -> Any:
    return request.app.state.prompts_root


def get_anthropic_client(request: Request) -> Any:
    client = getattr(request.app.state, "anthropic_client", None)
    if client is None:
        raise RuntimeError(
            "anthropic_client not configured on app.state; "
            "production wiring should create one at startup."
        )
    return client
