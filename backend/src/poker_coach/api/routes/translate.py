"""POST /api/translate — one-shot EN→FR translation for UI display.

Stateless. No persistence. Translations are ephemeral UI aids, not
research data; logging them would bloat the decisions table and invite
questions about which "text" was authoritative for replay.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from poker_coach.api.deps import get_anthropic_client, get_pricing
from poker_coach.oracle.pricing import PricingSnapshot
from poker_coach.translation import translate_to_french

router = APIRouter()

_MAX_CHARS = 50_000


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    target_lang: str = "fr"


class TranslateResponse(BaseModel):
    translation: str
    cost_usd: float


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    client: Annotated[Any, Depends(get_anthropic_client)],
    pricing: Annotated[PricingSnapshot, Depends(get_pricing)],
) -> TranslateResponse:
    if body.target_lang != "fr":
        raise HTTPException(
            status_code=400,
            detail=f"unsupported target_lang: {body.target_lang}",
        )
    if len(body.text) > _MAX_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text exceeds {_MAX_CHARS} character limit",
        )
    try:
        result = await translate_to_french(body.text, client=client, pricing=pricing)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return TranslateResponse(
        translation=result.translation,
        cost_usd=result.cost_usd,
    )
