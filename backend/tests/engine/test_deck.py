from poker_coach.engine.deck import (
    CANONICAL_DECK,
    deal_flop,
    deal_hero_hole,
    deal_river,
    deal_turn,
    deal_villain_hole,
    is_valid_card,
    seeded_shuffle,
)


def test_canonical_deck_has_52_unique_cards() -> None:
    assert len(CANONICAL_DECK) == 52
    assert len(set(CANONICAL_DECK)) == 52
    for card in CANONICAL_DECK:
        assert is_valid_card(card)


def test_seeded_shuffle_is_deterministic() -> None:
    assert seeded_shuffle(42) == seeded_shuffle(42)


def test_seeded_shuffle_preserves_card_set() -> None:
    deck = seeded_shuffle(7)
    assert len(deck) == 52
    assert set(deck) == set(CANONICAL_DECK)


def test_different_seeds_produce_different_decks() -> None:
    assert seeded_shuffle(1) != seeded_shuffle(2)


def test_deal_order_is_non_overlapping() -> None:
    deck = seeded_shuffle(99)
    hero = deal_hero_hole(deck)
    villain = deal_villain_hole(deck)
    flop = deal_flop(deck)
    turn = deal_turn(deck)
    river = deal_river(deck)
    dealt = {*hero, *villain, *flop, turn, river}
    assert len(dealt) == 9


def test_invalid_cards_rejected() -> None:
    assert not is_valid_card("10s")
    assert not is_valid_card("Xx")
    assert not is_valid_card("")
    assert is_valid_card("As")
    assert is_valid_card("Td")
