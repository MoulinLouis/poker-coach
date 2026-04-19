from __future__ import annotations

from poker_rta.state.hand_start import HandStartParams, detect_hand_start


def test_first_frame_blinds_match_hero_on_button(obs):
    """First frame with blinds matching → detects, hero on button if hero committed SB."""
    # hero_bet=50 (SB), villain_bet=100 (BB), bb=100 → hero is button (SB = button in HU)
    current = obs(
        hero_cards=("As", "Kd"),
        board=(),
        hero_bet_chips=50,
        villain_bet_chips=100,
        hero_stack_chips=9950,
        villain_stack_chips=9900,
    )
    result = detect_hand_start(prev=None, current=current, bb=100)
    assert isinstance(result, HandStartParams)
    assert result.button == "hero"
    assert result.bb == 100
    assert result.hero_hole == ("As", "Kd")
    assert result.effective_stack == min(9950 + 50, 9900 + 100)


def test_same_hole_cards_no_board_returns_none(obs):
    """Same hole cards + no board → None (no re-trigger)."""
    frame = obs(
        hero_cards=("As", "Kd"),
        board=(),
        hero_bet_chips=50,
        villain_bet_chips=100,
    )
    # First call would detect, but second with same prev → None
    result = detect_hand_start(prev=frame, current=frame, bb=100)
    assert result is None


def test_non_blind_committed_amounts_returns_none(obs):
    """Non-blind committed amounts → None (mid-hand, not a start)."""
    # hero has 300 in (a raise), villain has 200 in — doesn't match {50, 100}
    current = obs(
        hero_cards=("As", "Kd"),
        board=(),
        hero_bet_chips=300,
        villain_bet_chips=200,
    )
    result = detect_hand_start(prev=None, current=current, bb=100)
    assert result is None


def test_board_non_empty_returns_none(obs):
    """Board non-empty → None."""
    current = obs(
        hero_cards=("As", "Kd"),
        board=("Ah", "7c", "2d"),
        hero_bet_chips=50,
        villain_bet_chips=100,
    )
    result = detect_hand_start(prev=None, current=current, bb=100)
    assert result is None
