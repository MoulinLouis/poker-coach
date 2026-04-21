# Mixed-Strategy LLM Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `submit_advice` return a GTO-solver-style mixed strategy (list of `(action, sizing, frequency)` entries) instead of a single deterministic verdict, so the UI can show the distribution and a pro can evaluate advice the way they would a solver output.

**Architecture:** Additive — a new prompt `coach/v3.md`, an extended tool schema with `strategy` required on v3 (untouched on v2), and a new Pydantic `StrategyEntry` model. A backend validator normalizes, orders, and derives the argmax. The frontend gains a `StrategyBars` component that renders under the existing verdict; `strategy == null` (v2 decisions) hides it. Follow button stays on argmax.

**Tech Stack:** FastAPI + Pydantic v2, Anthropic Messages, OpenAI Responses, React 18 + TypeScript strict, vitest, pytest. No new runtime dependencies.

**Spec:** [`docs/superpowers/specs/2026-04-21-mixed-strategy-output-design.md`](../specs/2026-04-21-mixed-strategy-output-design.md)

---

## Conventions used by every task

- All paths relative to `/home/hyvexa/poker-coach` unless noted.
- Backend commands: `cd /home/hyvexa/poker-coach/backend && uv run pytest <path>`.
- Frontend commands: `cd /home/hyvexa/poker-coach/frontend && npm run test -- --run <path>` (single file) or `npm run test -- --run` (all), `npm run typecheck`.
- Type-check + lint at the end of every backend task: `cd backend && uv run ruff check . && uv run mypy .`.
- Commit each task as one commit once tests pass and typecheck is green.
- Executor MUST run the plan inside a dedicated worktree (create one with superpowers:using-git-worktrees first).
- Dictionary keys on frontend: add to the block they semantically belong to; keep EN/FR key order identical.

---

## Task 1: `StrategyEntry` Pydantic model + extend `Advice`

Adds the new data shape without touching any call sites. Pure additive change — all existing `Advice` round-trips still work.

**Files:**
- Modify: `backend/src/poker_coach/oracle/base.py`
- Create: `backend/tests/oracle/test_advice_round_trip.py`

---

- [ ] **Step 1.1: Write the failing round-trip test**

Write `backend/tests/oracle/test_advice_round_trip.py`:

```python
import pytest

from poker_coach.oracle.base import Advice, StrategyEntry


def test_advice_without_strategy_round_trips() -> None:
    a = Advice(
        action="raise",
        to_amount_bb=3.0,
        reasoning="Value raise on a wet board.",
        confidence="high",
    )
    payload = a.model_dump(mode="json")
    assert payload["strategy"] is None
    restored = Advice.model_validate(payload)
    assert restored == a


def test_advice_with_strategy_round_trips() -> None:
    a = Advice(
        action="bet",
        to_amount_bb=3.0,
        reasoning="Polarized c-bet.",
        confidence="medium",
        strategy=[
            StrategyEntry(action="bet", to_amount_bb=3.0, frequency=0.65),
            StrategyEntry(action="check", to_amount_bb=None, frequency=0.35),
        ],
    )
    payload = a.model_dump(mode="json")
    assert isinstance(payload["strategy"], list)
    assert len(payload["strategy"]) == 2
    restored = Advice.model_validate(payload)
    assert restored == a


def test_strategy_entry_is_frozen() -> None:
    e = StrategyEntry(action="check", to_amount_bb=None, frequency=1.0)
    with pytest.raises(Exception):
        e.action = "fold"  # type: ignore[misc]
```

- [ ] **Step 1.2: Run the test to confirm it fails**

Run: `cd backend && uv run pytest tests/oracle/test_advice_round_trip.py -v`
Expected: FAIL with `ImportError: cannot import name 'StrategyEntry' from 'poker_coach.oracle.base'`.

- [ ] **Step 1.3: Add `StrategyEntry` + extend `Advice`**

Open `backend/src/poker_coach/oracle/base.py`. After the `Confidence` type alias and before `ThinkingMode`, insert:

```python
class StrategyEntry(BaseModel):
    """One entry in a mixed strategy output.

    Multiple entries with the same `action` but different `to_amount_bb`
    are allowed (polarized sizings). `to_amount_bb` is `None` for
    fold / check / call / allin.
    """

    model_config = ConfigDict(frozen=True)

    action: ActionType
    to_amount_bb: float | None = None
    frequency: float
```

In the existing `Advice` class, add `strategy` as the last field:

```python
class Advice(BaseModel):
    """Parsed output of the submit_advice tool call."""

    model_config = ConfigDict(frozen=True)

    action: ActionType
    to_amount_bb: float | None = None
    reasoning: str
    confidence: Confidence
    strategy: list[StrategyEntry] | None = None
```

Ensure `StrategyEntry` is also re-exported via the module's public surface if there's an `__all__` (there isn't currently — check and skip if absent).

- [ ] **Step 1.4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/oracle/test_advice_round_trip.py -v`
Expected: 3 tests pass.

- [ ] **Step 1.5: Ruff + mypy**

Run: `cd backend && uv run ruff check . && uv run mypy .`
Expected: both clean.

- [ ] **Step 1.6: Commit**

```bash
git add backend/src/poker_coach/oracle/base.py backend/tests/oracle/test_advice_round_trip.py
git commit -m "feat(oracle): add StrategyEntry and optional Advice.strategy"
```

---

## Task 2: `normalize_strategy` validator

Pure function that turns a raw list of dicts (whatever the LLM produced) into a validated, sorted `list[StrategyEntry]` — or raises `ValueError` so the caller can emit `OracleError(kind="invalid_schema")`.

**Files:**
- Create: `backend/src/poker_coach/oracle/strategy_validator.py`
- Create: `backend/tests/oracle/test_strategy_validator.py`

---

- [ ] **Step 2.1: Write the failing validator tests**

Write `backend/tests/oracle/test_strategy_validator.py`:

```python
import pytest

from poker_coach.engine.models import LegalAction
from poker_coach.oracle.strategy_validator import normalize_strategy


def _la(type_: str, min_to_bb: float | None = None, max_to_bb: float | None = None) -> LegalAction:
    # Engine LegalAction uses integer chips for min_to/max_to, but the
    # validator works in BB (already converted upstream). Build a shim
    # that exposes the same fields the validator reads.
    return LegalAction(
        type=type_,  # type: ignore[arg-type]
        min_to=int(min_to_bb * 100) if min_to_bb is not None else None,
        max_to=int(max_to_bb * 100) if max_to_bb is not None else None,
    )


def test_valid_mix_sums_to_one() -> None:
    out = normalize_strategy(
        [
            {"action": "check", "to_amount_bb": None, "frequency": 0.35},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.65},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 2
    # Sorted desc by frequency
    assert out[0].action == "bet"
    assert out[0].frequency == pytest.approx(0.65)
    assert out[1].action == "check"


def test_normalizes_within_tolerance_band() -> None:
    # Sum = 0.99 → normalized to exactly 1.0
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.30},
            {"action": "call", "to_amount_bb": None, "frequency": 0.69},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    total = sum(e.frequency for e in out)
    assert total == pytest.approx(1.0, abs=1e-9)


def test_rejects_sum_below_tolerance() -> None:
    with pytest.raises(ValueError, match="frequencies sum"):
        normalize_strategy(
            [
                {"action": "fold", "to_amount_bb": None, "frequency": 0.50},
                {"action": "call", "to_amount_bb": None, "frequency": 0.47},
            ],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_sum_above_tolerance() -> None:
    with pytest.raises(ValueError, match="frequencies sum"):
        normalize_strategy(
            [
                {"action": "fold", "to_amount_bb": None, "frequency": 0.60},
                {"action": "call", "to_amount_bb": None, "frequency": 0.45},
            ],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_illegal_action() -> None:
    with pytest.raises(ValueError, match="not legal"):
        normalize_strategy(
            [{"action": "raise", "to_amount_bb": 6.0, "frequency": 1.0}],
            legal_actions=[_la("fold"), _la("call")],
            bb_chips=100,
        )


def test_rejects_sizing_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        normalize_strategy(
            [{"action": "bet", "to_amount_bb": 200.0, "frequency": 1.0}],
            legal_actions=[_la("bet", 1.0, 100.0)],
            bb_chips=100,
        )


def test_rejects_missing_sizing_on_bet() -> None:
    with pytest.raises(ValueError, match="sizing required"):
        normalize_strategy(
            [{"action": "bet", "to_amount_bb": None, "frequency": 1.0}],
            legal_actions=[_la("bet", 1.0, 100.0)],
            bb_chips=100,
        )


def test_rejects_sizing_on_non_sizing_action() -> None:
    with pytest.raises(ValueError, match="must be null"):
        normalize_strategy(
            [{"action": "check", "to_amount_bb": 3.0, "frequency": 1.0}],
            legal_actions=[_la("check")],
            bb_chips=100,
        )


def test_merges_duplicate_action_sizing() -> None:
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.40},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.25},
            {"action": "check", "to_amount_bb": None, "frequency": 0.35},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 2
    bet_entry = next(e for e in out if e.action == "bet")
    assert bet_entry.frequency == pytest.approx(0.65)


def test_drops_zero_frequency_entries() -> None:
    out = normalize_strategy(
        [
            {"action": "fold", "to_amount_bb": None, "frequency": 0.0},
            {"action": "call", "to_amount_bb": None, "frequency": 1.0},
        ],
        legal_actions=[_la("fold"), _la("call")],
        bb_chips=100,
    )
    assert [e.action for e in out] == ["call"]


def test_rejects_empty_after_drop() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_strategy(
            [{"action": "fold", "to_amount_bb": None, "frequency": 0.0}],
            legal_actions=[_la("fold")],
            bb_chips=100,
        )


def test_polarized_sizing_preserved() -> None:
    out = normalize_strategy(
        [
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.40},
            {"action": "bet", "to_amount_bb": 7.0, "frequency": 0.20},
            {"action": "check", "to_amount_bb": None, "frequency": 0.40},
        ],
        legal_actions=[_la("check"), _la("bet", 1.0, 100.0)],
        bb_chips=100,
    )
    assert len(out) == 3
    sizings = sorted(e.to_amount_bb for e in out if e.to_amount_bb is not None)
    assert sizings == [3.0, 7.0]
```

- [ ] **Step 2.2: Run the tests to confirm they fail**

Run: `cd backend && uv run pytest tests/oracle/test_strategy_validator.py -v`
Expected: all fail with `ModuleNotFoundError: No module named 'poker_coach.oracle.strategy_validator'`.

- [ ] **Step 2.3: Implement the validator**

Create `backend/src/poker_coach/oracle/strategy_validator.py`:

```python
"""Validate and normalize a raw mixed-strategy list from an LLM tool call.

The LLM returns `strategy` as a list of dicts. This module:

- enforces that every action is in the spot's legal_actions;
- enforces sizing presence/absence and range for bet/raise;
- merges duplicate (action, to_amount_bb) entries by summing their frequencies;
- drops entries with frequency == 0;
- normalizes frequency sums within a 0.98..1.02 tolerance band to exactly 1.0;
- rejects sums outside that band, or an empty result after cleanup.

The output is sorted descending by frequency so the argmax is always first.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from poker_coach.engine.models import LegalAction
from poker_coach.oracle.base import StrategyEntry

_SIZING_ACTIONS = {"bet", "raise"}
_NON_SIZING_ACTIONS = {"fold", "check", "call", "allin"}
_TOLERANCE_LOW = 0.98
_TOLERANCE_HIGH = 1.02


def normalize_strategy(
    raw: list[dict[str, Any]],
    legal_actions: list[LegalAction],
    bb_chips: int,
) -> list[StrategyEntry]:
    """Validate and normalize raw strategy entries from an LLM tool call.

    `legal_actions` uses integer chips for min_to/max_to; `bb_chips` is the
    number of chips per big blind so we can compare the LLM's BB-denominated
    sizing to the legal range.
    """
    by_legal_type = {la.type: la for la in legal_actions}

    # Validate each entry before merging or dropping.
    validated: list[tuple[str, float | None, float]] = []
    for i, entry in enumerate(raw):
        try:
            action = entry["action"]
            to_amount_bb = entry["to_amount_bb"]
            frequency = float(entry["frequency"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"strategy entry {i} malformed: {exc}") from exc

        if action not in by_legal_type:
            raise ValueError(f"action {action!r} not legal in this spot")

        la = by_legal_type[action]

        if action in _SIZING_ACTIONS:
            if to_amount_bb is None:
                raise ValueError(f"sizing required for action {action!r}")
            to_chips = int(round(to_amount_bb * bb_chips))
            if la.min_to is not None and to_chips < la.min_to:
                raise ValueError(
                    f"sizing {to_amount_bb}bb out of range for {action!r}"
                )
            if la.max_to is not None and to_chips > la.max_to:
                raise ValueError(
                    f"sizing {to_amount_bb}bb out of range for {action!r}"
                )
        elif action in _NON_SIZING_ACTIONS:
            if to_amount_bb is not None:
                raise ValueError(
                    f"to_amount_bb must be null for action {action!r}"
                )
        else:
            raise ValueError(f"unknown action {action!r}")

        if frequency < 0:
            raise ValueError(f"negative frequency in entry {i}")

        validated.append((action, to_amount_bb, frequency))

    # Merge duplicates: key by (action, to_amount_bb).
    merged: dict[tuple[str, float | None], float] = defaultdict(float)
    for action, to_amount_bb, frequency in validated:
        merged[(action, to_amount_bb)] += frequency

    # Drop zero-frequency entries.
    merged = {k: v for k, v in merged.items() if v > 0}
    if not merged:
        raise ValueError("strategy is empty after dropping zero-frequency entries")

    total = sum(merged.values())
    if total < _TOLERANCE_LOW or total > _TOLERANCE_HIGH:
        raise ValueError(
            f"frequencies sum to {total:.4f}, outside tolerance "
            f"[{_TOLERANCE_LOW}, {_TOLERANCE_HIGH}]"
        )

    # Normalize to exactly 1.0.
    scale = 1.0 / total
    entries = [
        StrategyEntry(
            action=action,  # type: ignore[arg-type]
            to_amount_bb=to_amount_bb,
            frequency=freq * scale,
        )
        for (action, to_amount_bb), freq in merged.items()
    ]

    # Sort descending by frequency (argmax first); stable tie-break on action name.
    entries.sort(key=lambda e: (-e.frequency, e.action))
    return entries


__all__ = ["normalize_strategy"]
```

- [ ] **Step 2.4: Run the tests to confirm they pass**

Run: `cd backend && uv run pytest tests/oracle/test_strategy_validator.py -v`
Expected: 12 tests pass.

- [ ] **Step 2.5: Ruff + mypy**

Run: `cd backend && uv run ruff check . && uv run mypy .`
Expected: clean.

- [ ] **Step 2.6: Commit**

```bash
git add backend/src/poker_coach/oracle/strategy_validator.py backend/tests/oracle/test_strategy_validator.py
git commit -m "feat(oracle): add normalize_strategy validator"
```

---

## Task 3: Versioned tool schema

Make `anthropic_tool_spec` and `openai_tool_spec` accept `prompt_version: str`. v1/v2 keep today's schema byte-for-byte; v3 adds the `strategy` array and makes `action`/`to_amount_bb` optional-nullable.

**Files:**
- Modify: `backend/src/poker_coach/oracle/tool_schema.py`
- Modify: `backend/tests/oracle/test_tool_schema.py`

---

- [ ] **Step 3.1: Write failing v3 tests and adjust existing tests**

Replace the entire content of `backend/tests/oracle/test_tool_schema.py`:

```python
from poker_coach.oracle.tool_schema import (
    anthropic_tool_spec,
    openai_tool_spec,
)


# ---------- v2 (legacy) shape ----------


def test_anthropic_v2_structure() -> None:
    spec = anthropic_tool_spec("v2")
    assert spec["name"] == "submit_advice"
    schema = spec["input_schema"]
    props = schema["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert props["action"]["enum"] == ["fold", "check", "call", "bet", "raise", "allin"]
    assert props["confidence"]["enum"] == ["low", "medium", "high"]
    assert schema["required"] == ["action", "reasoning", "confidence"]
    assert "additionalProperties" not in schema


def test_openai_v2_structure() -> None:
    spec = openai_tool_spec("v2")
    assert spec["strict"] is True
    params = spec["parameters"]
    assert params["additionalProperties"] is False
    assert set(params["required"]) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert params["properties"]["to_amount_bb"]["type"] == ["number", "null"]


def test_v1_emits_same_shape_as_v2() -> None:
    assert anthropic_tool_spec("v1") == anthropic_tool_spec("v2")
    assert openai_tool_spec("v1") == openai_tool_spec("v2")


# ---------- v3 (mixed strategy) shape ----------


def test_anthropic_v3_adds_strategy_and_relaxes_required() -> None:
    spec = anthropic_tool_spec("v3")
    schema = spec["input_schema"]
    props = schema["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence", "strategy"}
    # In v3, action/to_amount_bb are derived server-side — no longer required.
    assert set(schema["required"]) == {"strategy", "reasoning", "confidence"}
    strat = props["strategy"]
    assert strat["type"] == "array"
    item = strat["items"]
    assert item["type"] == "object"
    item_props = item["properties"]
    assert set(item_props) == {"action", "to_amount_bb", "frequency"}
    assert item_props["action"]["enum"] == ["fold", "check", "call", "bet", "raise", "allin"]
    assert item_props["frequency"]["type"] == "number"
    assert set(item["required"]) == {"action", "to_amount_bb", "frequency"}


def test_openai_v3_strict_adds_strategy() -> None:
    spec = openai_tool_spec("v3")
    params = spec["parameters"]
    assert params["additionalProperties"] is False
    props = params["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence", "strategy"}
    # OpenAI strict mode: every property in required, optionals are nullable.
    assert set(params["required"]) == {"action", "to_amount_bb", "reasoning", "confidence", "strategy"}
    assert props["action"]["type"] == ["string", "null"]
    assert props["to_amount_bb"]["type"] == ["number", "null"]

    strat = props["strategy"]
    assert strat["type"] == "array"
    item = strat["items"]
    assert item["additionalProperties"] is False
    item_props = item["properties"]
    assert set(item_props) == {"action", "to_amount_bb", "frequency"}
    assert item_props["to_amount_bb"]["type"] == ["number", "null"]
    assert set(item["required"]) == {"action", "to_amount_bb", "frequency"}


def test_v3_specs_share_strategy_shape() -> None:
    a_items = anthropic_tool_spec("v3")["input_schema"]["properties"]["strategy"]["items"]["properties"]
    o_items = openai_tool_spec("v3")["parameters"]["properties"]["strategy"]["items"]["properties"]
    assert set(a_items) == set(o_items) == {"action", "to_amount_bb", "frequency"}
    assert a_items["action"]["enum"] == o_items["action"]["enum"]
```

- [ ] **Step 3.2: Run tests to confirm failures**

Run: `cd backend && uv run pytest tests/oracle/test_tool_schema.py -v`
Expected: all fail — either on signature (positional arg required) or on v3 branch missing.

- [ ] **Step 3.3: Implement versioned tool schema**

Replace the entire content of `backend/src/poker_coach/oracle/tool_schema.py`:

```python
"""Shared submit_advice tool schema and provider-specific normalizers.

The same logical schema is emitted as two dialect variants:

- Anthropic Messages: permissive JSON Schema via `input_schema`.
- OpenAI Responses: strict mode (`additionalProperties: false`,
  all properties in `required`, nullable-typed optionals).

Two prompt-version shapes:

- v1 / v2: single deterministic verdict (action + optional to_amount_bb +
  reasoning + confidence).
- v3: adds `strategy` — a GTO-solver-style list of (action, to_amount_bb,
  frequency). `action` and `to_amount_bb` become server-derived (argmax of
  strategy) and are therefore no longer required on Anthropic; on OpenAI
  strict they stay in `required` but become nullable.

Hand-written rather than auto-derived so we own the exact wire shape.
Fixture snapshot tests catch drift between the two providers and between
versions.
"""

from __future__ import annotations

from typing import Any

TOOL_NAME = "submit_advice"

_TOOL_DESCRIPTION_V2 = (
    "Submit the final recommendation for the hero's action. Call this exactly once "
    "when you have a conclusion. action must be one of the legal types the prompt "
    "listed; to_amount_bb is required for bet and raise, omitted otherwise; "
    "reasoning is plain prose, exactly 2 sentences, 40-60 words total, no headers "
    "or markdown (sentence 1 = action + key reason; sentence 2 = next-street plan "
    "or tie-break exploit); confidence reflects mix closeness (high = dominant, "
    "medium = close, low = borderline)."
)

_TOOL_DESCRIPTION_V3 = (
    "Submit the hero's mixed strategy. Call this exactly once when you have a "
    "conclusion. `strategy` is the full GTO-style distribution: one entry per "
    "(action, sizing) you actually play at >= 5% frequency; frequencies sum to 1; "
    "rounded to 0.05 steps. For bet/raise you may include up to two sizings "
    "(polarized). `action` and `to_amount_bb` are derived server-side from the "
    "strategy argmax — you may leave them null. `reasoning` is 2 sentences, "
    "40-60 words; `confidence` reflects how close the top action is to its "
    "alternatives (high = dominant, medium = close, low = borderline)."
)

_ACTION_ENUM = ["fold", "check", "call", "bet", "raise", "allin"]
_CONFIDENCE_ENUM = ["low", "medium", "high"]


def anthropic_tool_spec(prompt_version: str) -> dict[str, Any]:
    if prompt_version == "v3":
        return _anthropic_v3()
    return _anthropic_v2()


def openai_tool_spec(prompt_version: str) -> dict[str, Any]:
    if prompt_version == "v3":
        return _openai_v3()
    return _openai_v2()


# ---------- v2 (legacy) ----------


def _anthropic_v2() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V2,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": _ACTION_ENUM},
                "to_amount_bb": {
                    "type": "number",
                    "description": "Sizing in BB; required for bet and raise.",
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
            },
            "required": ["action", "reasoning", "confidence"],
        },
    }


def _openai_v2() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V2,
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": "string", "enum": _ACTION_ENUM},
                "to_amount_bb": {
                    "type": ["number", "null"],
                    "description": "Sizing in BB; null unless action is bet or raise.",
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
            },
            "required": ["action", "to_amount_bb", "reasoning", "confidence"],
        },
    }


# ---------- v3 (mixed strategy) ----------


def _strategy_item_anthropic() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": _ACTION_ENUM},
            "to_amount_bb": {
                "type": ["number", "null"],
                "description": "Sizing in BB for bet/raise; null otherwise.",
            },
            "frequency": {"type": "number"},
        },
        "required": ["action", "to_amount_bb", "frequency"],
    }


def _strategy_item_openai() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": _ACTION_ENUM},
            "to_amount_bb": {
                "type": ["number", "null"],
                "description": "Sizing in BB for bet/raise; null otherwise.",
            },
            "frequency": {"type": "number"},
        },
        "required": ["action", "to_amount_bb", "frequency"],
    }


def _anthropic_v3() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V3,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": ["string", "null"],
                    "enum": [*_ACTION_ENUM, None],
                },
                "to_amount_bb": {"type": ["number", "null"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
                "strategy": {
                    "type": "array",
                    "items": _strategy_item_anthropic(),
                    "minItems": 1,
                },
            },
            "required": ["strategy", "reasoning", "confidence"],
        },
    }


def _openai_v3() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V3,
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": ["string", "null"], "enum": [*_ACTION_ENUM, None]},
                "to_amount_bb": {"type": ["number", "null"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
                "strategy": {
                    "type": "array",
                    "items": _strategy_item_openai(),
                },
            },
            "required": ["action", "to_amount_bb", "reasoning", "confidence", "strategy"],
        },
    }
```

Note: the Anthropic `enum` for v3 `action` accepts `null` by listing it explicitly. The OpenAI strict dialect uses the `type: ["string", "null"]` pattern.

- [ ] **Step 3.4: Run tests to confirm pass**

Run: `cd backend && uv run pytest tests/oracle/test_tool_schema.py -v`
Expected: 6 tests pass.

- [ ] **Step 3.5: Run full backend suite to catch any broken callers**

Run: `cd backend && uv run pytest -x`
Expected: fails in `test_anthropic_oracle.py` / `test_openai_oracle.py` because callers still invoke `anthropic_tool_spec()` / `openai_tool_spec()` with no arg. Task 4 fixes that — **do not fix now**, only confirm the expected failures list.

Note: if the full suite pass (i.e., callers already handled in another test setup), skip the note; the next task is the real fix.

- [ ] **Step 3.6: Commit**

```bash
git add backend/src/poker_coach/oracle/tool_schema.py backend/tests/oracle/test_tool_schema.py
git commit -m "feat(oracle): version tool schema; add v3 with strategy field"
```

---

## Task 4: Thread `prompt_version` through oracle dispatch + apply `normalize_strategy`

Both oracle implementations read `rendered.version` to parameterize the tool schema, and on v3, parse + validate `strategy`, then derive `action` / `to_amount_bb` from the argmax.

**Files:**
- Modify: `backend/src/poker_coach/oracle/anthropic_oracle.py`
- Modify: `backend/src/poker_coach/oracle/openai_oracle.py`
- Modify: `backend/tests/oracle/test_anthropic_oracle.py`
- Modify: `backend/tests/oracle/test_openai_oracle.py`

---

- [ ] **Step 4.1: Read current oracle tests to understand fixture shape**

Open `backend/tests/oracle/fixtures.py` (likely) and `backend/tests/oracle/test_anthropic_oracle.py` — note how the fake stream caller builds messages. The v3 path needs a new fixture that embeds `strategy` in the tool_use input.

- [ ] **Step 4.2: Extract bb_chips from rendered prompt (helper)**

The validator needs `bb_chips`. It's not currently on `RenderedPrompt`. The coach v2/v3 prompt's legal_actions section uses BB amounts, but the engine's `LegalAction.min_to`/`max_to` are integer chips. We need the `bb` value of the spot.

Two options:
1. Pass `bb_chips` as an extra field on `RenderedPrompt.variables` (the coach pack already has `effective_bb` etc., but not a raw `bb` chip count).
2. Pass `bb_chips` through a new parameter on `advise_stream`.

Going with (1) — `state_to_coach_variables` already has access to the full `GameState` and can record `bb` explicitly as a variable named `bb_chips` (a raw integer, used by the backend only — it is NOT consumed by Jinja, so not leaked to the prompt).

Open `backend/src/poker_coach/prompts/context.py`. In `state_to_coach_variables`, add:

```python
variables["bb_chips"] = state.bb
```

Verify the coach/v2.md and (future) v3.md prompts don't reference `bb_chips` (they don't — the variable list in frontmatter enforces this). The `StrictUndefined` Jinja2 config will not fail on unused declared variables, but adding `bb_chips` to the declared `variables:` list in the YAML frontmatter WOULD break `test_no_villain_leak.py` if not matched in template. Instead, do NOT add `bb_chips` to the template frontmatter — it's a backend-only sidecar. `state_to_coach_variables` returns a dict that includes more keys than the template declares; the renderer only passes what the template asks for.

Confirm this by reading `backend/src/poker_coach/prompts/renderer.py` and noticing how it filters — if it doesn't filter, adding an undeclared variable to the context dict is harmless (Jinja just ignores unreferenced keys).

If the renderer DOES filter to declared variables (strict allowlist), instead use approach (2): thread `bb_chips` through `advise_stream`. For the scope of this task, assume approach (1) works.

(Executor: if you hit a blocker here because the renderer filters, stop and report — we'll switch to approach (2) with a parameter.)

- [ ] **Step 4.3: Write failing tests for the v3 oracle path**

Before writing the new tests, **read** `backend/tests/oracle/test_anthropic_oracle.py` end-to-end to understand its fixture conventions (fake stream caller, how `tool_use` blocks are constructed, how `RenderedPrompt` is built). Mirror that style for the new tests.

Append to `backend/tests/oracle/test_anthropic_oracle.py`:

```python
# Add to existing imports
from poker_coach.oracle.base import StrategyEntry, ToolCallComplete
from poker_coach.engine.models import LegalAction


async def test_v3_parses_strategy_and_derives_argmax() -> None:
    """On prompt_version='v3', the oracle reads `strategy` from the tool_use,
    validates + normalizes it, sorts by frequency, and derives the top-level
    `action` and `to_amount_bb` from the argmax entry."""
    tool_input = {
        "action": None,
        "to_amount_bb": None,
        "reasoning": "Polarized c-bet.",
        "confidence": "medium",
        "strategy": [
            {"action": "check", "to_amount_bb": None, "frequency": 0.35},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.65},
        ],
    }
    legal_actions = [
        LegalAction(type="check"),
        LegalAction(type="bet", min_to=100, max_to=9700),
    ]
    # Build RenderedPrompt with variables including bb_chips + legal_actions.
    # Follow the fixture style in this file for the exact constructor args.
    rendered = _make_rendered_prompt(
        pack="coach",
        version="v3",
        variables={
            "bb_chips": 100,
            "legal_actions": [la.model_dump() for la in legal_actions],
        },
    )
    oracle = _make_oracle_with_tool_input(tool_input)  # file-local helper pattern
    spec = _default_spec()  # file-local helper pattern

    events = [e async for e in oracle.advise_stream(rendered, spec)]
    tool_events = [e for e in events if isinstance(e, ToolCallComplete)]
    assert len(tool_events) == 1

    advice = tool_events[0].advice
    assert advice.strategy is not None
    assert len(advice.strategy) == 2
    # Sorted desc by frequency: argmax first.
    assert advice.strategy[0].action == "bet"
    assert advice.strategy[0].frequency == pytest.approx(0.65)
    # Server-derived top-level fields match argmax.
    assert advice.action == "bet"
    assert advice.to_amount_bb == 3.0


async def test_v3_rejects_invalid_strategy() -> None:
    """A strategy whose frequencies sum outside [0.98, 1.02] is rejected
    as invalid_schema; no ToolCallComplete is emitted."""
    tool_input = {
        "action": None,
        "to_amount_bb": None,
        "reasoning": "Invalid.",
        "confidence": "low",
        "strategy": [
            {"action": "check", "to_amount_bb": None, "frequency": 0.3},
            {"action": "bet", "to_amount_bb": 3.0, "frequency": 0.3},
        ],  # sum = 0.6 -> outside tolerance
    }
    legal_actions = [
        LegalAction(type="check"),
        LegalAction(type="bet", min_to=100, max_to=9700),
    ]
    rendered = _make_rendered_prompt(
        pack="coach",
        version="v3",
        variables={
            "bb_chips": 100,
            "legal_actions": [la.model_dump() for la in legal_actions],
        },
    )
    oracle = _make_oracle_with_tool_input(tool_input)
    spec = _default_spec()

    events = [e async for e in oracle.advise_stream(rendered, spec)]
    assert not any(isinstance(e, ToolCallComplete) for e in events)
    errors = [e for e in events if getattr(e, "kind", None) == "invalid_schema"]
    assert len(errors) == 1
```

The helpers `_make_rendered_prompt`, `_make_oracle_with_tool_input`, `_default_spec` correspond to whatever the file currently uses (helper functions or pytest fixtures). Match names to what already exists — DO NOT invent new names if existing ones are suitable.

Add symmetric tests in `backend/tests/oracle/test_openai_oracle.py` using that file's fixture conventions (the tool_use block shape differs between providers — OpenAI's `function_call.arguments` is a JSON string rather than a dict).

- [ ] **Step 4.4: Run to confirm failures**

Run: `cd backend && uv run pytest tests/oracle/test_anthropic_oracle.py tests/oracle/test_openai_oracle.py -v`
Expected: new v3 tests fail; existing v2 tests may also fail because `anthropic_tool_spec()` / `openai_tool_spec()` now require a `prompt_version` argument.

- [ ] **Step 4.5: Update oracle implementations**

In `backend/src/poker_coach/oracle/anthropic_oracle.py`:

Update the import:
```python
from poker_coach.oracle.tool_schema import anthropic_tool_spec
from poker_coach.oracle.strategy_validator import normalize_strategy
from poker_coach.engine.models import LegalAction
```

Inside `advise_stream`, change the tool spec call:
```python
"tools": [anthropic_tool_spec(rendered.version)],
```

After `raw_input = _coerce_tool_input(tool_use_block)` and before `Advice.model_validate(raw_input)`, handle the v3 path:

```python
if rendered.version == "v3":
    try:
        legal_actions = [
            LegalAction.model_validate(la) if isinstance(la, dict) else la
            for la in rendered.variables.get("legal_actions", [])
        ]
        bb_chips = int(rendered.variables["bb_chips"])
        strategy = normalize_strategy(
            raw_input.get("strategy", []),
            legal_actions=legal_actions,
            bb_chips=bb_chips,
        )
    except (ValueError, KeyError, TypeError) as exc:
        yield OracleError(
            kind="invalid_schema",
            message=f"strategy validation failed: {exc}",
            raw_tool_input=raw_input,
        )
        return

    # Derive top-level fields from argmax (first entry after sort desc).
    argmax = strategy[0]
    raw_input = {
        **raw_input,
        "strategy": [e.model_dump(mode="json") for e in strategy],
        "action": argmax.action,
        "to_amount_bb": argmax.to_amount_bb,
    }
```

Then continue with `Advice.model_validate(raw_input)` as before.

Apply the identical change to `backend/src/poker_coach/oracle/openai_oracle.py` (the tool spec call changes to `openai_tool_spec(rendered.version)` and the validation block goes after `raw_input = ...` and before `Advice.model_validate(...)`).

- [ ] **Step 4.6: Update any existing oracle tests that constructed tool specs**

Any test that was calling `anthropic_tool_spec()` / `openai_tool_spec()` with no args needs updating — either pass `"v2"` explicitly or rely on the production path that now knows which version to use. Grep for `tool_spec(` in the backend and fix stragglers.

- [ ] **Step 4.7: Run the full backend suite**

Run: `cd backend && uv run pytest -v`
Expected: all tests pass, including the new v3 tests.

- [ ] **Step 4.8: Ruff + mypy**

Run: `cd backend && uv run ruff check . && uv run mypy .`
Expected: clean.

- [ ] **Step 4.9: Commit**

```bash
git add backend/src/poker_coach/ backend/tests/
git commit -m "feat(oracle): wire prompt_version and normalize strategy on v3"
```

---

## Task 5: Prompt `coach/v3.md`

Clone of v2 with a new closing instruction that asks for the mixed strategy.

**Files:**
- Create: `prompts/coach/v3.md`
- Create: `backend/tests/prompts/test_coach_v3_render.py`

---

- [ ] **Step 5.1: Write the failing render test**

Create `backend/tests/prompts/test_coach_v3_render.py`:

```python
from pathlib import Path

from poker_coach.prompts.renderer import PromptRenderer


def test_coach_v3_renders_with_v2_variables(tmp_path: Path) -> None:
    """v3 uses the same variable set as v2 — no new context fields required."""
    prompts_root = Path(__file__).resolve().parents[3] / "prompts"
    renderer = PromptRenderer(prompts_root)

    variables = {
        "street": "flop",
        "hero_hole": ["Ah", "Kh"],
        "board": ["2c", "7d", "Th"],
        "button": "hero",
        "pot_bb": 6.0,
        "effective_bb": 100.0,
        "hero_stack_bb": 97.0,
        "villain_stack_bb": 97.0,
        "hero_committed_bb": 0.0,
        "villain_committed_bb": 0.0,
        "stack_depth_bucket": "deep",
        "spr_bb": 16.0,
        "history": [],
        "legal_actions": [
            {"type": "check", "min_to": None, "max_to": None},
            {"type": "bet", "min_to": 100, "max_to": 9700},
        ],
        "villain_profile": "unknown",
        "villain_stats": {"hands_played": 0},
    }
    rendered = renderer.render("coach", "v3", variables)
    assert rendered.version == "v3"
    # v3-specific content: mention of the strategy field.
    assert "strategy" in rendered.rendered_prompt.lower()
    # No leak of hero_hole is expected — same contract as v2.
    assert "Ah Kh" in rendered.rendered_prompt  # hero_hole IS permitted in coach prompt
```

- [ ] **Step 5.2: Run to confirm failure**

Run: `cd backend && uv run pytest tests/prompts/test_coach_v3_render.py -v`
Expected: fail — `coach/v3.md` does not exist.

- [ ] **Step 5.3: Create `prompts/coach/v3.md`**

Write `prompts/coach/v3.md` — identical to `v2.md` up to the end of the "## Legal actions" block, then replace the trailing line:

```md
---
name: coach
version: v3
description: HU coach prompt v3 — mixed-strategy output (GTO-style frequencies).
variables:
  - street
  - hero_hole
  - board
  - button
  - pot_bb
  - effective_bb
  - hero_stack_bb
  - villain_stack_bb
  - hero_committed_bb
  - villain_committed_bb
  - stack_depth_bucket
  - spr_bb
  - history
  - legal_actions
  - villain_profile
  - villain_stats
---
## Spot
- Street: {{ street }}
- Hero's hole cards: {{ hero_hole | join(' ') }}
- Board: {% if board %}{{ board | join(' ') }}{% else %}(none){% endif %}
- Button (small blind): {{ button }}
- Pot (settled prior streets): {{ pot_bb }} bb
- Effective stack (starting): {{ effective_bb }} bb
- Hero stack behind: {{ hero_stack_bb }} bb
- Villain stack behind: {{ villain_stack_bb }} bb
- Hero committed this street: {{ hero_committed_bb }} bb
- Villain committed this street: {{ villain_committed_bb }} bb
- Stack depth: {{ stack_depth_bucket }} (SPR {{ spr_bb }})

## Villain profile
{{ villain_profile }}
{% if villain_stats.hands_played >= 10 %}
## Villain observed stats (last {{ villain_stats.hands_played }} hands)
- VPIP/PFR: {{ villain_stats.vpip_pct }}/{{ villain_stats.pfr_pct }}
- 3-bet: {{ villain_stats.threebet_pct }}
- AF: {{ villain_stats.agg_factor }}
- C-bet / fold-to-cbet: {{ villain_stats.cbet_pct }} / {{ villain_stats.fold_to_cbet_pct }}
- WTSD: {{ villain_stats.wtsd_pct }}
{% endif %}

## Action history (this hand)
{% if history -%}
{% for action in history -%}
- {{ action.actor }}: {{ action.type }}{% if action.to_amount_bb is not none %} to {{ action.to_amount_bb }} bb{% endif %}
{% endfor -%}
{% else -%}
(no voluntary actions yet — blinds only)
{% endif %}

## Legal actions for hero right now
{% for la in legal_actions -%}
- `{{ la.type }}`{% if la.min_to_bb is not none %} (to amount in [{{ la.min_to_bb }}, {{ la.max_to_bb }}] bb){% endif %}
{% endfor %}

## Output format
Call `submit_advice` now. In the `strategy` field, output the full mixed strategy
as a GTO solver would — one entry per (action, sizing) you actually play, each
with a frequency in [0, 1]. Frequencies across all entries must sum to 1.

Guidelines:
- List only actions you play at least 5% of the time; omit the rest (implicit 0%).
- For bet/raise, you may include up to two sizings (a small and a large) when the
  spot is polarized; one sizing otherwise.
- Frequencies are rounded to 0.05 increments (e.g. 0.35, 0.60, 0.05).
- The primary `action` and `to_amount_bb` fields are derived by the server from
  your strategy — you do not need to fill them.
- `reasoning` is 2 sentences, 40-60 words, explaining why the mix is what it is
  (what drives the split between the top action and the alternatives).
```

- [ ] **Step 5.4: Run the test to confirm it passes**

Run: `cd backend && uv run pytest tests/prompts/test_coach_v3_render.py -v`
Expected: pass.

- [ ] **Step 5.5: Run the full prompt test suite** (ensures leak test still passes)

Run: `cd backend && uv run pytest tests/prompts/ -v`
Expected: all tests pass, including `test_no_villain_leak.py`.

- [ ] **Step 5.6: Commit**

```bash
git add prompts/coach/v3.md backend/tests/prompts/test_coach_v3_render.py
git commit -m "feat(prompts): add coach/v3 with mixed-strategy output instruction"
```

---

## Task 6: Frontend types — `StrategyEntry` + extended `Advice`

Pure type addition. No UI yet.

**Files:**
- Modify: `frontend/src/api/types.ts`

---

- [ ] **Step 6.1: Extend the types**

Open `frontend/src/api/types.ts` and find the `Advice` interface (or type alias). Next to it, add:

```ts
export interface StrategyEntry {
  action: ActionType;
  to_amount_bb: number | null;
  frequency: number;
}
```

Then extend `Advice` with the field marked **optional AND nullable** so existing consumers that don't set it compile without change:

```ts
  strategy?: StrategyEntry[] | null;
```

If `Advice` already uses `type ... = { ... }` syntax instead of `interface`, add the field at the end of the object type.

- [ ] **Step 6.2: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: clean. Because `strategy` is `?:` optional, any test fixture or ad-hoc `Advice` object constructed in existing code keeps compiling. Real instances coming from the server (v2 decisions) return `undefined` for this field; v3 decisions return an array. Both are narrowable with `advice.strategy && advice.strategy.length > 0`.

- [ ] **Step 6.3: Run frontend tests**

Run: `cd frontend && npm run test -- --run`
Expected: 70/70 pass.

- [ ] **Step 6.4: Commit**

```bash
git add frontend/src/api/types.ts
git commit -m "feat(frontend): add StrategyEntry type and Advice.strategy field"
```

---

## Task 7: i18n keys for the strategy panel

Two keys — a header and the argmax hint.

**Files:**
- Modify: `frontend/src/i18n/en.ts`
- Modify: `frontend/src/i18n/fr.ts`

---

- [ ] **Step 7.1: Add to `en.ts`**

Inside the existing `advice:` block in `frontend/src/i18n/en.ts`, add (keep the order you find — preserve existing keys):

```ts
    strategy: {
      header: "Strategy",
      argmaxHint: "Follow plays the highlighted row",
    },
```

- [ ] **Step 7.2: Add matching keys to `fr.ts`**

In the `advice:` block of `frontend/src/i18n/fr.ts`:

```ts
    strategy: {
      header: "Stratégie",
      argmaxHint: "Follow joue la ligne mise en évidence",
    },
```

- [ ] **Step 7.3: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: clean. If it fails because `fr.ts` shape doesn't match `en.ts`, verify the strategy block was added in both files.

- [ ] **Step 7.4: Run existing frontend tests**

Run: `cd frontend && npm run test -- --run`
Expected: 70/70 still pass.

- [ ] **Step 7.5: Commit**

```bash
git add frontend/src/i18n/en.ts frontend/src/i18n/fr.ts
git commit -m "feat(i18n): add advice.strategy keys"
```

---

## Task 8: `StrategyBars` component + unit tests

Pure presentational component. Takes the sorted strategy array and renders one bar per entry.

**Files:**
- Create: `frontend/src/components/StrategyBars.tsx`
- Create: `frontend/src/components/StrategyBars.test.tsx`

---

- [ ] **Step 8.1: Write the failing test**

Create `frontend/src/components/StrategyBars.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { StrategyEntry } from "../api/types";
import { StrategyBars } from "./StrategyBars";

describe("StrategyBars", () => {
  const strategy: StrategyEntry[] = [
    { action: "bet", to_amount_bb: 3, frequency: 0.65 },
    { action: "check", to_amount_bb: null, frequency: 0.35 },
  ];

  it("renders one row per entry, preserving order", () => {
    render(<StrategyBars strategy={strategy} />);
    const rows = screen.getAllByTestId(/^strategy-row-/);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByTestId("strategy-label")).toHaveTextContent(/bet.*3.*bb/i);
    expect(within(rows[1]).getByTestId("strategy-label")).toHaveTextContent(/check/i);
  });

  it("renders percent labels", () => {
    render(<StrategyBars strategy={strategy} />);
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
  });

  it("marks the first row (argmax) as highlighted", () => {
    render(<StrategyBars strategy={strategy} />);
    const rows = screen.getAllByTestId(/^strategy-row-/);
    expect(rows[0]).toHaveAttribute("data-argmax", "true");
    expect(rows[1]).toHaveAttribute("data-argmax", "false");
  });

  it("sets the bar width proportional to frequency", () => {
    render(<StrategyBars strategy={strategy} />);
    const bars = screen.getAllByTestId("strategy-bar-fill");
    expect(bars[0].style.width).toBe("65%");
    expect(bars[1].style.width).toBe("35%");
  });

  it("renders no rows when strategy is empty", () => {
    const { container } = render(<StrategyBars strategy={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 8.2: Run to confirm failure**

Run: `cd frontend && npm run test -- --run src/components/StrategyBars`
Expected: FAIL — `StrategyBars` not defined.

- [ ] **Step 8.3: Implement the component**

Create `frontend/src/components/StrategyBars.tsx`:

```tsx
import type { StrategyEntry } from "../api/types";
import { useLocale } from "../i18n";
import type { DictKey } from "../i18n";

const ACTION_LABEL_KEY: Record<StrategyEntry["action"], DictKey> = {
  fold: "advice.action.fold",
  check: "advice.action.check",
  call: "advice.action.call",
  bet: "advice.action.bet",
  raise: "advice.action.raise",
  allin: "advice.action.allin",
};

const ACTION_COLOR: Record<StrategyEntry["action"], string> = {
  fold: "var(--color-parchment)",
  check: "var(--color-jade)",
  call: "var(--color-jade)",
  bet: "var(--color-gold-bright)",
  raise: "var(--color-gold-bright)",
  allin: "var(--color-coral)",
};

export function StrategyBars({ strategy }: { strategy: StrategyEntry[] }) {
  const { t } = useLocale();
  if (strategy.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5" data-testid="strategy-bars">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
          {t("advice.strategy.header")}
        </span>
        <span className="font-mono text-[8px] text-[color:var(--color-parchment-dim)] opacity-70">
          {t("advice.strategy.argmaxHint")}
        </span>
      </div>
      {strategy.map((entry, i) => {
        const isArgmax = i === 0;
        const color = ACTION_COLOR[entry.action];
        const label = `${t(ACTION_LABEL_KEY[entry.action])}${
          entry.to_amount_bb != null ? ` ${entry.to_amount_bb}bb` : ""
        }`;
        const pct = `${Math.round(entry.frequency * 100)}%`;
        return (
          <div
            key={`${entry.action}-${entry.to_amount_bb ?? "na"}-${i}`}
            data-testid={`strategy-row-${i}`}
            data-argmax={isArgmax ? "true" : "false"}
            className="relative flex items-center gap-2 text-[11px] font-mono tabular-nums"
            style={{
              padding: "2px 6px",
              borderRadius: 3,
              border: isArgmax
                ? `1px solid ${color}`
                : "1px solid rgba(201,162,94,0.12)",
              boxShadow: isArgmax ? `0 0 8px -2px ${color}` : "none",
            }}
          >
            <span
              data-testid="strategy-label"
              className="relative z-10 min-w-[70px]"
              style={{ color }}
            >
              {label}
            </span>
            <div className="relative flex-1 h-2 rounded-sm overflow-hidden bg-[rgba(10,7,6,0.5)]">
              <div
                data-testid="strategy-bar-fill"
                className="h-full"
                style={{
                  width: pct,
                  background: color,
                  opacity: isArgmax ? 0.9 : 0.45,
                }}
              />
            </div>
            <span
              className="relative z-10 text-[color:var(--color-parchment)] min-w-[32px] text-right"
            >
              {pct}
            </span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 8.4: Run tests to confirm pass**

Run: `cd frontend && npm run test -- --run src/components/StrategyBars`
Expected: 5 tests pass.

- [ ] **Step 8.5: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: clean.

- [ ] **Step 8.6: Commit**

```bash
git add frontend/src/components/StrategyBars.tsx frontend/src/components/StrategyBars.test.tsx
git commit -m "feat(frontend): add StrategyBars component"
```

---

## Task 9: Wire `StrategyBars` into `AdvicePanel`

Renders under the verdict + sizing line in `AdviceCard` when `advice.strategy` is present.

**Files:**
- Modify: `frontend/src/components/AdvicePanel.tsx`

---

- [ ] **Step 9.1: Add import**

In `frontend/src/components/AdvicePanel.tsx`, add to the existing imports:

```tsx
import { StrategyBars } from "./StrategyBars";
```

- [ ] **Step 9.2: Render below the verdict**

Inside the `AdviceCard` function, find the `<div className="flex items-baseline gap-3 mb-3">` block (the one that contains the big verdict word and the sizing `to Xbb`). Immediately after the closing `</div>` of that block, and before the `<p className="text-[13px] ...">` reasoning paragraph, insert:

```tsx
{advice.strategy && advice.strategy.length > 0 && (
  <div className="mb-3">
    <StrategyBars strategy={advice.strategy} />
  </div>
)}
```

- [ ] **Step 9.3: Run tests to confirm no regression**

Run: `cd frontend && npm run test -- --run`
Expected: 75/75 pass (70 baseline + 5 new StrategyBars tests).

- [ ] **Step 9.4: Typecheck**

Run: `cd frontend && npm run typecheck`
Expected: clean.

- [ ] **Step 9.5: Add an AdvicePanel integration test**

Append to `frontend/src/components/AdvicePanel.test.tsx`:

```tsx
import type { StrategyEntry } from "../api/types";

it("renders StrategyBars when advice.strategy is populated", () => {
  const strategy: StrategyEntry[] = [
    { action: "bet", to_amount_bb: 3, frequency: 0.6 },
    { action: "check", to_amount_bb: null, frequency: 0.4 },
  ];
  const adviceWithMix = {
    ...raiseAdvice,
    strategy,
  };
  render(
    <AdvicePanel
      stream={streamWithAdvice(adviceWithMix)}
      diverged={false}
      presetLabel="test"
      onFollow={() => undefined}
    />,
  );
  expect(screen.getByTestId("strategy-bars")).toBeInTheDocument();
  expect(screen.getAllByTestId(/^strategy-row-/)).toHaveLength(2);
});

it("does not render StrategyBars when advice.strategy is null", () => {
  render(
    <AdvicePanel
      stream={streamWithAdvice(raiseAdvice)}
      diverged={false}
      presetLabel="test"
      onFollow={() => undefined}
    />,
  );
  expect(screen.queryByTestId("strategy-bars")).toBeNull();
});
```

(Note: `raiseAdvice` in the existing file does not have a `strategy` field. The TypeScript type for `Advice` now requires `strategy` — update the `raiseAdvice` fixture to include `strategy: null`. Do this in the same test file.)

- [ ] **Step 9.6: Run the test to confirm it passes**

Run: `cd frontend && npm run test -- --run src/components/AdvicePanel`
Expected: 6 tests pass (the 4 original + 2 new).

- [ ] **Step 9.7: Full frontend test + typecheck**

Run: `cd frontend && npm run test -- --run && npm run typecheck`
Expected: all green.

- [ ] **Step 9.8: Commit**

```bash
git add frontend/src/components/AdvicePanel.tsx frontend/src/components/AdvicePanel.test.tsx
git commit -m "feat(frontend): render StrategyBars in AdvicePanel when strategy present"
```

---

## Task 10: History detail — read-only strategy bars

Surface the same component in the History detail panel when looking at a v3 decision.

**Files:**
- Modify: `frontend/src/routes/History.tsx`

---

- [ ] **Step 10.1: Find the section that renders `selected.parsed_advice`**

Open `frontend/src/routes/History.tsx` and locate the `Collapsible` block titled with `t("routes.history.sectionAdvice")`. Inside, there's a snippet rendering the action/sizing/reasoning of `selected.parsed_advice`.

- [ ] **Step 10.2: Add `StrategyBars` when strategy is present**

Add the import at the top:
```tsx
import { StrategyBars } from "../components/StrategyBars";
```

Inside the advice section's block (after the action/reasoning text, before the closing `</Collapsible>`), add:

```tsx
{selected.parsed_advice?.strategy && selected.parsed_advice.strategy.length > 0 && (
  <div className="mt-2">
    <StrategyBars strategy={selected.parsed_advice.strategy} />
  </div>
)}
```

The `selected.parsed_advice` is typed loosely in History.tsx (likely as `Record<string, unknown>` or an inline shape); if the type guard doesn't narrow cleanly, cast explicitly via `(selected.parsed_advice as Advice).strategy`. Prefer narrowing first (add a proper `Advice | null` type to `parsed_advice` in the `DecisionDetail` TS type if not already).

- [ ] **Step 10.3: Typecheck + tests**

Run: `cd frontend && npm run typecheck && npm run test -- --run`
Expected: green.

- [ ] **Step 10.4: Commit**

```bash
git add frontend/src/routes/History.tsx
git commit -m "feat(frontend): show StrategyBars in History detail for v3 decisions"
```

---

## Task 11: Flip default prompt version to `v3` in Live Coach

One-line change; `SpotAnalysis.tsx` stays on v2 per scope.

**Files:**
- Modify: `frontend/src/routes/LiveCoach.tsx`

---

- [ ] **Step 11.1: Find the hardcoded version**

Open `frontend/src/routes/LiveCoach.tsx`, search for `prompt_version: "v2"`. Replace with `"v3"`.

- [ ] **Step 11.2: Full frontend verification**

Run: `cd frontend && npm run test -- --run && npm run typecheck`
Expected: green.

- [ ] **Step 11.3: E2E spec enumeration check**

Run: `cd frontend && npx playwright test --list` (via `rtk proxy npx playwright test --list` if direct invocation is blocked).
Expected: 4 tests listed. No execution (local env lacks `libnspr4.so`; CI will run them).

- [ ] **Step 11.4: Commit**

```bash
git add frontend/src/routes/LiveCoach.tsx
git commit -m "feat(coach): default LiveCoach to prompt v3 (mixed strategy)"
```

---

## Task 12: Final verification

- [ ] **Step 12.1: Full backend test + lint**

Run: `cd backend && uv run pytest -v && uv run ruff check . && uv run mypy .`
Expected: all green.

- [ ] **Step 12.2: Full frontend test + typecheck**

Run: `cd frontend && npm run test -- --run && npm run typecheck`
Expected: all green.

- [ ] **Step 12.3: Manual smoke (optional but encouraged)**

`make dev` from repo root. Start a hand in Live Coach with any preset (e.g. `gpt-5.3-codex-xhigh` or `claude-haiku-4-5-min`), request advice, and confirm:

- A "Strategy / Stratégie" block appears below the verdict word.
- The top row is highlighted (border + glow color).
- Bar widths reflect the percentages.
- Toggle EN ↔ FR in the header; the header label switches.
- Open History, find the just-generated decision, expand the advice section — same bars show up.
- Drop back to v2 for A/B: in `LiveCoach.tsx`, temporarily change `"v3"` back to `"v2"`, reload, start a fresh hand. No bars show up. Revert.

- [ ] **Step 12.4: Commit (only if Step 12.3 found polish to apply)**

If the manual smoke surfaced any straggler (missing i18n key, visual tweak), fix it and:

```bash
git add frontend/ backend/
git commit -m "chore(mixed-strategy): polish from manual smoke"
```

---

## Summary of touched files

- **New backend:** `backend/src/poker_coach/oracle/strategy_validator.py`; `backend/tests/oracle/test_advice_round_trip.py`, `test_strategy_validator.py`; `backend/tests/prompts/test_coach_v3_render.py`.
- **New prompt:** `prompts/coach/v3.md`.
- **New frontend:** `frontend/src/components/StrategyBars.tsx`, `StrategyBars.test.tsx`.
- **Modified backend:** `oracle/base.py` (StrategyEntry, Advice.strategy), `oracle/tool_schema.py` (versioned), `oracle/anthropic_oracle.py`, `oracle/openai_oracle.py`, `prompts/context.py` (bb_chips sidecar), plus their test files.
- **Modified frontend:** `api/types.ts`, `i18n/{en,fr}.ts`, `components/AdvicePanel.tsx`, `components/AdvicePanel.test.tsx`, `routes/LiveCoach.tsx`, `routes/History.tsx`.

## Not touched (out of scope per spec)

- `SpotAnalysis.tsx` / any multi-model comparison view.
- Database schema / Alembic migrations (`parsed_advice` is already JSON).
- The LLM advice-translation path (`api/useAdviceTranslation.ts`).
- The Anthropic prompt caching canary / pricing snapshot.
- Engine code, replay, prompt leak tests.
