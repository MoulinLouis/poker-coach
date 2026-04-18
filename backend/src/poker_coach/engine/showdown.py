from typing import Literal

from phevaluator import evaluate_cards
from pydantic import BaseModel, ConfigDict

from .models import GameState


def classify(rank: int) -> str:
    """phevaluator rank → human-readable hand class.

    Lower rank = better hand. 1 is a royal flush; 7462 is a 7-high
    high-card. Thresholds are the standard Cactus-Kev rank partitions.
    """
    if rank == 1:
        return "royal flush"
    if rank <= 10:
        return "straight flush"
    if rank <= 166:
        return "four of a kind"
    if rank <= 322:
        return "full house"
    if rank <= 1599:
        return "flush"
    if rank <= 1609:
        return "straight"
    if rank <= 2467:
        return "three of a kind"
    if rank <= 3325:
        return "two pair"
    if rank <= 6185:
        return "pair"
    return "high card"


class ShowdownResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    winner: Literal["hero", "villain", "tie"]
    hero_rank: int
    villain_rank: int
    hero_label: str
    villain_label: str


def resolve_showdown(state: GameState) -> ShowdownResult:
    if state.villain_hole is None:
        raise ValueError("villain_hole required for showdown resolution")
    if len(state.board) != 5:
        raise ValueError(f"expected 5 board cards, got {len(state.board)}")

    hero_cards = [*state.hero_hole, *state.board]
    villain_cards = [*state.villain_hole, *state.board]
    hero_rank = int(evaluate_cards(*hero_cards))
    villain_rank = int(evaluate_cards(*villain_cards))

    winner: Literal["hero", "villain", "tie"]
    if hero_rank < villain_rank:
        winner = "hero"
    elif villain_rank < hero_rank:
        winner = "villain"
    else:
        winner = "tie"

    return ShowdownResult(
        winner=winner,
        hero_rank=hero_rank,
        villain_rank=villain_rank,
        hero_label=classify(hero_rank),
        villain_label=classify(villain_rank),
    )
