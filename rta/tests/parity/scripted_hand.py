"""Canonical scripted hand for parity tests.

Derives a deterministic 4-step hand from the engine:
  1. Start (preflop, hero SB/button raises)
  2. Villain calls → pending_reveal (flop)
  3. Board reveal (Ah, 7c, 2d) → flop, villain acts first (checks)
  4. Villain checks → hero to act

HAND_START    - body for POST /api/engine/start
SCRIPTED_ACTIONS - sequence of Action dicts to drive the hand forward.
                   Each entry is POSTed to /api/engine/apply (or the reveal
                   endpoint for reveal steps) in order.

The mock_html SCRIPT (game.js) shows:
  step 0 - preflop: hero As/Kd, SB=150, BB=300, heroTurn=True (hero raised)
  step 1 - flop:    board Ah/7c/2d, pot=600, both even (villain just called,
                    villain acts first, heroTurn=False)
  step 2 - flop:    villain bet 300, heroTurn=True
  ...

We map this to a clean engine sequence.  hero=button=SB, bb=100,
effective_stack=10000.

Engine preflop forced bets: SB posts 50, BB posts 100.
  Action 0: hero raises to 300 (3xBB raise-to, matching mock's SB=150 ~= 1.5BB
             but 300 chips is cleaner for "Raise 450" = bet 450 total; we use
             300 for "raise-to 300" which means 300 committed -> pot = 600).
  Action 1: villain calls.
  [reveal]  board = ["Ah", "7c", "2d"]
  Action 2: villain checks (to_act=villain after flop reveal for OOP/BB).
  → hero to act on flop (matches mock step 2 reversed; hero is BTN=SB, so
    villain is BB=OOP, checks first, hero faces first real decision).

Actually in HU: BTN/SB acts first preflop (as raiser); post-flop BTN acts
last (IP).  So after the flop reveal: villain (BB, OOP) acts first, checks;
hero (BTN, IP) faces the check.

SCRIPTED_ACTIONS entries of type "reveal" use {"type": "reveal", "cards": [...]}
to signal the caller to route to /api/engine/reveal instead of /api/engine/apply.
"""

from __future__ import annotations

from typing import Any

# ── hand start ────────────────────────────────────────────────────────────────
# hero_hole pinned for determinism; villain_hole omitted (stays hidden from LLM)
HAND_START: dict[str, Any] = {
    "effective_stack": 10000,
    "bb": 100,
    "button": "hero",
    "hero_hole": ["As", "Kd"],
    "villain_hole": ["Qc", "Qh"],  # pinned so engine state is reproducible
}

# ── action sequence ───────────────────────────────────────────────────────────
# Each entry is either:
#   {"actor": ..., "type": ..., "to_amount": ...}  → POST /api/engine/apply
#   {"type": "reveal", "cards": [...]}               → POST /api/engine/reveal
#
# Step-by-step:
#   0. hero raises to 300 (preflop open from SB/BTN).
#      SB posted 50, so hero already has 50 committed; raise-to 300.
#   1. villain calls (BB posted 100; call brings villain to 300 committed).
#      → pending_reveal="flop" set by engine after all-in or callers even up.
#   2. reveal flop ["Ah", "7c", "2d"]
#      → to_act=villain (OOP BB checks or bets first post-flop in HU).
#   3. villain checks.
#      → to_act=hero (IP BTN, first hero-to-act flop situation).
SCRIPTED_ACTIONS: list[dict[str, Any]] = [
    # preflop: hero (BTN/SB) raises to 300
    {"actor": "hero", "type": "raise", "to_amount": 300},
    # preflop: villain (BB) calls
    {"actor": "villain", "type": "call"},
    # board reveal: flop
    {"type": "reveal", "cards": ["Ah", "7c", "2d"]},
    # flop: villain (OOP) checks
    {"actor": "villain", "type": "check"},
    # → hero is now to_act on the flop (end of scripted sequence)
]

# ── convenience: number of steps that land us at a hero-to-act flop state ────
# After replaying all SCRIPTED_ACTIONS the resulting EngineSnapshot has
# to_act="hero", street="flop", board=["Ah","7c","2d"].
FINAL_STEP_INDEX = len(SCRIPTED_ACTIONS) - 1
