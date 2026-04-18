from fastapi import APIRouter, Depends
from sqlalchemy import Engine, insert

from poker_coach.api.deps import get_engine
from poker_coach.api.schemas import CreateSessionRequest, CreateSessionResponse
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
            )
        )
    return CreateSessionResponse(session_id=session_id)
