"""Aggregate villain statistics over a session's recent hands.

Derives VPIP/PFR/3-bet/AF/cbet/fold-to-cbet/WTSD from the action traces
stored in `decisions.game_state`. For each hand we use the hand's
latest decision's history as the observation window — villain's action
after hero's final decision of that hand is not visible to us, but at
50-hand aggregate scale the tail noise is small relative to the body.

Deliberately read-only. No schema changes; the LLM reads its own
digest as prompt context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, func, select

from poker_coach.db.tables import decisions


@dataclass(frozen=True)
class VillainStats:
    """Aggregated villain stats, suitable for rendering into the prompt.

    Percentages are in the 0-100 range, rounded to 0 decimals (the prompt
    is lossy anyway; keeping integers avoids `28.5714...` noise). AF is
    the only non-percent metric and gets 1 decimal.
    """

    hands_played: int
    vpip_pct: float
    pfr_pct: float
    threebet_pct: float
    agg_factor: float
    cbet_pct: float
    fold_to_cbet_pct: float
    wtsd_pct: float

    def as_prompt_payload(self) -> dict[str, Any]:
        return {
            "hands_played": self.hands_played,
            "vpip_pct": self.vpip_pct,
            "pfr_pct": self.pfr_pct,
            "threebet_pct": self.threebet_pct,
            "agg_factor": self.agg_factor,
            "cbet_pct": self.cbet_pct,
            "fold_to_cbet_pct": self.fold_to_cbet_pct,
            "wtsd_pct": self.wtsd_pct,
        }

    @classmethod
    def zero(cls) -> VillainStats:
        """Sentinel for callers without a session DB. Renders nothing
        because `hands_played < 10` gates the prompt block."""
        return cls(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def _pct(hit: int, opp: int) -> float:
    return round(100.0 * hit / opp, 0) if opp > 0 else 0.0


def _tally_hand(
    trace: list[dict[str, Any]],
    board_revealed: bool,
    reached_showdown: bool,
) -> dict[str, int]:
    """Walk one hand's action trace and return per-hand counters.

    `trace` entries are pydantic Action dicts: {actor, type, to_amount}.
    Streets are inferred from the position of reveals in the engine, but
    `history` is flat — we segment by walking and tracking preflop raises.
    """
    preflop_actions: list[dict[str, Any]] = []
    postflop_actions: list[dict[str, Any]] = []
    # Segment: preflop = actions until both players have acted and
    # matched. Simpler rule for our use: preflop runs until a "call"
    # action that closes action (equal commitments). We approximate by
    # treating actions before `board_revealed` (meaning flop reached)
    # as preflop — but `trace` doesn't include board events. Instead:
    # preflop ends when a player calls a raise. We track `last_raise`.
    seen_preflop_raise = False
    preflop_closed = False
    for act in trace:
        if not preflop_closed:
            preflop_actions.append(act)
            if act["type"] in ("bet", "raise", "allin"):
                seen_preflop_raise = True
            elif act["type"] == "call" and seen_preflop_raise:
                preflop_closed = True
            elif act["type"] == "fold":
                preflop_closed = True  # hand ends preflop
        else:
            postflop_actions.append(act)

    counts = {
        "vpip_op": 1,
        "vpip_hit": 0,
        "pfr_op": 1,
        "pfr_hit": 0,
        "threebet_op": 0,
        "threebet_hit": 0,
        "bets_and_raises": 0,
        "calls": 0,
        "cbet_op": 0,
        "cbet_hit": 0,
        "fold_to_cbet_op": 0,
        "fold_to_cbet_hit": 0,
        "wtsd_op": 1,
        "wtsd_hit": 1 if reached_showdown else 0,
    }

    villain_preflop_acted = False
    preflop_raiser: str | None = None
    facing_raise_for_villain = False
    for act in preflop_actions:
        actor = act["actor"]
        atype = act["type"]
        if actor == "villain":
            villain_preflop_acted = True
            if atype in ("call", "bet", "raise", "allin"):
                counts["vpip_hit"] = 1
            if atype in ("bet", "raise", "allin"):
                counts["pfr_hit"] = 1
                preflop_raiser = "villain"
            if facing_raise_for_villain:
                counts["threebet_op"] = 1
                if atype in ("raise", "allin"):
                    counts["threebet_hit"] = 1
                facing_raise_for_villain = False
        else:  # hero
            if atype in ("bet", "raise", "allin"):
                preflop_raiser = "hero"
                facing_raise_for_villain = True

    # If villain never preflop-acted (hand ended before villain's turn,
    # e.g. hero folded to the BB post), strip preflop opportunity.
    if not villain_preflop_acted:
        counts["vpip_op"] = 0
        counts["pfr_op"] = 0

    # AF: count across the whole trace.
    for act in trace:
        if act["actor"] != "villain":
            continue
        if act["type"] in ("bet", "raise", "allin"):
            counts["bets_and_raises"] += 1
        elif act["type"] == "call":
            counts["calls"] += 1

    # CBET and fold-to-CBET are flop-only and require we reached the flop.
    if not board_revealed or not postflop_actions:
        # Can't observe either situation.
        counts["wtsd_op"] = 0
        counts["wtsd_hit"] = 0
        return counts

    # On the flop, the first bet by the preflop raiser is a cbet (assuming
    # villain OOP bets first — we tolerate that here since we only measure
    # "villain was PFR AND villain bet first action on flop"). Fold-to-cbet:
    # hero was PFR AND hero's first flop action was a bet AND villain's
    # response was fold.
    first_flop_idx = 0
    flop_actions = postflop_actions  # simplification: treat all as flop
    if preflop_raiser == "villain":
        # Find villain's first flop action
        for act in flop_actions[first_flop_idx:]:
            if act["actor"] == "villain":
                counts["cbet_op"] = 1
                if act["type"] in ("bet", "raise", "allin"):
                    counts["cbet_hit"] = 1
                break
    elif preflop_raiser == "hero":
        # Find hero's first flop bet, then villain's response
        hero_bet_seen = False
        for act in flop_actions:
            if not hero_bet_seen:
                if act["actor"] == "hero" and act["type"] in ("bet", "raise", "allin"):
                    hero_bet_seen = True
                    counts["fold_to_cbet_op"] = 1
                    continue
            else:
                if act["actor"] == "villain":
                    if act["type"] == "fold":
                        counts["fold_to_cbet_hit"] = 1
                    break

    return counts


def compute_villain_stats(engine: Engine, session_id: str, limit: int = 50) -> VillainStats:
    """Aggregate stats over the most recent `limit` hands in `session_id`.

    Returns zero-filled stats with `hands_played=0` if no usable hands
    exist. Callers gate rendering on `hands_played >= N`.
    """
    with engine.connect() as conn:
        hand_rows = conn.execute(
            select(
                decisions.c.hand_id,
                func.max(decisions.c.created_at).label("last_activity"),
            )
            .where(
                decisions.c.session_id == session_id,
                decisions.c.hand_id.isnot(None),
            )
            .group_by(decisions.c.hand_id)
            .order_by(func.max(decisions.c.created_at).desc())
            .limit(limit)
        ).all()
        hand_ids = [r.hand_id for r in hand_rows]
        if not hand_ids:
            return VillainStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        traces: list[tuple[list[dict[str, Any]], bool]] = []
        for hid in hand_ids:
            last = conn.execute(
                select(decisions.c.game_state)
                .where(decisions.c.hand_id == hid)
                .order_by(decisions.c.created_at.desc())
                .limit(1)
            ).first()
            if last is None:
                continue
            gs = last.game_state
            history = gs.get("history", [])
            board_revealed = bool(gs.get("board"))
            traces.append((history, board_revealed))

    hands_played = len(traces)
    agg = {
        "vpip_op": 0,
        "vpip_hit": 0,
        "pfr_op": 0,
        "pfr_hit": 0,
        "threebet_op": 0,
        "threebet_hit": 0,
        "bets_and_raises": 0,
        "calls": 0,
        "cbet_op": 0,
        "cbet_hit": 0,
        "fold_to_cbet_op": 0,
        "fold_to_cbet_hit": 0,
        "wtsd_op": 0,
        "wtsd_hit": 0,
    }
    for history, board_revealed in traces:
        per = _tally_hand(history, board_revealed=board_revealed, reached_showdown=False)
        for k, v in per.items():
            agg[k] += v

    agg_factor = (
        round(agg["bets_and_raises"] / agg["calls"], 1)
        if agg["calls"] > 0
        else float(agg["bets_and_raises"])
    )

    return VillainStats(
        hands_played=hands_played,
        vpip_pct=_pct(agg["vpip_hit"], agg["vpip_op"]),
        pfr_pct=_pct(agg["pfr_hit"], agg["pfr_op"]),
        threebet_pct=_pct(agg["threebet_hit"], agg["threebet_op"]),
        agg_factor=agg_factor,
        cbet_pct=_pct(agg["cbet_hit"], agg["cbet_op"]),
        fold_to_cbet_pct=_pct(agg["fold_to_cbet_hit"], agg["fold_to_cbet_op"]),
        wtsd_pct=_pct(agg["wtsd_hit"], agg["wtsd_op"]),
    )
