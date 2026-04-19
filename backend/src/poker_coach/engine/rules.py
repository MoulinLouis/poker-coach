from __future__ import annotations

import uuid

from .deck import (
    deal_hero_hole,
    deal_villain_hole,
    seeded_shuffle,
)
from .models import (
    Action,
    GameState,
    LegalAction,
    Seat,
    other_seat,
)


class IllegalAction(ValueError):
    """Raised when apply_action receives an action not in legal_actions(state)."""


def start_hand(
    *,
    effective_stack: int,
    bb: int,
    button: Seat,
    hero_hole: tuple[str, str] | None = None,
    villain_hole: tuple[str, str] | None = None,
    rng_seed: int | None = None,
    deck_snapshot: list[str] | None = None,
    hand_id: str | None = None,
) -> GameState:
    if bb < 2 or bb % 2 != 0:
        raise ValueError(f"bb ({bb}) must be a positive even integer")
    if effective_stack <= bb:
        raise ValueError(f"effective_stack ({effective_stack}) must exceed bb ({bb})")

    if rng_seed is not None and deck_snapshot is None:
        deck_snapshot = seeded_shuffle(rng_seed)
    if deck_snapshot is not None:
        if hero_hole is None:
            hero_hole = deal_hero_hole(deck_snapshot)
        if villain_hole is None:
            villain_hole = deal_villain_hole(deck_snapshot)
    if hero_hole is None:
        raise ValueError("hero_hole required (supply directly or via rng_seed/deck_snapshot)")

    sb = bb // 2
    non_button = other_seat(button)
    stacks = {button: effective_stack - sb, non_button: effective_stack - bb}
    committed = {button: sb, non_button: bb}

    return GameState(
        hand_id=hand_id or uuid.uuid4().hex,
        bb=bb,
        effective_stack=effective_stack,
        button=button,
        hero_hole=hero_hole,
        villain_hole=villain_hole,
        stacks=stacks,
        committed=committed,
        pot=0,
        street="preflop",
        to_act=button,
        last_aggressor=non_button,
        last_raise_size=bb,
        acted_this_street=frozenset(),
        board=[],
        history=[],
        rng_seed=rng_seed,
        deck_snapshot=deck_snapshot,
    )


def initial_state(state: GameState) -> GameState:
    """Reconstruct the pre-action starting state from a finished or in-progress state.

    Uses the setup fields (effective_stack, bb, button, holes, deck) to replay
    start_hand. Combined with folding apply_action over state.history, this
    proves replay idempotency.
    """
    return start_hand(
        effective_stack=state.effective_stack,
        bb=state.bb,
        button=state.button,
        hero_hole=state.hero_hole,
        villain_hole=state.villain_hole,
        rng_seed=state.rng_seed,
        deck_snapshot=state.deck_snapshot,
        hand_id=state.hand_id,
    )


def legal_actions(state: GameState) -> list[LegalAction]:
    if state.pending_reveal is not None:
        return []
    if state.street in ("showdown", "complete"):
        return []
    actor = state.to_act
    if actor is None:
        return []
    opp = other_seat(actor)
    actor_committed = state.committed[actor]
    opp_committed = state.committed[opp]
    actor_stack = state.stacks[actor]
    max_to = actor_committed + actor_stack

    options: list[LegalAction] = []

    if opp_committed > actor_committed:
        # Facing a bet or raise
        options.append(LegalAction(type="fold"))
        options.append(LegalAction(type="call"))
        if actor_stack > 0 and state.raises_open:
            min_raise_to = opp_committed + state.last_raise_size
            if min_raise_to <= max_to:
                options.append(LegalAction(type="raise", min_to=min_raise_to, max_to=max_to))
            # Going all-in is available even when it's less than a full min-raise,
            # provided raises are still open.
            if max_to > opp_committed:
                options.append(LegalAction(type="allin", min_to=max_to, max_to=max_to))
    else:
        # Not facing a bet (committed amounts equal)
        options.append(LegalAction(type="check"))
        if actor_stack > 0:
            min_bet_to = actor_committed + state.bb
            if min_bet_to <= max_to:
                options.append(LegalAction(type="bet", min_to=min_bet_to, max_to=max_to))
            options.append(LegalAction(type="allin", min_to=max_to, max_to=max_to))

    return options


def _is_aggressive(action_type: str, all_in_to: int, opp_committed: int) -> bool:
    """Whether the action is "aggressive" enough to re-open action.

    Pure bet/raise always reopens. Allin reopens only if the all-in amount
    is strictly greater than the opponent's current commitment.
    """
    if action_type in ("bet", "raise"):
        return True
    if action_type == "allin":
        return all_in_to > opp_committed
    return False


def _apply_street_transition(state: GameState) -> GameState:
    """Settle the street: move committed into pot, reset per-street fields,
    advance to the next street, set pending_reveal for user card input.
    """
    new_committed = {"hero": 0, "villain": 0}
    new_pot = state.pot + sum(state.committed.values())

    idx = _STREET_ORDER.index(state.street)
    next_street = _STREET_ORDER[idx + 1] if idx + 1 < len(_STREET_ORDER) else "complete"

    both_have_chips = state.stacks["hero"] > 0 and state.stacks["villain"] > 0

    pending_reveal: str | None = None
    if next_street in ("flop", "turn", "river"):
        pending_reveal = next_street
    if not both_have_chips and next_street not in ("showdown", "complete"):
        next_street = "showdown"
        pending_reveal = "runout" if len(state.board) < 5 else None

    return state.model_copy(
        update={
            "street": next_street,
            "committed": new_committed,
            "pot": new_pot,
            "to_act": None,
            "last_aggressor": None,
            "last_raise_size": state.bb,
            "raises_open": True,
            "acted_this_street": frozenset(),
            "pending_reveal": pending_reveal,
        }
    )


_STREET_ORDER: tuple[str, ...] = ("preflop", "flop", "turn", "river", "showdown")

_PENDING_EXPECTED_LEN = {
    "flop": 3,
    "turn": 1,
    "river": 1,
}


def _expected_reveal_len(state: GameState) -> int:
    pending = state.pending_reveal
    if pending is None:
        raise IllegalAction("no pending reveal")
    if pending == "runout":
        return 5 - len(state.board)
    return _PENDING_EXPECTED_LEN[pending]


def _swap_into_board_positions(deck: list[str], cards: list[str], start: int) -> list[str]:
    """Return a deck with `cards` placed at positions [start : start+len(cards)].

    Cards already present elsewhere in the deck get swapped to the positions the
    new cards vacated. Preserves the "52 unique cards" invariant.
    """
    new_deck = list(deck)
    for i, card in enumerate(cards):
        target = start + i
        if new_deck[target] == card:
            continue
        try:
            source = new_deck.index(card)
        except ValueError as exc:
            raise IllegalAction(f"card {card} not in deck_snapshot") from exc
        new_deck[target], new_deck[source] = new_deck[source], new_deck[target]
    return new_deck


def apply_reveal(state: GameState, cards: list[str]) -> GameState:
    """Consume `pending_reveal` by committing user-supplied board cards.

    Validates length, uniqueness (no dupes with holes or existing board, no
    dupes within `cards`), rewrites `deck_snapshot` so positions [4:4+len(board)]
    match the new board in order, and clears `pending_reveal`.
    """
    if state.pending_reveal is None:
        raise IllegalAction("no pending reveal")

    expected = _expected_reveal_len(state)
    if len(cards) != expected:
        raise IllegalAction(
            f"{state.pending_reveal} reveal expects {expected} cards, got {len(cards)}"
        )

    if len(set(cards)) != len(cards):
        raise IllegalAction(f"duplicate cards in reveal: {cards}")

    excluded: set[str] = set(state.hero_hole)
    if state.villain_hole is not None:
        excluded.update(state.villain_hole)
    excluded.update(state.board)
    clash = excluded.intersection(cards)
    if clash:
        raise IllegalAction(f"reveal duplicates existing cards: {sorted(clash)}")

    new_board = [*state.board, *cards]
    new_reveals = [*state.reveals, list(cards)]

    new_deck = state.deck_snapshot
    if new_deck is not None:
        new_deck = _swap_into_board_positions(new_deck, new_board, start=4)

    if state.street in ("showdown", "complete"):
        to_act: Seat | None = None
    else:
        to_act = other_seat(state.button)

    return state.model_copy(
        update={
            "board": new_board,
            "reveals": new_reveals,
            "pending_reveal": None,
            "deck_snapshot": new_deck,
            "to_act": to_act,
        }
    )


def replay(state: GameState) -> GameState:
    """Reconstruct `state` by replaying its history and reveals from the initial setup.

    Replaces the old `reduce(apply_action, history, initial_state)` form, which
    no longer converges because apply_action halts at pending_reveal.
    """
    s = initial_state(state)
    reveal_cursor = 0
    for action in state.history:
        s = apply_action(s, action)
        while s.pending_reveal is not None:
            if reveal_cursor >= len(state.reveals):
                raise AssertionError(
                    "history has pending reveal but no matching entry in state.reveals"
                )
            s = apply_reveal(s, state.reveals[reveal_cursor])
            reveal_cursor += 1
    if reveal_cursor != len(state.reveals):
        raise AssertionError(
            f"unused reveals: consumed {reveal_cursor}, state has {len(state.reveals)}"
        )
    return s


def apply_action(state: GameState, action: Action) -> GameState:
    if state.street in ("showdown", "complete"):
        raise IllegalAction(f"hand already at {state.street}")
    if state.pending_reveal is not None:
        raise IllegalAction(f"pending reveal ({state.pending_reveal}) must be resolved first")
    if state.to_act is None or action.actor != state.to_act:
        raise IllegalAction(f"not {action.actor}'s turn (to_act={state.to_act})")

    legal = legal_actions(state)
    legal_by_type = {la.type: la for la in legal}
    if action.type not in legal_by_type:
        raise IllegalAction(f"{action.type} not in legal {set(legal_by_type)}")

    actor = action.actor
    opp = other_seat(actor)
    history = [*state.history, action]

    if action.type == "fold":
        # Opponent wins the entire pot (settled pot + both committed).
        total_pot = state.pot + sum(state.committed.values())
        new_stacks = dict(state.stacks)
        new_stacks[opp] += total_pot
        return state.model_copy(
            update={
                "street": "complete",
                "to_act": None,
                "stacks": new_stacks,
                "committed": {"hero": 0, "villain": 0},
                "pot": 0,
                "history": history,
            }
        )

    if action.type == "check":
        new_acted = state.acted_this_street | {actor}
        closed = len(new_acted) == 2 and state.committed[actor] == state.committed[opp]
        if closed:
            settled = state.model_copy(update={"history": history})
            return _apply_street_transition(settled)
        return state.model_copy(
            update={
                "to_act": opp,
                "acted_this_street": new_acted,
                "history": history,
            }
        )

    if action.type == "call":
        # Match opponent's committed up to actor's stack (handles all-in-for-less).
        to_match = min(state.committed[opp], state.committed[actor] + state.stacks[actor])
        delta = to_match - state.committed[actor]
        new_stacks = dict(state.stacks)
        new_committed = dict(state.committed)
        new_stacks[actor] -= delta
        new_committed[actor] += delta

        # Uncalled-bet return: opponent's excess above what we matched returns.
        if new_committed[opp] > new_committed[actor]:
            excess = new_committed[opp] - new_committed[actor]
            new_committed[opp] -= excess
            new_stacks[opp] += excess

        new_acted = state.acted_this_street | {actor}
        closed = len(new_acted) == 2 and new_committed[actor] == new_committed[opp]
        intermediate = state.model_copy(
            update={
                "stacks": new_stacks,
                "committed": new_committed,
                "to_act": opp,
                "acted_this_street": new_acted,
                "history": history,
            }
        )
        if closed:
            return _apply_street_transition(intermediate)
        return intermediate

    if action.type in ("bet", "raise", "allin"):
        # Derive the "to" amount
        if action.type == "allin":
            to_amount = state.committed[actor] + state.stacks[actor]
        else:
            if action.to_amount is None:
                raise IllegalAction(f"{action.type} requires to_amount")
            to_amount = action.to_amount
            la = legal_by_type[action.type]
            assert la.min_to is not None and la.max_to is not None
            if not (la.min_to <= to_amount <= la.max_to):
                raise IllegalAction(
                    f"{action.type} to {to_amount} outside [{la.min_to}, {la.max_to}]"
                )

        delta = to_amount - state.committed[actor]
        if delta > state.stacks[actor]:
            raise IllegalAction(f"{action.type} amount {delta} exceeds stack {state.stacks[actor]}")

        new_stacks = dict(state.stacks)
        new_committed = dict(state.committed)
        new_stacks[actor] -= delta
        new_committed[actor] = to_amount

        # Determine raise size (for min-raise bookkeeping)
        prior_bet = state.committed[opp]
        raise_size = to_amount - prior_bet

        # Aggressive actions that re-open action update last_raise_size.
        # All-in below a full min-raise does NOT re-open action for the prior aggressor.
        reopens = _is_aggressive(action.type, to_amount, prior_bet)
        min_raise_amount = state.last_raise_size
        short_allin = action.type == "allin" and raise_size < min_raise_amount and prior_bet > 0
        if short_allin:
            # All-in short of a full min-raise: opponent must still respond
            # (fold or call), but cannot re-raise. Opponent's "acted" state
            # is preserved; raises are closed until the next street.
            new_acted = state.acted_this_street | {actor}
            new_last_raise_size = state.last_raise_size
            new_last_aggressor = state.last_aggressor
            new_raises_open = False
        else:
            # Full raise/bet (or all-in large enough to qualify): opponent must respond.
            new_acted = frozenset({actor}) if reopens else state.acted_this_street | {actor}
            new_last_raise_size = max(raise_size, state.bb) if reopens else state.last_raise_size
            new_last_aggressor = actor if reopens else state.last_aggressor
            new_raises_open = state.raises_open

        intermediate = state.model_copy(
            update={
                "stacks": new_stacks,
                "committed": new_committed,
                "to_act": opp,
                "acted_this_street": new_acted,
                "last_aggressor": new_last_aggressor,
                "last_raise_size": new_last_raise_size,
                "raises_open": new_raises_open,
                "history": history,
            }
        )
        # If opponent has no chips to respond, the betting round is over. Any
        # excess the actor put in beyond what the opponent could possibly match
        # returns immediately (uncalled-bet rule).
        if new_stacks[opp] == 0:
            opp_max_match = new_committed[opp] + new_stacks[opp]
            if new_committed[actor] > opp_max_match:
                over = new_committed[actor] - opp_max_match
                adj_committed = dict(new_committed)
                adj_stacks = dict(new_stacks)
                adj_committed[actor] -= over
                adj_stacks[actor] += over
                intermediate = intermediate.model_copy(
                    update={"committed": adj_committed, "stacks": adj_stacks}
                )
            return _apply_street_transition(intermediate)

        return intermediate

    raise IllegalAction(f"unknown action type {action.type}")
