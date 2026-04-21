from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Seat = Literal["hero", "villain"]
Street = Literal["preflop", "flop", "turn", "river", "showdown", "complete"]
ActionType = Literal["fold", "check", "call", "bet", "raise", "allin"]


class Action(BaseModel):
    """A single player action.

    Amounts use "raise-to / bet-to" semantics — `to_amount` is the total
    the actor's `committed` becomes after this action, not the delta.
    `None` for fold, check, and call (call amount is derived from state).
    """

    model_config = ConfigDict(frozen=True)

    actor: Seat
    type: ActionType
    to_amount: int | None = None


class LegalAction(BaseModel):
    """A legal option for the player to act.

    For `bet` and `raise`, `min_to` and `max_to` bound the legal "to" amount.
    `None` for actions without amounts (fold, check, call, allin).
    """

    model_config = ConfigDict(frozen=True)

    type: ActionType
    min_to: int | None = None
    max_to: int | None = None


class GameState(BaseModel):
    """Immutable snapshot of a hand at a point in time.

    All amounts are integer chips. `bb` is the chip value of one big blind.
    Display converts to BB by dividing by `bb`.
    """

    model_config = ConfigDict(frozen=True)

    hand_id: str
    bb: int
    ante: int = 0
    effective_stack: int
    button: Seat
    hero_hole: tuple[str, str]
    villain_hole: tuple[str, str] | None = None
    board: list[str] = Field(default_factory=list)
    street: Street = "preflop"
    stacks: dict[Seat, int]
    committed: dict[Seat, int]
    pot: int = 0
    to_act: Seat | None = None
    last_aggressor: Seat | None = None
    last_raise_size: int = 0
    raises_open: bool = True
    acted_this_street: frozenset[Seat] = Field(default_factory=frozenset)
    history: list[Action] = Field(default_factory=list)
    rng_seed: int | None = None
    deck_snapshot: list[str] | None = None
    pending_reveal: Literal["flop", "turn", "river", "runout"] | None = None
    reveals: list[list[str]] = Field(default_factory=list)


def other_seat(seat: Seat) -> Seat:
    return "villain" if seat == "hero" else "hero"
