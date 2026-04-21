"""Decision creation endpoint.

Does NOT invoke the oracle — just validates inputs, renders the prompt,
writes the in_flight row, and returns decision_id. The oracle call
actually happens when the SSE stream endpoint is opened (see stream.py).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, desc, insert, select

from poker_coach.analytics import compute_villain_stats
from poker_coach.api.deps import get_engine, get_prompts_root
from poker_coach.api.schemas import (
    CreateDecisionRequest,
    CreateDecisionResponse,
    DecisionDetail,
    DecisionListRow,
    DecisionSummary,
)
from poker_coach.db.tables import decisions, hands, sessions
from poker_coach.ids import new_id
from poker_coach.oracle.presets import MODEL_PRESETS
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer

router = APIRouter()


@router.post("/decisions", response_model=CreateDecisionResponse)
def create_decision(
    body: CreateDecisionRequest,
    engine: Engine = Depends(get_engine),
    prompts_root: Path = Depends(get_prompts_root),
) -> CreateDecisionResponse:
    spec = MODEL_PRESETS.get(body.model_preset)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"unknown model_preset {body.model_preset!r}",
        )

    renderer = PromptRenderer(prompts_root)
    try:
        villain_stats_payload: dict[str, object] | None = None
        uses_villain_block = body.prompt_version in ("v2", "v3")
        if uses_villain_block:
            stats = compute_villain_stats(engine, body.session_id, limit=50)
            villain_stats_payload = stats.as_prompt_payload()
        variables = state_to_coach_variables(
            body.game_state,
            villain_profile=body.villain_profile if uses_villain_block else None,
            villain_stats=villain_stats_payload,
            include_bb_chips=body.prompt_version == "v3",
        )
        rendered = renderer.render(body.prompt_name, body.prompt_version, variables)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"prompt render failed: {exc}") from exc

    system_prompt_snapshot = SYSTEM_PROMPT
    system_prompt_hash_snapshot = hashlib.sha256(system_prompt_snapshot.encode("utf-8")).hexdigest()

    with engine.begin() as conn:
        session_row = conn.execute(
            select(sessions.c.session_id).where(sessions.c.session_id == body.session_id)
        ).first()
        if session_row is None:
            raise HTTPException(status_code=404, detail=f"session {body.session_id} not found")
        if body.hand_id is not None:
            hand_row = conn.execute(
                select(hands.c.hand_id).where(hands.c.hand_id == body.hand_id)
            ).first()
            if hand_row is None:
                raise HTTPException(status_code=404, detail=f"hand {body.hand_id} not found")

        decision_id = new_id()
        conn.execute(
            insert(decisions).values(
                decision_id=decision_id,
                session_id=body.session_id,
                hand_id=body.hand_id,
                retry_of=body.retry_of,
                game_state=body.game_state.model_dump(mode="json"),
                prompt_name=rendered.pack,
                prompt_version=rendered.version,
                template_hash=rendered.template_hash,
                template_raw=rendered.template_raw,
                rendered_prompt=rendered.rendered_prompt,
                variables=variables,
                villain_profile=body.villain_profile,
                system_prompt=system_prompt_snapshot,
                system_prompt_hash=system_prompt_hash_snapshot,
                provider=spec.provider,
                model_id=spec.model_id,
                reasoning_effort=spec.reasoning_effort,
                thinking_budget=spec.thinking_budget,
                temperature=spec.temperature,
                status="in_flight",
            )
        )

    return CreateDecisionResponse(decision_id=decision_id)


@router.get("/decisions/{decision_id}", response_model=DecisionSummary)
def get_decision(
    decision_id: str,
    engine: Engine = Depends(get_engine),
) -> DecisionSummary:
    with engine.connect() as conn:
        row = conn.execute(
            select(
                decisions.c.decision_id,
                decisions.c.status,
                decisions.c.parsed_advice,
                decisions.c.cost_usd,
            ).where(decisions.c.decision_id == decision_id)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"decision {decision_id} not found")
    return DecisionSummary(
        decision_id=row.decision_id,
        status=row.status,
        parsed_advice=row.parsed_advice,
        cost_usd=row.cost_usd,
    )


@router.get("/decisions", response_model=list[DecisionListRow])
def list_decisions(
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    status: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DecisionListRow]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    stmt = (
        select(
            decisions.c.decision_id,
            decisions.c.created_at,
            decisions.c.session_id,
            decisions.c.hand_id,
            decisions.c.model_id,
            decisions.c.prompt_name,
            decisions.c.prompt_version,
            decisions.c.villain_profile,
            decisions.c.status,
            decisions.c.parsed_advice,
            decisions.c.cost_usd,
            decisions.c.latency_ms,
        )
        .order_by(desc(decisions.c.created_at))
        .limit(limit)
        .offset(offset)
    )
    if session_id:
        stmt = stmt.where(decisions.c.session_id == session_id)
    if model_id:
        stmt = stmt.where(decisions.c.model_id == model_id)
    if prompt_version:
        stmt = stmt.where(decisions.c.prompt_version == prompt_version)
    if status:
        stmt = stmt.where(decisions.c.status == status)

    with engine.connect() as conn:
        rows = conn.execute(stmt).all()
    return [
        DecisionListRow(
            decision_id=r.decision_id,
            created_at=r.created_at.isoformat() if r.created_at else "",
            session_id=r.session_id,
            hand_id=r.hand_id,
            model_id=r.model_id,
            prompt_name=r.prompt_name,
            prompt_version=r.prompt_version,
            villain_profile=r.villain_profile,
            status=r.status,
            parsed_advice=r.parsed_advice,
            cost_usd=r.cost_usd,
            latency_ms=r.latency_ms,
        )
        for r in rows
    ]


@router.get("/decisions/{decision_id}/detail", response_model=DecisionDetail)
def get_decision_detail(
    decision_id: str,
    engine: Engine = Depends(get_engine),
) -> DecisionDetail:
    with engine.connect() as conn:
        row = conn.execute(select(decisions).where(decisions.c.decision_id == decision_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"decision {decision_id} not found")
    return DecisionDetail(
        decision_id=row.decision_id,
        created_at=row.created_at.isoformat() if row.created_at else "",
        session_id=row.session_id,
        hand_id=row.hand_id,
        model_id=row.model_id,
        prompt_name=row.prompt_name,
        prompt_version=row.prompt_version,
        villain_profile=row.villain_profile,
        status=row.status,
        parsed_advice=row.parsed_advice,
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        game_state=row.game_state,
        template_hash=row.template_hash,
        template_raw=row.template_raw,
        rendered_prompt=row.rendered_prompt,
        system_prompt_hash=row.system_prompt_hash,
        reasoning_text=row.reasoning_text,
        raw_tool_input=row.raw_tool_input,
        reasoning_effort=row.reasoning_effort,
        thinking_budget=row.thinking_budget,
        temperature=row.temperature,
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        reasoning_tokens=row.reasoning_tokens,
        total_tokens=row.total_tokens,
        pricing_snapshot=row.pricing_snapshot,
        error_message=row.error_message,
        retry_of=row.retry_of,
    )
