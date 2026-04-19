"""Calibration doc → PlatformProfile. Pure-data layer; the Qt UI sits on top."""

from __future__ import annotations

from dataclasses import dataclass, field

from poker_rta.profile.model import (
    ROI,
    OCRPreprocess,
    PlatformProfile,
    WindowSelector,
)


@dataclass
class CalibrationDoc:
    name: str
    version: str
    window_title: str
    card_templates_dir: str
    button_templates: dict[str, str]
    rois: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)  # (x, y, w, h)
    ocr: OCRPreprocess = field(default_factory=OCRPreprocess)


def emit_profile(doc: CalibrationDoc) -> PlatformProfile:
    return PlatformProfile(
        name=doc.name,
        version=doc.version,
        window=WindowSelector(title_contains=doc.window_title),
        rois={k: ROI(x=x, y=y, width=w, height=h) for k, (x, y, w, h) in doc.rois.items()},
        card_templates_dir=doc.card_templates_dir,
        button_templates=doc.button_templates,
        ocr=doc.ocr,
    )
