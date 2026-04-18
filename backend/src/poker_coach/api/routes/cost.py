"""Cost aggregation endpoints.

Reads decisions.cost_usd grouped by (model_id, reasoning_effort) so the
frontend footer can show totals + a per-preset breakdown. Null
reasoning_effort (Anthropic presets) is surfaced as the string "none"
so the UI has a stable key.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Engine, func, select

from poker_coach.api.deps import get_engine
from poker_coach.db.tables import decisions

router = APIRouter()


class CostBreakdownRow(BaseModel):
    model_id: str
    reasoning_effort: str
    decision_count: int
    cost_usd: float


class CostResponse(BaseModel):
    session_usd: float
    all_time_usd: float
    by_model: list[CostBreakdownRow]


@router.get("/cost", response_model=CostResponse)
def get_cost(
    session_id: str | None = None,
    engine: Engine = Depends(get_engine),
) -> CostResponse:
    with engine.connect() as conn:
        all_time_total = conn.execute(
            select(func.coalesce(func.sum(decisions.c.cost_usd), 0.0))
        ).scalar_one()

        session_total = 0.0
        if session_id is not None:
            session_total = (
                conn.execute(
                    select(func.coalesce(func.sum(decisions.c.cost_usd), 0.0)).where(
                        decisions.c.session_id == session_id
                    )
                ).scalar_one()
                or 0.0
            )

        breakdown_rows = conn.execute(
            select(
                decisions.c.model_id,
                decisions.c.reasoning_effort,
                func.count().label("n"),
                func.coalesce(func.sum(decisions.c.cost_usd), 0.0).label("total"),
            )
            .where(decisions.c.cost_usd.isnot(None))
            .group_by(decisions.c.model_id, decisions.c.reasoning_effort)
            .order_by(func.sum(decisions.c.cost_usd).desc())
        ).all()

    breakdown = [
        CostBreakdownRow(
            model_id=row.model_id,
            reasoning_effort=row.reasoning_effort or "none",
            decision_count=int(row.n),
            cost_usd=float(row.total or 0.0),
        )
        for row in breakdown_rows
    ]

    return CostResponse(
        session_usd=float(session_total or 0.0),
        all_time_usd=float(all_time_total or 0.0),
        by_model=breakdown,
    )
