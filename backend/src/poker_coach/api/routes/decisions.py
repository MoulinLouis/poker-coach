"""Decision creation endpoint.

Does NOT invoke the oracle — just validates inputs, renders the prompt,
writes the in_flight row, and returns decision_id. The oracle call
actually happens when the SSE stream endpoint is opened (see stream.py).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, insert, select

from poker_coach.api.deps import get_engine, get_prompts_root
from poker_coach.api.schemas import CreateDecisionRequest, CreateDecisionResponse, DecisionSummary
from poker_coach.db.tables import decisions, hands, sessions
from poker_coach.ids import new_id
from poker_coach.oracle.presets import MODEL_PRESETS
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
        variables = state_to_coach_variables(body.game_state)
        rendered = renderer.render(body.prompt_name, body.prompt_version, variables)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"prompt render failed: {exc}") from exc

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
