from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, insert, select

from poker_coach.api.deps import get_engine
from poker_coach.api.schemas import RecordActionRequest, RecordActionResponse
from poker_coach.db.tables import actual_actions, decisions

router = APIRouter()


@router.post("/actions", response_model=RecordActionResponse)
def record_action(
    body: RecordActionRequest,
    engine: Engine = Depends(get_engine),
) -> RecordActionResponse:
    with engine.begin() as conn:
        row = conn.execute(
            select(decisions.c.decision_id).where(decisions.c.decision_id == body.decision_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"decision {body.decision_id} not found")
        result = conn.execute(
            insert(actual_actions).values(
                decision_id=body.decision_id,
                action_type=body.action.type,
                to_amount=body.action.to_amount,
            )
        )
    pk = result.inserted_primary_key
    assert pk is not None, "insert did not return a primary key"
    return RecordActionResponse(id=int(pk[0]))
