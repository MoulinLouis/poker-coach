"""Project a GameState into the variable dict the coach prompt consumes.

Deliberately omits villain_hole and deck_snapshot so the prompt never
leaks information the hero can't see during live play. Spot-analysis
mode goes through this same projection.

villain_profile is conditional: when callers pass it, we include it in
the output dict (needed by coach/v2 which declares the variable).
Leaving it out keeps backward compatibility with coach/v1 which has
no such variable declared. The renderer rejects unexpected keys, so
this conditional inclusion is load-bearing: do not flip it to always-on.
"""

from typing import Any, Literal

from poker_coach.engine.models import GameState
from poker_coach.engine.rules import legal_actions

VillainProfile = Literal["reg", "unknown"]


def _bb(chips: int, bb: int) -> float:
    return round(chips / bb, 2)


def state_to_coach_variables(
    state: GameState,
    villain_profile: VillainProfile | None = None,
) -> dict[str, Any]:
    bb = state.bb
    history = [
        {
            "actor": a.actor,
            "type": a.type,
            "to_amount_bb": _bb(a.to_amount, bb) if a.to_amount is not None else None,
        }
        for a in state.history
    ]
    legal = [
        {
            "type": la.type,
            "min_to_bb": _bb(la.min_to, bb) if la.min_to is not None else None,
            "max_to_bb": _bb(la.max_to, bb) if la.max_to is not None else None,
        }
        for la in legal_actions(state)
    ]
    result: dict[str, Any] = {
        "street": state.street,
        "hero_hole": list(state.hero_hole),
        "board": list(state.board),
        "button": state.button,
        "pot_bb": _bb(state.pot, bb),
        "effective_bb": _bb(state.effective_stack, bb),
        "hero_stack_bb": _bb(state.stacks["hero"], bb),
        "villain_stack_bb": _bb(state.stacks["villain"], bb),
        "hero_committed_bb": _bb(state.committed["hero"], bb),
        "villain_committed_bb": _bb(state.committed["villain"], bb),
        "history": history,
        "legal_actions": legal,
    }
    if villain_profile is not None:
        result["villain_profile"] = villain_profile
    return result
