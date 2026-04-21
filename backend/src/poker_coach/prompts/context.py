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
    villain_stats: dict[str, Any] | None = None,
    include_bb_chips: bool = False,
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
    pot_bb = _bb(state.pot, bb)
    pot_bb_live = round((state.pot + sum(state.committed.values())) / bb, 2)
    ante_bb = _bb(state.ante, bb)
    effective_bb = _bb(state.effective_stack, bb)
    # SPR uses live pot; guard against the preflop pre-action pot being ~0
    # so the ratio stays a meaningful scalar rather than exploding.
    spr_bb = round(effective_bb / max(pot_bb, 0.5), 1)
    if effective_bb < 50:
        stack_depth_bucket = "shallow"
    elif effective_bb > 150:
        stack_depth_bucket = "deep"
    else:
        stack_depth_bucket = "standard"
    result: dict[str, Any] = {
        "street": state.street,
        "hero_hole": list(state.hero_hole),
        "board": list(state.board),
        "button": state.button,
        "pot_bb": pot_bb,
        "pot_bb_live": pot_bb_live,
        "ante_bb": ante_bb,
        "effective_bb": effective_bb,
        "hero_stack_bb": _bb(state.stacks["hero"], bb),
        "villain_stack_bb": _bb(state.stacks["villain"], bb),
        "hero_committed_bb": _bb(state.committed["hero"], bb),
        "villain_committed_bb": _bb(state.committed["villain"], bb),
        "stack_depth_bucket": stack_depth_bucket,
        "spr_bb": spr_bb,
        "history": history,
        "legal_actions": legal,
    }
    if villain_profile is not None:
        result["villain_profile"] = villain_profile
    if villain_stats is not None:
        result["villain_stats"] = villain_stats
    if include_bb_chips:
        result["bb_chips"] = state.bb
    return result
