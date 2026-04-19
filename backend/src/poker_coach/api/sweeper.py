"""Background sweeper that transitions stale decision rows.

Two thresholds in a single pass:

- `stream_opened_at IS NULL AND created_at < now - abandoned_seconds`
  → status="abandoned". User POSTed a decision and never opened SSE
  (closed the tab, lost connection, etc.). No API cost incurred.

- `stream_opened_at < now - timeout_seconds AND status='in_flight'`
  → status="timeout". SSE was opened but the oracle never produced a
  terminal event. Covers crashes and hung upstream streams.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, and_, update

from poker_coach.db.tables import decisions

logger = logging.getLogger(__name__)


def sweep_once(
    engine: Engine,
    *,
    now: datetime | None = None,
    abandoned_seconds: float = 30.0,
    timeout_seconds: float = 180.0,
) -> tuple[int, int]:
    now = now or datetime.now(UTC)
    abandoned_cutoff = now - timedelta(seconds=abandoned_seconds)
    timeout_cutoff = now - timedelta(seconds=timeout_seconds)

    with engine.begin() as conn:
        abandoned_result = conn.execute(
            update(decisions)
            .where(
                and_(
                    decisions.c.status == "in_flight",
                    decisions.c.stream_opened_at.is_(None),
                    decisions.c.created_at < abandoned_cutoff,
                )
            )
            .values(status="abandoned")
        )
        timeout_result = conn.execute(
            update(decisions)
            .where(
                and_(
                    decisions.c.status == "in_flight",
                    decisions.c.stream_opened_at.isnot(None),
                    decisions.c.stream_opened_at < timeout_cutoff,
                )
            )
            .values(status="timeout")
        )

    return abandoned_result.rowcount or 0, timeout_result.rowcount or 0


async def run_sweeper(
    engine: Engine,
    *,
    interval_seconds: float = 30.0,
    abandoned_seconds: float = 30.0,
    timeout_seconds: float = 180.0,
) -> None:
    """Loop forever calling sweep_once. Cancel the task to stop."""
    while True:
        try:
            sweep_once(
                engine,
                abandoned_seconds=abandoned_seconds,
                timeout_seconds=timeout_seconds,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("sweeper tick failed")
        await asyncio.sleep(interval_seconds)
