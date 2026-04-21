"""Unit tests for the villain-stats aggregator.

Writes synthetic decisions directly into the DB (bypassing the API) so
we can control the action history per hand deterministically. Then
calls `compute_villain_stats` and asserts the rollups.

No oracle involved — this is a pure read aggregation.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import Engine, insert

from poker_coach.analytics import VillainStats, compute_villain_stats
from poker_coach.db.tables import decisions, hands, sessions
from poker_coach.ids import new_id

# Minimal but valid game_state snapshot shape — matches GameState.model_dump(mode="json").
_BASE_STATE: dict[str, Any] = {
    "hand_id": "",
    "bb": 100,
    "effective_stack": 10_000,
    "button": "hero",
    "hero_hole": ["As", "Kd"],
    "villain_hole": None,
    "board": [],
    "street": "preflop",
    "stacks": {"hero": 10_000, "villain": 10_000},
    "committed": {"hero": 0, "villain": 0},
    "pot": 0,
    "to_act": "hero",
    "last_aggressor": None,
    "last_raise_size": 0,
    "raises_open": True,
    "acted_this_street": [],
    "history": [],
    "rng_seed": None,
    "deck_snapshot": None,
    "pending_reveal": None,
    "reveals": [],
}


def _seed_session(engine: Engine) -> str:
    session_id = new_id()
    with engine.begin() as conn:
        conn.execute(insert(sessions).values(session_id=session_id, mode="live"))
    return session_id


def _insert_hand(
    engine: Engine,
    session_id: str,
    history: list[dict[str, Any]],
    board: list[str],
) -> None:
    """Insert one hand + one decision carrying the scripted history."""
    hand_id = new_id()
    decision_id = new_id()
    game_state = {**_BASE_STATE, "hand_id": hand_id, "history": history, "board": board}
    with engine.begin() as conn:
        conn.execute(
            insert(hands).values(
                hand_id=hand_id,
                session_id=session_id,
                bb=100,
                effective_stack_start=10_000,
            )
        )
        conn.execute(
            insert(decisions).values(
                decision_id=decision_id,
                session_id=session_id,
                hand_id=hand_id,
                game_state=game_state,
                prompt_name="coach",
                prompt_version="v2",
                template_hash="h",
                template_raw="t",
                rendered_prompt="p",
                variables={},
                villain_profile="unknown",
                provider="anthropic",
                model_id="x",
                status="ok",
            )
        )


def test_empty_session_returns_zeroed_stats(migrated_engine: Engine) -> None:
    session_id = _seed_session(migrated_engine)
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats == VillainStats(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def test_vpip_pfr_on_preflop_open_fold_line(migrated_engine: Engine) -> None:
    """Villain (BB) raises then hero folds in 10 hands — VPIP and PFR = 100%."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "raise", "to_amount": 900},
    ]
    for _ in range(10):
        _insert_hand(migrated_engine, session_id, history, board=[])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.hands_played == 10
    assert stats.vpip_pct == 100.0
    assert stats.pfr_pct == 100.0
    # 3-bet opportunity = facing hero's raise. Villain did 3-bet.
    assert stats.threebet_pct == 100.0


def test_vpip_without_pfr_on_flatcall(migrated_engine: Engine) -> None:
    """Villain calls hero's open each hand."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
    ]
    for _ in range(20):
        _insert_hand(migrated_engine, session_id, history, board=[])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.hands_played == 20
    assert stats.vpip_pct == 100.0
    assert stats.pfr_pct == 0.0
    # Villain faced a raise and did not re-raise → 0% 3-bet.
    assert stats.threebet_pct == 0.0


def test_agg_factor_counts_across_streets(migrated_engine: Engine) -> None:
    """3 bets + 1 raise = 4 aggressive, 2 calls → AF = 2.0."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
        {"actor": "villain", "type": "bet", "to_amount": 600},
        {"actor": "hero", "type": "raise", "to_amount": 1800},
        {"actor": "villain", "type": "call", "to_amount": None},
        {"actor": "villain", "type": "bet", "to_amount": 1500},
        {"actor": "villain", "type": "raise", "to_amount": 3000},
        {"actor": "villain", "type": "bet", "to_amount": 5000},
    ]
    _insert_hand(migrated_engine, session_id, history, board=["Ah", "7c", "2d"])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.hands_played == 1
    # Aggressive villain actions: bet, raise, bet, bet = 4. Calls: 2. AF = 2.0.
    assert stats.agg_factor == pytest.approx(2.0)


def test_cbet_when_villain_is_preflop_raiser(migrated_engine: Engine) -> None:
    """Villain raises preflop then bets flop — cbet hit."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "raise", "to_amount": 900},
        {"actor": "hero", "type": "call", "to_amount": None},
        # flop: villain was last preflop aggressor, bets first
        {"actor": "villain", "type": "bet", "to_amount": 1200},
    ]
    for _ in range(10):
        _insert_hand(migrated_engine, session_id, history, board=["Ah", "7c", "2d"])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.cbet_pct == 100.0


def test_fold_to_cbet_when_hero_is_preflop_raiser(migrated_engine: Engine) -> None:
    """Hero raises preflop, hero cbets, villain folds. 100% fold-to-cbet."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
        # flop: villain checks, hero cbets, villain folds
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "hero", "type": "bet", "to_amount": 500},
        {"actor": "villain", "type": "fold", "to_amount": None},
    ]
    for _ in range(12):
        _insert_hand(migrated_engine, session_id, history, board=["Ah", "7c", "2d"])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.fold_to_cbet_pct == 100.0


def test_twenty_hand_synthetic_session_headline_stats(migrated_engine: Engine) -> None:
    """End-to-end: 20 mixed hands, assert every headline stat."""
    session_id = _seed_session(migrated_engine)

    # 10 hands: villain 3-bets preflop, hero folds → VPIP+PFR+3bet all hit
    agg_history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "raise", "to_amount": 900},
    ]
    for _ in range(10):
        _insert_hand(migrated_engine, session_id, agg_history, board=[])

    # 10 hands: villain calls, to flop, villain check-folds (hero cbets)
    passive_history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "hero", "type": "bet", "to_amount": 500},
        {"actor": "villain", "type": "fold", "to_amount": None},
    ]
    for _ in range(10):
        _insert_hand(migrated_engine, session_id, passive_history, board=["Ah", "7c", "2d"])

    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.hands_played == 20
    # VPIP hit every hand (raise or call preflop) → 100%
    assert stats.vpip_pct == 100.0
    # PFR hit only on the 10 aggressive hands → 50%
    assert stats.pfr_pct == 50.0
    # 3-bet opportunity every hand (villain faces hero's raise); hit only 10 → 50%
    assert stats.threebet_pct == 50.0
    # Fold-to-cbet: opportunity in 10 passive hands (hero PFR + cbet); hit every time
    assert stats.fold_to_cbet_pct == 100.0


def test_gate_threshold_caller_checks_hands_played(migrated_engine: Engine) -> None:
    """Fewer than 10 hands: caller should suppress the prompt block, but
    the aggregator still returns a valid (possibly noisy) payload."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
    ]
    for _ in range(5):
        _insert_hand(migrated_engine, session_id, history, board=[])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.hands_played == 5
    # Less than 10 — caller's job to gate, not ours.


def test_limit_caps_window_to_recent_hands(migrated_engine: Engine) -> None:
    """Beyond `limit` hands are excluded from the aggregation."""
    session_id = _seed_session(migrated_engine)
    history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
    ]
    for _ in range(60):
        _insert_hand(migrated_engine, session_id, history, board=[])
    stats = compute_villain_stats(migrated_engine, session_id, limit=50)
    assert stats.hands_played == 50


def test_limp_flop_segments_preflop_correctly(migrated_engine: Engine) -> None:
    """BTN limps, BB checks, then a flop cbet by villain.

    With limp-segmentation broken, the flop bet gets misclassified as
    preflop (villain as PFR), skewing both pfr_pct and cbet tracking.
    """
    session_id = _seed_session(migrated_engine)
    # Hero = BTN here (hero limps), villain = BB checks, flop goes check/bet/fold
    history = [
        {"actor": "hero", "type": "call", "to_amount": None},
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "villain", "type": "bet", "to_amount": 150},
        {"actor": "hero", "type": "fold", "to_amount": None},
    ]
    for _ in range(12):
        _insert_hand(
            migrated_engine,
            session_id,
            history,
            board=["Ah", "7c", "2d"],
        )
    stats = compute_villain_stats(migrated_engine, session_id)
    # Villain never raised preflop — PFR must be 0
    assert stats.pfr_pct == 0.0
    # Villain checked preflop only — no 3bet opportunity
    assert stats.threebet_pct == 0.0


def test_wtsd_counts_showdown_hands(migrated_engine: Engine) -> None:
    """Hands with 5 board cards and no fold count as showdown reached."""
    session_id = _seed_session(migrated_engine)
    showdown_history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "call", "to_amount": None},
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "hero", "type": "check", "to_amount": None},
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "hero", "type": "check", "to_amount": None},
        {"actor": "villain", "type": "check", "to_amount": None},
        {"actor": "hero", "type": "check", "to_amount": None},
    ]
    for _ in range(10):
        _insert_hand(
            migrated_engine,
            session_id,
            showdown_history,
            board=["Ah", "7c", "2d", "5s", "Kh"],
        )
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.wtsd_pct == 100.0


def test_wtsd_excludes_fold_hands(migrated_engine: Engine) -> None:
    """Hands that end in a fold do not count as showdown reached."""
    session_id = _seed_session(migrated_engine)
    fold_history = [
        {"actor": "hero", "type": "raise", "to_amount": 300},
        {"actor": "villain", "type": "fold", "to_amount": None},
    ]
    for _ in range(10):
        _insert_hand(migrated_engine, session_id, fold_history, board=[])
    stats = compute_villain_stats(migrated_engine, session_id)
    assert stats.wtsd_pct == 0.0


def test_prompt_payload_shape_matches_template(migrated_engine: Engine) -> None:
    """Payload keys match what `coach/v2.md` references in the stats block."""
    payload = VillainStats.zero().as_prompt_payload()
    required = {
        "hands_played",
        "vpip_pct",
        "pfr_pct",
        "threebet_pct",
        "agg_factor",
        "cbet_pct",
        "fold_to_cbet_pct",
        "wtsd_pct",
    }
    assert required <= set(payload)
