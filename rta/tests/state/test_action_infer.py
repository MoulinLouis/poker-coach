from __future__ import annotations

from poker_rta.state.action_infer import infer_action


def test_call(snap):
    """delta>0, new_committed == villain_committed, stack>0 → call"""
    s = snap(
        committed={"hero": 50, "villain": 100},
        last_aggressor="villain",
        last_raise_size=100,
    )
    result = infer_action(
        prev_state=s.state,
        actor="hero",
        obs_committed={"hero": 100, "villain": 100},
        obs_stacks={"hero": 9900, "villain": 9900},
    )
    assert result == {"actor": "hero", "type": "call", "to_amount": None}


def test_raise(snap):
    """delta>0, new > villain, prior aggression → raise"""
    s = snap(
        committed={"hero": 100, "villain": 100},
        last_aggressor="villain",
        last_raise_size=100,
        street="preflop",
    )
    result = infer_action(
        prev_state=s.state,
        actor="hero",
        obs_committed={"hero": 300, "villain": 100},
        obs_stacks={"hero": 9700, "villain": 9900},
    )
    assert result == {"actor": "hero", "type": "raise", "to_amount": 300}


def test_check(snap):
    """delta=0, villain_committed == new_committed → check"""
    s = snap(
        committed={"hero": 100, "villain": 100},
        last_aggressor=None,
        last_raise_size=0,
        street="flop",
    )
    result = infer_action(
        prev_state=s.state,
        actor="hero",
        obs_committed={"hero": 100, "villain": 100},
        obs_stacks={"hero": 9900, "villain": 9900},
    )
    assert result == {"actor": "hero", "type": "check", "to_amount": None}


def test_flop_bet_no_prior_aggression(snap):
    """delta>0, new > villain, no prior aggression → bet"""
    s = snap(
        committed={"hero": 0, "villain": 0},
        last_aggressor=None,
        last_raise_size=0,
        street="flop",
    )
    result = infer_action(
        prev_state=s.state,
        actor="hero",
        obs_committed={"hero": 200, "villain": 0},
        obs_stacks={"hero": 9800, "villain": 10000},
    )
    assert result == {"actor": "hero", "type": "bet", "to_amount": 200}


def test_allin(snap):
    """stack hits 0 → allin"""
    s = snap(
        committed={"hero": 100, "villain": 100},
        last_aggressor="villain",
        last_raise_size=100,
        street="preflop",
    )
    result = infer_action(
        prev_state=s.state,
        actor="hero",
        obs_committed={"hero": 10000, "villain": 100},
        obs_stacks={"hero": 0, "villain": 9900},
    )
    assert result == {"actor": "hero", "type": "allin", "to_amount": 10000}
