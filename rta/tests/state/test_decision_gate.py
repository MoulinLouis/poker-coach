from __future__ import annotations

from poker_rta.state.decision_gate import GateDecision, should_fire_decision


def _fire(obs_factory, snap_factory, **overrides):
    """Helper: call should_fire_decision with sensible defaults."""
    obs = obs_factory()
    snap = snap_factory()
    kwargs = dict(
        state=snap.state,
        obs=obs,
        degraded=False,
        already_fired_for_state_id=None,
        state_id="s1",
        min_confidence=0.7,
    )
    kwargs.update(overrides)
    return should_fire_decision(**kwargs)


def test_ok(obs, snap):
    result = _fire(obs, snap)
    assert result == GateDecision(True, "ok")


def test_degraded(obs, snap):
    result = _fire(obs, snap, degraded=True)
    assert result.fire is False
    assert result.reason == "session degraded"


def test_not_hero(obs, snap):
    sn = snap(to_act="villain")
    result = should_fire_decision(
        state=sn.state,
        obs=obs(),
        degraded=False,
        already_fired_for_state_id=None,
        state_id="s1",
        min_confidence=0.7,
    )
    assert result.fire is False
    assert "to_act=" in result.reason
    assert "villain" in result.reason


def test_low_confidence(obs, snap):
    low_obs = obs(confidence={"hero_cards": 0.5})
    sn = snap()
    result = should_fire_decision(
        state=sn.state,
        obs=low_obs,
        degraded=False,
        already_fired_for_state_id=None,
        state_id="s1",
        min_confidence=0.7,
    )
    assert result.fire is False
    assert "hero_cards" in result.reason
    assert "0.50" in result.reason


def test_already_fired(obs, snap):
    result = _fire(obs, snap, already_fired_for_state_id="s1", state_id="s1")
    assert result.fire is False
    assert result.reason == "already fired"
