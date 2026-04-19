"""SSE stream endpoint for a decision.

Atomically claims the row (UPDATE ... WHERE stream_opened_at IS NULL),
invokes the oracle for the row's preset, and forwards OracleEvent
instances as SSE frames. On terminal event (or cancellation), writes
the final status, parsed advice, token usage, and cost back to the
decisions row.

Client disconnect → CancelledError → status="cancelled" with whatever
reasoning streamed so far preserved.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import Engine, and_, select, update

from poker_coach.api.deps import (
    OracleFactory,
    get_engine,
    get_oracle_factory,
)
from poker_coach.db.tables import decisions
from poker_coach.oracle.base import (
    ModelSpec,
    OracleError,
    ReasoningComplete,
    ReasoningDelta,
    ToolCallComplete,
    UsageComplete,
)
from poker_coach.oracle.presets import PRESETS_BY_MODEL
from poker_coach.prompts.renderer import RenderedPrompt

logger = logging.getLogger(__name__)

router = APIRouter()


def _sse(event_type: str, payload: dict[str, Any]) -> bytes:
    return f"event: {event_type}\ndata: {json.dumps(payload)}\n\n".encode()


@dataclass
class _StreamState:
    final_status: str = "in_flight"
    reasoning_text: str | None = None
    parsed_advice: dict[str, Any] | None = None
    raw_tool_input: dict[str, Any] | None = None
    error_message: str | None = None
    usage_fields: dict[str, Any] = field(default_factory=dict)


def _find_preset_for(model_id: str, provider: str) -> ModelSpec | None:
    return PRESETS_BY_MODEL.get((model_id, provider))


def _finalize(engine: Engine, decision_id: str, state: _StreamState, started_at: datetime) -> None:
    latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
    values: dict[str, Any] = {
        "status": state.final_status,
        "latency_ms": latency_ms,
        "reasoning_text": state.reasoning_text,
        "raw_tool_input": state.raw_tool_input,
        "parsed_advice": state.parsed_advice,
        "error_message": state.error_message,
    }
    values.update(state.usage_fields)
    with engine.begin() as conn:
        conn.execute(
            update(decisions).where(decisions.c.decision_id == decision_id).values(**values)
        )


@router.get("/decisions/{decision_id}/stream")
async def stream_decision(
    decision_id: str,
    engine: Engine = Depends(get_engine),
    oracle_factory: OracleFactory = Depends(get_oracle_factory),
) -> StreamingResponse:
    now = datetime.now(UTC)

    # Atomic claim. Refuses if stream_opened_at already set or status has
    # already moved on.
    with engine.begin() as conn:
        claim = conn.execute(
            update(decisions)
            .where(
                and_(
                    decisions.c.decision_id == decision_id,
                    decisions.c.stream_opened_at.is_(None),
                    decisions.c.status == "in_flight",
                )
            )
            .values(stream_opened_at=now)
        )
        if claim.rowcount == 0:
            existing = conn.execute(
                select(decisions.c.decision_id, decisions.c.status).where(
                    decisions.c.decision_id == decision_id
                )
            ).first()
            if existing is None:
                raise HTTPException(status_code=404, detail="decision not found")
            raise HTTPException(
                status_code=409,
                detail=f"stream already opened (status={existing.status})",
            )

        row = conn.execute(
            select(
                decisions.c.template_raw,
                decisions.c.rendered_prompt,
                decisions.c.template_hash,
                decisions.c.prompt_name,
                decisions.c.prompt_version,
                decisions.c.variables,
                decisions.c.provider,
                decisions.c.model_id,
                decisions.c.system_prompt,
            ).where(decisions.c.decision_id == decision_id)
        ).one()

    spec = _find_preset_for(model_id=row.model_id, provider=row.provider)
    if spec is None:
        raise HTTPException(
            status_code=500,
            detail=f"no preset matches provider={row.provider} model_id={row.model_id}",
        )

    rendered = RenderedPrompt(
        pack=row.prompt_name,
        version=row.prompt_version,
        template_hash=row.template_hash,
        template_raw=row.template_raw,
        rendered_prompt=row.rendered_prompt,
        variables=row.variables,
    )

    async def generate() -> Any:
        state = _StreamState()
        started_at = datetime.now(UTC)
        try:
            oracle = oracle_factory.for_spec(spec)
            async for event in oracle.advise_stream(
                rendered, spec, system_prompt=row.system_prompt
            ):
                if isinstance(event, ReasoningDelta):
                    yield _sse("reasoning_delta", {"text": event.text})
                elif isinstance(event, ReasoningComplete):
                    state.reasoning_text = event.full_text
                    yield _sse("reasoning_complete", {"full_text": event.full_text})
                elif isinstance(event, ToolCallComplete):
                    state.parsed_advice = event.advice.model_dump()
                    state.raw_tool_input = event.raw_tool_input
                    if state.final_status == "in_flight":
                        state.final_status = "ok"
                    yield _sse(
                        "tool_call_complete",
                        {"advice": state.parsed_advice, "raw_tool_input": state.raw_tool_input},
                    )
                elif isinstance(event, UsageComplete):
                    state.usage_fields = {
                        "input_tokens": event.input_tokens,
                        "output_tokens": event.output_tokens,
                        "reasoning_tokens": event.reasoning_tokens,
                        "total_tokens": event.total_tokens,
                        "cost_usd": event.cost_usd,
                        "pricing_snapshot": event.pricing_snapshot,
                    }
                    yield _sse("usage_complete", event.model_dump())
                elif isinstance(event, OracleError):
                    status_map = {
                        "invalid_schema": "invalid_response",
                        "illegal_action": "illegal_action",
                        "provider_error": "provider_error",
                        "internal": "provider_error",
                    }
                    state.final_status = status_map.get(event.kind, "provider_error")
                    state.error_message = event.message
                    state.raw_tool_input = event.raw_tool_input
                    yield _sse("oracle_error", event.model_dump())
            if state.final_status == "in_flight":
                # Oracle stream ended without a terminal event.
                state.final_status = "provider_error"
                state.error_message = "oracle stream ended without a terminal event"
            yield _sse(
                "done",
                {"status": state.final_status, "error_message": state.error_message},
            )
        except asyncio.CancelledError:
            state.final_status = "cancelled"
            raise
        except Exception as exc:
            state.final_status = "provider_error"
            state.error_message = f"{type(exc).__name__}: {exc}"
            with contextlib.suppress(ConnectionError, asyncio.CancelledError):
                yield _sse(
                    "oracle_error",
                    {"kind": "provider_error", "message": state.error_message},
                )
                yield _sse(
                    "done",
                    {"status": state.final_status, "error_message": state.error_message},
                )
        finally:
            _finalize(engine, decision_id, state, started_at)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
