from random import Random

RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A")
SUITS = ("s", "h", "d", "c")
CANONICAL_DECK: tuple[str, ...] = tuple(r + s for r in RANKS for s in SUITS)


def seeded_shuffle(seed: int) -> list[str]:
    """Deterministic 52-card deck in dealing order for the given seed.

    The returned list is the `deck_snapshot` stored on GameState. Dealing
    convention (HU): deck[0:2] = hero hole, deck[2:4] = villain hole,
    deck[4:7] = flop, deck[7] = turn, deck[8] = river.
    """
    rng = Random(seed)
    deck = list(CANONICAL_DECK)
    rng.shuffle(deck)
    return deck


def deal_hero_hole(deck: list[str]) -> tuple[str, str]:
    return (deck[0], deck[1])


def deal_villain_hole(deck: list[str]) -> tuple[str, str]:
    return (deck[2], deck[3])


def deal_flop(deck: list[str]) -> list[str]:
    return list(deck[4:7])


def deal_turn(deck: list[str]) -> str:
    return deck[7]


def deal_river(deck: list[str]) -> str:
    return deck[8]


def is_valid_card(card: str) -> bool:
    return len(card) == 2 and card[0] in RANKS and card[1] in SUITS
