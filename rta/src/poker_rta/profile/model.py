"""Platform Profile — all site-specific config for the RTA pipeline.

A profile captures: where in the window to find each ROI, which card template
set to use, how to preprocess text for OCR, and optional timing hints. Swapping
profiles lets the same engine run on any target without code changes.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REQUIRED_ROIS: frozenset[str] = frozenset(
    {
        "hero_card_1",
        "hero_card_2",
        "board_1",
        "board_2",
        "board_3",
        "board_4",
        "board_5",
        "pot",
        "hero_stack",
        "villain_stack",
        "hero_bet",
        "villain_bet",
        "button_marker",
        "hero_action_highlight",
    }
)


class ROI(BaseModel):
    """A rectangular region of interest within the captured window."""

    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class WindowSelector(BaseModel):
    """How to find the target window on screen.

    Either `title_contains` (substring match on window title — platform-dependent
    look-up via the capture layer) or explicit `bbox` on the primary display.
    """

    model_config = ConfigDict(frozen=True)

    title_contains: str | None = None
    bbox: ROI | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> WindowSelector:
        if (self.title_contains is None) == (self.bbox is None):
            raise ValueError("WindowSelector needs exactly one of title_contains or bbox")
        return self


class OCRPreprocess(BaseModel):
    """Image preprocessing hints for the OCR step."""

    model_config = ConfigDict(frozen=True)

    grayscale: bool = True
    threshold: int | None = Field(default=None, ge=0, le=255)
    invert: bool = False
    scale: float = Field(default=1.0, gt=0.0, le=8.0)


class PlatformProfile(BaseModel):
    """Top-level profile describing one target platform."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = ""
    window: WindowSelector
    rois: dict[str, ROI]
    card_templates_dir: str = Field(min_length=1)
    button_templates: dict[str, str]
    ocr: OCRPreprocess
    capture_fps: float = Field(default=5.0, gt=0.0, le=30.0)
    your_turn_highlight_threshold: float = Field(default=0.90, ge=0.0, le=1.0)
    overlay_position: tuple[int, int] | None = None

    @field_validator("rois")
    @classmethod
    def _require_core_rois(cls, v: dict[str, ROI]) -> dict[str, ROI]:
        missing = REQUIRED_ROIS - v.keys()
        if missing:
            raise ValueError(f"profile missing required ROIs: {sorted(missing)}")
        return v
