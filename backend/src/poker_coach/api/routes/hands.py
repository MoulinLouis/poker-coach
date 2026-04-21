from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, insert, select

from poker_coach.api.deps import get_engine
from poker_coach.api.schemas import CreateHandRequest, CreateHandResponse
from poker_coach.db.tables import hands, sessions
from poker_coach.ids import new_id

router = APIRouter()


@router.post("/hands", response_model=CreateHandResponse)
def create_hand(
    body: CreateHandRequest,
    engine: Engine = Depends(get_engine),
) -> CreateHandResponse:
    with engine.begin() as conn:
        row = conn.execute(
            select(sessions.c.session_id).where(sessions.c.session_id == body.session_id)
        ).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"session {body.session_id} not found")
        # Resolve stack shape same way start_hand does (legacy vs pair).
        if body.hero_stack_start is not None and body.villain_stack_start is not None:
            hero_s = body.hero_stack_start
            villain_s = body.villain_stack_start
        elif body.effective_stack_start is not None:
            hero_s = body.effective_stack_start
            villain_s = body.effective_stack_start
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    "must provide effective_stack_start OR both "
                    "hero_stack_start + villain_stack_start"
                ),
            )
        hand_id = new_id()
        conn.execute(
            insert(hands).values(
                hand_id=hand_id,
                session_id=body.session_id,
                bb=body.bb,
                ante=body.ante,
                effective_stack_start=min(hero_s, villain_s),
                hero_stack_start=hero_s,
                villain_stack_start=villain_s,
                rng_seed=body.rng_seed,
                deck_snapshot=body.deck_snapshot,
            )
        )
    return CreateHandResponse(hand_id=hand_id)
