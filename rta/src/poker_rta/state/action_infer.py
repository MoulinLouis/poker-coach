from __future__ import annotations

from typing import Any, Literal

Seat = Literal["hero", "villain"]


def infer_action(
    *,
    prev_state: dict[str, Any],
    actor: Seat,
    obs_committed: dict[str, int],
    obs_stacks: dict[str, int],
) -> dict[str, Any] | None:
    prev_committed = prev_state["committed"][actor]
    new_committed = obs_committed[actor]
    delta = new_committed - prev_committed
    if delta < 0:
        return None  # chips moved to pot between streets — not a new-street action
    other: Seat = "villain" if actor == "hero" else "hero"
    villain_committed = obs_committed[other]
    is_allin = obs_stacks[actor] == 0
    if delta == 0:
        if villain_committed == new_committed:
            return {"actor": actor, "type": "check", "to_amount": None}
        return None
    if new_committed == villain_committed:
        kind = "allin" if is_allin else "call"
        return {"actor": actor, "type": kind, "to_amount": new_committed if is_allin else None}
    if new_committed > villain_committed:
        had_aggression = (
            prev_state.get("last_aggressor") and prev_state.get("last_raise_size", 0) > 0
        )
        kind = "allin" if is_allin else ("raise" if had_aggression else "bet")
        return {"actor": actor, "type": kind, "to_amount": new_committed}
    return None
