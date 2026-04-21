from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, insert, select

from poker_coach.api.deps import get_engine
from poker_coach.api.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionDetail,
)
from poker_coach.db.tables import sessions
from poker_coach.ids import new_id

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    body: CreateSessionRequest,
    engine: Engine = Depends(get_engine),
) -> CreateSessionResponse:
    session_id = new_id()
    with engine.begin() as conn:
        conn.execute(
            insert(sessions).values(
                session_id=session_id,
                mode=body.mode,
                notes=body.notes,
                payout_structure=body.payout_structure,
                blind_level_label=body.blind_level_label,
            )
        )
    return CreateSessionResponse(session_id=session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: str,
    engine: Engine = Depends(get_engine),
) -> SessionDetail:
    with engine.connect() as conn:
        row = conn.execute(
            select(
                sessions.c.session_id,
                sessions.c.mode,
                sessions.c.notes,
                sessions.c.payout_structure,
                sessions.c.blind_level_label,
            ).where(sessions.c.session_id == session_id)
        ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"session {session_id} not found")
    return SessionDetail(
        session_id=row.session_id,
        mode=row.mode,
        notes=row.notes,
        payout_structure=row.payout_structure,
        blind_level_label=row.blind_level_label,
    )
