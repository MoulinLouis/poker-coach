from __future__ import annotations

from typing import Any

import pytest

from poker_rta.cv.pipeline import FrameObservation


@pytest.fixture
def obs():
    """Factory for FrameObservation — override any field via kwargs."""

    def _make(**kw: Any) -> FrameObservation:
        base: dict[str, Any] = {
            "hero_cards": ("As", "Kd"),
            "board": (),
            "pot_chips": 150,
            "hero_stack_chips": 9950,
            "villain_stack_chips": 9900,
            "hero_bet_chips": 50,
            "villain_bet_chips": 100,
            "hero_is_button": True,
            "hero_to_act": True,
            "visible_buttons": frozenset({"fold", "call", "raise"}),
            "confidence": {},
        }
        base.update(kw)
        return FrameObservation(**base)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def snap():
    """Factory for a minimal EngineSnapshot-like object for mocked clients."""

    class _Snap:
        def __init__(self, state: dict[str, Any], legal: list[dict[str, Any]] | None = None):
            self.state = state
            self.legal_actions = legal or []

    def _make(**overrides: Any) -> _Snap:
        state: dict[str, Any] = {
            "hand_id": "h1",
            "bb": 100,
            "effective_stack": 10000,
            "button": "hero",
            "hero_hole": ["As", "Kd"],
            "villain_hole": None,
            "board": [],
            "street": "preflop",
            "stacks": {"hero": 9950, "villain": 9900},
            "committed": {"hero": 50, "villain": 100},
            "pot": 0,
            "to_act": "hero",
            "last_aggressor": "villain",
            "last_raise_size": 100,
            "raises_open": True,
            "acted_this_street": [],
            "history": [],
            "rng_seed": None,
            "deck_snapshot": None,
            "pending_reveal": None,
            "reveals": [],
        }
        state.update(overrides)
        return _Snap(state=state)

    return _make
