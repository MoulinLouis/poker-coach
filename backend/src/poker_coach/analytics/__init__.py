"""Cross-hand analytics used to enrich the coach prompt.

Pure-read module: no schema changes, no writes, no side effects.
Consumers request aggregates (e.g. villain stats over the last N hands)
and get dataclasses that the prompt renderer can consume directly.
"""

from poker_coach.analytics.villain_stats import VillainStats, compute_villain_stats

__all__ = ["VillainStats", "compute_villain_stats"]
