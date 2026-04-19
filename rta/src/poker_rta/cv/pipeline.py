"""Single-frame observation: given one screenshot + profile, extract every
poker-relevant fact we can see. No state, no memory — that's the tracker's job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from poker_rta.capture.grab import crop_roi
from poker_rta.cv.buttons import ButtonDetector
from poker_rta.cv.cards import CardClassifier, classify_card
from poker_rta.cv.ocr import NumberReader
from poker_rta.profile.model import PlatformProfile


@dataclass(frozen=True)
class FrameObservation:
    hero_cards: tuple[str, str] | None
    board: tuple[str, ...]
    pot_chips: int | None
    hero_stack_chips: int | None
    villain_stack_chips: int | None
    hero_bet_chips: int | None
    villain_bet_chips: int | None
    hero_is_button: bool
    hero_to_act: bool
    visible_buttons: frozenset[str]
    confidence: dict[str, float] = field(default_factory=dict)


def _read_cards(
    img: np.ndarray,
    profile: PlatformProfile,
    classifier: CardClassifier,
    names: list[str],
) -> list[str | None]:
    return [classify_card(crop_roi(img, profile.rois[n]), classifier) for n in names]


def _brightness(img: np.ndarray) -> float:
    return float(img.mean()) / 255.0


def observe_frame(
    img: np.ndarray,
    profile: PlatformProfile,
    classifier: CardClassifier,
    ocr: NumberReader | None = None,
    button_detector: ButtonDetector | None = None,
) -> FrameObservation:
    ocr = ocr or NumberReader(profile.ocr)
    if button_detector is None:
        buttons_root = Path(profile.card_templates_dir).parent / "buttons"
        button_detector = (
            ButtonDetector({k: Path(v) for k, v in profile.button_templates.items()})
            if (buttons_root.exists() and profile.button_templates)
            else None
        )

    hero1, hero2 = _read_cards(img, profile, classifier, ["hero_card_1", "hero_card_2"])
    board_raw = _read_cards(
        img,
        profile,
        classifier,
        ["board_1", "board_2", "board_3", "board_4", "board_5"],
    )
    board = tuple(c for c in board_raw if c is not None)

    pot = ocr.read(crop_roi(img, profile.rois["pot"]))
    h_stack = ocr.read(crop_roi(img, profile.rois["hero_stack"]))
    v_stack = ocr.read(crop_roi(img, profile.rois["villain_stack"]))
    h_bet = ocr.read(crop_roi(img, profile.rois["hero_bet"]))
    v_bet = ocr.read(crop_roi(img, profile.rois["villain_bet"]))

    btn_crop = crop_roi(img, profile.rois["button_marker"])
    hero_is_button = _brightness(btn_crop) > 0.3

    highlight_crop = crop_roi(img, profile.rois["hero_action_highlight"])
    hero_to_act = _brightness(highlight_crop) >= profile.your_turn_highlight_threshold

    visible = frozenset(button_detector.detect(highlight_crop) if button_detector else ())

    return FrameObservation(
        hero_cards=(hero1, hero2) if hero1 and hero2 else None,
        board=board,
        pot_chips=pot,
        hero_stack_chips=h_stack,
        villain_stack_chips=v_stack,
        hero_bet_chips=h_bet,
        villain_bet_chips=v_bet,
        hero_is_button=hero_is_button,
        hero_to_act=hero_to_act,
        visible_buttons=visible,
    )
