"""Prompt-rendering parity: CV path vs frontend path.

Verifies that driving ``EngineSession`` with synthesized ``FrameObservation``s
and replaying the scripted hand via the backend engine API both produce engine
states that render to the *identical* coach-v2 prompt.  Also writes a golden
fixture on first run so subsequent runs catch accidental prompt drift.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from poker_coach.analytics import VillainStats
from poker_coach.engine.models import GameState
from poker_coach.prompts.context import state_to_coach_variables
from poker_coach.prompts.renderer import PromptRenderer
from poker_coach.settings import PROMPTS_ROOT


def _render(state: dict[str, Any]) -> str:
    gs = GameState.model_validate(state)
    renderer = PromptRenderer(PROMPTS_ROOT)
    result = renderer.render(
        pack="coach",
        version="v2",
        variables=state_to_coach_variables(
            gs,
            villain_profile="unknown",
            villain_stats=VillainStats.zero().as_prompt_payload(),
        ),
    )
    return result.rendered_prompt


def _strip_hand_id(text: str) -> str:
    # strip the variable part of hand_id if present in the rendered prompt
    return re.sub(r"hand_id: [0-9a-f\-]+", "hand_id: <stripped>", text)


async def test_prompt_renders_identically(api_client: TestClient) -> None:
    from parity.conftest import run_cv_path, run_frontend_path

    f_state = run_frontend_path(api_client)
    c_state = await run_cv_path(api_client)

    f_text = _strip_hand_id(_render(f_state))
    c_text = _strip_hand_id(_render(c_state))
    assert f_text == c_text

    golden = Path(__file__).parent / "golden_coach_v2.txt"
    if not golden.exists():
        golden.write_text(f_text)
    assert f_text == golden.read_text()
