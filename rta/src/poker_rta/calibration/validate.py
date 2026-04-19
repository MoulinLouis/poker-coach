from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationRow:
    step_index: int
    description: str
    passed: bool
    mismatches: list[str]


def validate_step(
    step_index: int,
    description: str,
    expected: dict[str, Any],
    observed: dict[str, Any],
) -> ValidationRow:
    mismatches: list[str] = []
    for key, exp in expected.items():
        obs = observed.get(key)
        if obs != exp:
            mismatches.append(f"{key}: expected={exp!r} observed={obs!r}")
    return ValidationRow(
        step_index=step_index,
        description=description,
        passed=not mismatches,
        mismatches=mismatches,
    )
