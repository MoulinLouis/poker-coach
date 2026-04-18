from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from poker_coach.oracle.presets import DEFAULT_PRESET_ID, MODEL_PRESETS

router = APIRouter()


class PresetSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    selector_id: str
    provider: str
    model_id: str
    reasoning_effort: str | None
    thinking_budget: int | None


class PresetsResponse(BaseModel):
    default: str
    presets: list[PresetSummary]


@router.get("/presets", response_model=PresetsResponse)
def list_presets() -> PresetsResponse:
    return PresetsResponse(
        default=DEFAULT_PRESET_ID,
        presets=[
            PresetSummary(
                selector_id=spec.selector_id,
                provider=spec.provider,
                model_id=spec.model_id,
                reasoning_effort=spec.reasoning_effort,
                thinking_budget=spec.thinking_budget,
            )
            for spec in MODEL_PRESETS.values()
        ],
    )
