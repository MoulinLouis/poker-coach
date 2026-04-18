from __future__ import annotations

import uuid

from .deck import (
    deal_flop,
    deal_hero_hole,
    deal_river,
    deal_turn,
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
    advance to the next street, deal community cards as needed.
    """
    new_committed = {"hero": 0, "villain": 0}
    new_pot = state.pot + sum(state.committed.values())

    # Determine next street
    street_order = ["preflop", "flop", "turn", "river", "showdown"]
    idx = street_order.index(state.street)
    next_street = street_order[idx + 1] if idx + 1 < len(street_order) else "complete"

    # Deal board cards from the deck if one is attached
    new_board = list(state.board)
    if state.deck_snapshot is not None:
        if next_street == "flop" and len(new_board) == 0:
            new_board = deal_flop(state.deck_snapshot)
        elif next_street == "turn" and len(new_board) == 3:
            new_board = [*new_board, deal_turn(state.deck_snapshot)]
        elif next_street == "river" and len(new_board) == 4:
            new_board = [*new_board, deal_river(state.deck_snapshot)]

    # If either player is all-in at the end of a betting round, we skip to showdown.
    both_have_chips = state.stacks["hero"] > 0 and state.stacks["villain"] > 0
    if not both_have_chips and next_street not in ("showdown", "complete"):
        # Fast-forward: deal remaining streets then go to showdown
        if state.deck_snapshot is not None:
            if len(new_board) < 3:
                new_board = deal_flop(state.deck_snapshot)
            if len(new_board) < 4:
                new_board = [*new_board, deal_turn(state.deck_snapshot)]
            if len(new_board) < 5:
                new_board = [*new_board, deal_river(state.deck_snapshot)]
        next_street = "showdown"

    if next_street in ("showdown", "complete"):
        to_act: Seat | None = None
    else:
        # Postflop: BB (non-button) acts first.
        to_act = other_seat(state.button)

    return state.model_copy(
        update={
            "street": next_street,
            "board": new_board,
            "committed": new_committed,
            "pot": new_pot,
            "to_act": to_act,
            "last_aggressor": None,
            "last_raise_size": state.bb,
            "raises_open": True,
            "acted_this_street": frozenset(),
        }
    )


def apply_action(state: GameState, action: Action) -> GameState:
    if state.street in ("showdown", "complete"):
        raise IllegalAction(f"hand already at {state.street}")
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
