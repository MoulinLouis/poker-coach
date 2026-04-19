# Coach Prompt v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship a refined coach prompt (v2) that drives LLM recommendations toward what a solid HU NLHE regular would actually play — GTO-baseline, calibrated exploits per villain profile, deterministic mix resolution, structured reasoning.

**Architecture:**
- Split the monolithic v1 prompt into a stable **system prompt** (strategic frame, cached across calls, shared by both providers) + a per-spot **user prompt** (data-only payload rendered by Jinja).
- Add a new `villain_profile` input (`"reg" | "unknown"`) that the user selects in the UI, passes through the API, and the prompt references to calibrate exploits.
- Tighten `reasoning` budget from 200 → 150 words and define an explicit 3-block structure (Frame / Decision / Plan).
- **Persist** both `villain_profile` AND the system prompt (full text + sha256 hash) on the decisions row at POST time, then replay at stream time from the DB snapshot — so research fidelity survives any mid-lifecycle edit of the constant.

**Tech Stack:** FastAPI + Pydantic, SQLAlchemy Core + Alembic (SQLite), Jinja2 with `StrictUndefined`, React + Vite + TypeScript on the frontend, Playwright E2E.

**Load-bearing gotchas to re-read before touching code:**
- `CLAUDE.md` §"Load-bearing gotchas" — especially villain leak guard + `StrictUndefined` + round-tripping `GameState`.
- `backend/tests/prompts/test_no_villain_leak.py` — three leak tests that must stay green AND be extended to cover v2 (Task 1).
- Prompt versioning convention: **v1 is never deleted**. The loader path must still resolve v1 for historical replay. Live traffic moves to v2; v1 keeps a functional renderer path (Task 2's conditional `villain_profile` inclusion preserves this).

**Review-driven corrections baked in:**
1. `state_to_coach_variables` now emits `villain_profile` **only when explicitly passed**, so existing v1 call sites don't break between commits.
2. System prompt is persisted on the decision row (new columns) and the stream route passes the DB-snapshotted value to the oracle — the constant is never read at stream time.
3. Villain-leak tests are parametrized over `["v1", "v2"]`.
4. `DecisionDetail` / `DecisionListRow` pydantic + TS types expose `villain_profile` so the verification step can actually observe it.

---

## Task 1: Create `prompts/coach/v2.md` + extend villain-leak suite to cover v2

**Files:**
- Create: `prompts/coach/v2.md`
- Modify: `backend/tests/prompts/test_no_villain_leak.py` (parametrize over v1 / v2)
- Modify: `backend/tests/prompts/test_renderer.py` (append a v2 smoke test; do not replace the v1 smoke)

**Step 1: Create `prompts/coach/v2.md`**

```markdown
---
name: coach
version: v2
description: HU coach prompt v2 — data-only payload; strategic frame lives in system prompt.
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
  - history
  - legal_actions
  - villain_profile
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

## Villain profile
{{ villain_profile }}

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

Call `submit_advice` now.
```

**Step 2: Parametrize `test_no_villain_leak.py`**

Rewrite the existing tests to cover both versions. Replace the test file content from line 38 onward with:

```python
import pytest


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_coach_variables_omit_forbidden_keys(version: str) -> None:
    # Variables projection is version-agnostic, but both prompts must
    # consume the same projection shape modulo villain_profile.
    state = _sample_state(("As", "Kd"), ("Qc", "Qh"))
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    leaked = FORBIDDEN_KEYS & set(variables.keys())
    assert leaked == set(), f"leaked keys for {version}: {leaked}"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_coach_declared_vars_omit_forbidden_keys(version: str) -> None:
    renderer = PromptRenderer(PROMPTS_ROOT)
    template = renderer.load("coach", version)
    declared = set(template.declared_variables)
    leaked = FORBIDDEN_KEYS & declared
    assert leaked == set(), f"coach/{version} declares forbidden variables: {leaked}"


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_rendered_coach_prompt_does_not_contain_villain_cards(version: str) -> None:
    hero = ("2c", "3c")
    villain = ("7h", "7s")
    state = _sample_state(hero, villain)

    renderer = PromptRenderer(PROMPTS_ROOT)
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    rendered = renderer.render("coach", version, variables)

    assert "7h" not in rendered.rendered_prompt
    assert "7s" not in rendered.rendered_prompt
    assert "2c" in rendered.rendered_prompt
    assert "3c" in rendered.rendered_prompt


@pytest.mark.parametrize("version", ["v1", "v2"])
def test_rendered_prompt_also_excludes_deck_snapshot(version: str) -> None:
    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        rng_seed=42,
    )
    assert state.deck_snapshot is not None

    renderer = PromptRenderer(PROMPTS_ROOT)
    variables = state_to_coach_variables(
        state,
        villain_profile="unknown" if version == "v2" else None,
    )
    rendered = renderer.render("coach", version, variables)

    villain_0, villain_1 = state.deck_snapshot[2], state.deck_snapshot[3]
    assert villain_0 not in rendered.rendered_prompt
    assert villain_1 not in rendered.rendered_prompt
    for unexposed in state.deck_snapshot[4:9]:
        assert unexposed not in rendered.rendered_prompt, (
            f"unexposed board card {unexposed} leaked into {version} prompt"
        )
```

The `tmp_path` arg on the original `test_rendered_prompt_also_excludes_deck_snapshot` is unused — drop it.

**Step 3: Append v2 smoke test in `test_renderer.py`**

```python
def test_coach_v2_renders_against_sample_state() -> None:
    """Smoke test: coach v2 renders cleanly with villain_profile included."""
    from poker_coach.engine.rules import start_hand
    from poker_coach.prompts.context import state_to_coach_variables

    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render(
        "coach",
        "v2",
        state_to_coach_variables(state, villain_profile="reg"),
    )
    assert "As Kd" in rendered.rendered_prompt
    assert "reg" in rendered.rendered_prompt
    # v2 no longer carries the strategic intro paragraph — it lives in system prompt.
    assert "Your job: evaluate" not in rendered.rendered_prompt
```

**Step 4: Don't run tests yet** — they depend on Task 2's `state_to_coach_variables` signature (optional `villain_profile` kwarg). Tests run at the end of Task 2.

**Step 5: Commit (deferred to Task 2)**

---

## Task 2: Extend `state_to_coach_variables` to accept optional `villain_profile`

**Files:**
- Modify: `backend/src/poker_coach/prompts/context.py`

**Step 1: Rewrite `state_to_coach_variables`**

Replace the file body:

```python
"""Project a GameState into the variable dict the coach prompt consumes.

Deliberately omits villain_hole and deck_snapshot so the prompt never
leaks information the hero can't see during live play. Spot-analysis
mode goes through this same projection.

villain_profile is conditional: when callers pass it, we include it in
the output dict (needed by coach/v2 which declares the variable).
Leaving it out keeps backward compatibility with coach/v1 which has
no such variable declared. The renderer rejects unexpected keys, so
this conditional inclusion is load-bearing: do not flip it to always-on.
"""

from typing import Any, Literal

from poker_coach.engine.models import GameState
from poker_coach.engine.rules import legal_actions

VillainProfile = Literal["reg", "unknown"]


def _bb(chips: int, bb: int) -> float:
    return round(chips / bb, 2)


def state_to_coach_variables(
    state: GameState,
    villain_profile: VillainProfile | None = None,
) -> dict[str, Any]:
    bb = state.bb
    history = [
        {
            "actor": a.actor,
            "type": a.type,
            "to_amount_bb": _bb(a.to_amount, bb) if a.to_amount is not None else None,
        }
        for a in state.history
    ]
    legal = [
        {
            "type": la.type,
            "min_to_bb": _bb(la.min_to, bb) if la.min_to is not None else None,
            "max_to_bb": _bb(la.max_to, bb) if la.max_to is not None else None,
        }
        for la in legal_actions(state)
    ]
    result: dict[str, Any] = {
        "street": state.street,
        "hero_hole": list(state.hero_hole),
        "board": list(state.board),
        "button": state.button,
        "pot_bb": _bb(state.pot, bb),
        "effective_bb": _bb(state.effective_stack, bb),
        "hero_stack_bb": _bb(state.stacks["hero"], bb),
        "villain_stack_bb": _bb(state.stacks["villain"], bb),
        "hero_committed_bb": _bb(state.committed["hero"], bb),
        "villain_committed_bb": _bb(state.committed["villain"], bb),
        "history": history,
        "legal_actions": legal,
    }
    if villain_profile is not None:
        result["villain_profile"] = villain_profile
    return result
```

**Step 2: Run the prompt test suite**

Run: `cd backend && uv run pytest tests/prompts/ -v`

Expected: all green. The parametrized leak tests cover v1 (no `villain_profile` kwarg) and v2 (with kwarg). The v1 smoke test passes with the default `None`. The new v2 smoke test passes with `villain_profile="reg"`.

**Step 3: Sanity check — existing callers don't regress**

Run: `grep -rn 'state_to_coach_variables(' backend/src backend/tests`

Each call site either:
- passes no `villain_profile` → renders v1 safely (the route path), or
- passes `villain_profile` explicitly → renders v2 (new path, added in Task 9).

**Step 4: Commit (bundles Task 1 + Task 2)**

```bash
git add prompts/coach/v2.md \
        backend/src/poker_coach/prompts/context.py \
        backend/tests/prompts/test_renderer.py \
        backend/tests/prompts/test_no_villain_leak.py
git commit -m "feat(prompts): add coach v2 template with conditional villain_profile variable"
```

---

## Task 3: Tighten `TOOL_DESCRIPTION` in the tool schema

**Files:**
- Modify: `backend/src/poker_coach/oracle/tool_schema.py:18-23`
- Modify: `backend/tests/oracle/test_tool_schema.py` (fixture snapshot drift)

**Step 1: Update `TOOL_DESCRIPTION`**

Replace lines 18-23 in `backend/src/poker_coach/oracle/tool_schema.py`:

```python
TOOL_DESCRIPTION = (
    "Submit the final recommendation for the hero's action. Call this exactly once "
    "when you have a conclusion. action must be one of the legal types the prompt "
    "listed; to_amount_bb is required for bet and raise, omitted otherwise; "
    "reasoning is a structured (<=150 word) explanation following the "
    "frame/decision/plan format described in the system prompt; confidence "
    "reflects mix closeness (high = dominant, medium = close, low = borderline)."
)
```

**Step 2: Run the tool schema tests to see the drift**

Run: `cd backend && uv run pytest tests/oracle/test_tool_schema.py -v`

Expected: FAIL — fixture snapshot drift on description field.

**Step 3: Update the snapshot fixture**

Locate the expected description string in `test_tool_schema.py` (either inline or as a fixture) and update to match the new constant.

**Step 4: Run tests**

Run: `cd backend && uv run pytest tests/oracle/test_tool_schema.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/poker_coach/oracle/tool_schema.py backend/tests/oracle/test_tool_schema.py
git commit -m "feat(oracle): tighten submit_advice description to 150-word structured reasoning"
```

---

## Task 4: Create shared `SYSTEM_PROMPT` constant

**Files:**
- Create: `backend/src/poker_coach/oracle/system_prompt.py`
- Create: `backend/tests/oracle/test_system_prompt.py`

**Step 1: Write a sanity test**

Create `backend/tests/oracle/test_system_prompt.py`:

```python
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT


def test_system_prompt_mentions_both_villain_profiles() -> None:
    assert "`reg`" in SYSTEM_PROMPT
    assert "`unknown`" in SYSTEM_PROMPT


def test_system_prompt_enforces_tool_only_output() -> None:
    assert "submit_advice" in SYSTEM_PROMPT
    assert "ONLY VISIBLE OUTPUT" in SYSTEM_PROMPT


def test_system_prompt_documents_confidence_mapping() -> None:
    assert "`high`" in SYSTEM_PROMPT
    assert "`medium`" in SYSTEM_PROMPT
    assert "`low`" in SYSTEM_PROMPT


def test_system_prompt_reasoning_budget_is_150_words() -> None:
    assert "150 words" in SYSTEM_PROMPT or "<=150" in SYSTEM_PROMPT
```

**Step 2: Run it to verify it fails**

Run: `cd backend && uv run pytest tests/oracle/test_system_prompt.py -v`

Expected: FAIL — module doesn't exist.

**Step 3: Create `backend/src/poker_coach/oracle/system_prompt.py`**

```python
"""Shared system prompt for the coach pack.

Stable strategic frame sent alongside every per-spot user prompt. Both
Anthropic and OpenAI oracles consume this constant. Prompt caching lets
the providers amortize the system prompt across a session's decisions.

IMPORTANT: this constant is also persisted verbatim on every decision
row (see decisions.system_prompt column) at POST time. The stream route
reads that persisted snapshot and passes it to the oracle, so an edit
of this constant between POST and stream-open does NOT retroactively
change what the model received for an in-flight decision.
"""

SYSTEM_PROMPT = """You are a heads-up No-Limit Hold'em coach. Your recommendation must match what a solid human regular would actually play — not abstract GTO theory, not academic output. Decisive, grounded, coherent across streets.

## Strategic frame

Start from a GTO-baseline (simplified solver-aligned play: standard sizings, coherent ranges, no exotic mixes) and apply exploits calibrated to the villain profile. GTO is the floor, not the target — deviate toward higher EV when the villain profile warrants it.

### Villain profiles

- `reg` — solid regular. Balanced ranges, standard sizings, near-GTO defaults. Apply only small exploits correcting for typical reg micro-leaks (slightly under-bluffed rivers, mild over-folds to large overbets). Do not assume broad population leaks.

- `unknown` — random player from a typical low/mid-stakes pool. Apply standard population exploits:
  - Over-folds to small c-bets, under-folds to large ones
  - Under-bluffs turn and river (tighten bluffcatches)
  - Over-calls flop (thin value, fewer flop bluffs)
  - Over-defends preflop with trash
  - Caps on check-check lines (attack with delayed aggression)
  Deviate more than vs a reg, but never abandon the GTO frame entirely.

## Mix resolution

When the theoretically correct play is a mix, pick one deterministically:

- >=70% dominant action -> pick silently; do not mention the alternative.
- 55-70% -> pick, acknowledge alternative in one clause ("bet preferred; check also viable").
- ~50/50 -> break the tie using the villain exploit direction; flag the closeness.

Never randomize. Never output two actions as a choice. One action, decisively.

## Simplified play

Real regulars simplify:
- One preferred sizing per spot, not three mixed frequencies
- Coherent ranges across streets (don't barrel scare cards without value)
- Standard HU sizings for the stack depth
- No exotic lines unless the spot genuinely calls for it

## Confidence mapping

- `high` — clearly dominant (>=70% or obvious exploit)
- `medium` — preferred but close (55-70%)
- `low` — borderline (~50/50); tie-break

## Output contract

YOUR ONLY VISIBLE OUTPUT IS ONE CALL TO `submit_advice`. No text block, no narration.

Structure `reasoning` (<=150 words):
1. **Frame** (1 sentence): spot type + hero's relative strength.
2. **Decision** (2-3 sentences): why this action; key strategic reason; exploit applied.
3. **Plan** (1 sentence): next-street read or why this line is final.

Assume a competent reader. Do not restate board/stacks. Do not explain basics.
"""

__all__ = ["SYSTEM_PROMPT"]
```

**Step 4: Run the test**

Run: `cd backend && uv run pytest tests/oracle/test_system_prompt.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/poker_coach/oracle/system_prompt.py backend/tests/oracle/test_system_prompt.py
git commit -m "feat(oracle): add shared SYSTEM_PROMPT with GTO-baseline frame and villain profiles"
```

---

## Task 5: Update Oracle protocol + Anthropic oracle to accept `system_prompt` kwarg

**Files:**
- Modify: `backend/src/poker_coach/oracle/base.py:105-108` (Protocol signature)
- Modify: `backend/src/poker_coach/oracle/anthropic_oracle.py`
- Modify: `backend/tests/oracle/test_anthropic_oracle.py`

**Background:** to preserve research fidelity (Finding 2), the oracle must use the system prompt that was captured at decision creation time, not re-import the live constant at stream time. We make `system_prompt` an optional kwarg on `advise_stream` — when `None`, falls back to the imported `SYSTEM_PROMPT` so intermediate commits don't break the stream route (updated in Task 9).

**Step 1: Update the Oracle protocol**

In `backend/src/poker_coach/oracle/base.py`, replace the `Oracle` class (lines 105-108):

```python
class Oracle(Protocol):
    def advise_stream(
        self,
        rendered: RenderedPrompt,
        spec: ModelSpec,
        system_prompt: str | None = None,
    ) -> AsyncIterator[OracleEvent]: ...
```

**Step 2: Update `anthropic_oracle.py`**

Add the import at the top:

```python
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT
```

Delete the existing `_SYSTEM_ENFORCE_TOOL = (...)` block (lines 33-45 in the current file).

Update the `advise_stream` signature:

```python
async def advise_stream(
    self,
    rendered: RenderedPrompt,
    spec: ModelSpec,
    system_prompt: str | None = None,
) -> AsyncIterator[OracleEvent]:
    effective_system = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    ...
```

Replace the line `"system": _SYSTEM_ENFORCE_TOOL,` with `"system": effective_system,`.

**Step 3: Update tests in `test_anthropic_oracle.py`**

If any test asserts on the old system prompt content, update to check against something stable in the new `SYSTEM_PROMPT` (e.g., `"solid human regular"` or `"ONLY VISIBLE OUTPUT"`).

Add a new test:

```python
def test_anthropic_oracle_uses_explicit_system_prompt_when_passed(
    sample_pricing: PricingSnapshot,
) -> None:
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_stream(**kwargs: Any):
        captured.update(kwargs)
        yield _fake_anthropic_stream_with_tool_use()  # use existing helper

    oracle = AnthropicOracle(stream_caller=fake_stream, pricing=sample_pricing)
    rendered = _sample_rendered_prompt()
    spec = _sample_spec_no_thinking()

    custom = "OVERRIDE SYSTEM PROMPT FOR TEST"

    async def collect() -> None:
        async for _ in oracle.advise_stream(rendered, spec, system_prompt=custom):
            pass

    asyncio.run(collect())
    assert captured["system"] == custom
```

Adapt helper names to match what's already in the test file.

**Step 4: Run the Anthropic tests**

Run: `cd backend && uv run pytest tests/oracle/test_anthropic_oracle.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/poker_coach/oracle/base.py \
        backend/src/poker_coach/oracle/anthropic_oracle.py \
        backend/tests/oracle/test_anthropic_oracle.py
git commit -m "refactor(oracle): accept system_prompt kwarg on Anthropic oracle with SYSTEM_PROMPT fallback"
```

---

## Task 6: OpenAI oracle — accept `system_prompt` via `instructions`

**Files:**
- Modify: `backend/src/poker_coach/oracle/openai_oracle.py`
- Modify: `backend/tests/oracle/test_openai_oracle.py`

**Step 1: Write the failing test**

Append to `backend/tests/oracle/test_openai_oracle.py`:

```python
def test_openai_oracle_passes_system_prompt_as_instructions(
    sample_pricing: PricingSnapshot,
) -> None:
    from poker_coach.oracle.system_prompt import SYSTEM_PROMPT

    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_stream(**kwargs: Any):
        captured.update(kwargs)
        yield _fake_openai_stream_with_tool_call()  # use existing helper

    oracle = OpenAIOracle(stream_caller=fake_stream, pricing=sample_pricing)
    rendered = _sample_rendered_prompt()
    spec = _sample_openai_spec()

    async def collect() -> None:
        async for _ in oracle.advise_stream(rendered, spec):
            pass

    asyncio.run(collect())
    assert captured["instructions"] == SYSTEM_PROMPT


def test_openai_oracle_uses_explicit_system_prompt_when_passed(
    sample_pricing: PricingSnapshot,
) -> None:
    captured: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_stream(**kwargs: Any):
        captured.update(kwargs)
        yield _fake_openai_stream_with_tool_call()

    oracle = OpenAIOracle(stream_caller=fake_stream, pricing=sample_pricing)
    custom = "CUSTOM SYSTEM PROMPT"

    async def collect() -> None:
        async for _ in oracle.advise_stream(
            _sample_rendered_prompt(),
            _sample_openai_spec(),
            system_prompt=custom,
        ):
            pass

    asyncio.run(collect())
    assert captured["instructions"] == custom
```

Adapt helper names to match existing test structure.

**Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/oracle/test_openai_oracle.py -v -k system_prompt`

Expected: FAIL (no `instructions` kwarg passed yet).

**Step 3: Update `openai_oracle.py`**

Add the import:

```python
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT
```

Update `advise_stream` signature and kwargs dict:

```python
async def advise_stream(
    self,
    rendered: RenderedPrompt,
    spec: ModelSpec,
    system_prompt: str | None = None,
) -> AsyncIterator[OracleEvent]:
    effective_system = system_prompt if system_prompt is not None else SYSTEM_PROMPT
    kwargs: dict[str, Any] = {
        "model": spec.model_id,
        "instructions": effective_system,
        "input": [{"role": "user", "content": rendered.rendered_prompt}],
        "tools": [openai_tool_spec()],
        "tool_choice": {"type": "function", "name": "submit_advice"},
    }
    ...
```

**Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/oracle/test_openai_oracle.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add backend/src/poker_coach/oracle/openai_oracle.py backend/tests/oracle/test_openai_oracle.py
git commit -m "feat(oracle): send SYSTEM_PROMPT via OpenAI instructions kwarg with override support"
```

---

## Task 7: Alembic migration — add `villain_profile`, `system_prompt`, `system_prompt_hash`

**Files:**
- Create: `backend/src/poker_coach/db/migrations/versions/20260418_0003_coach_v2_columns.py`
- Modify: `backend/src/poker_coach/db/tables.py` (add the three columns)

**Step 1: Create the migration**

Create `backend/src/poker_coach/db/migrations/versions/20260418_0003_coach_v2_columns.py`:

```python
"""add villain_profile + system_prompt snapshot columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "villain_profile",
            sa.String(16),
            nullable=False,
            server_default="unknown",
        ),
    )
    # System prompt + hash are nullable: historical rows have no
    # system prompt snapshot. New rows always write both.
    op.add_column("decisions", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("system_prompt_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "system_prompt_hash")
    op.drop_column("decisions", "system_prompt")
    op.drop_column("decisions", "villain_profile")
```

**Step 2: Update `decisions` Table in `tables.py`**

Insert the three new columns right after `Column("variables", JSON, nullable=False)`:

```python
    Column("variables", JSON, nullable=False),
    Column("villain_profile", String(16), nullable=False, server_default="unknown"),
    Column("system_prompt", Text, nullable=True),
    Column("system_prompt_hash", String(64), nullable=True),
    # Model config
    Column("provider", String(32), nullable=False),
```

**Step 3: Run the migration**

Run: `make db-upgrade`

Expected: no errors.

**Step 4: Run the backend test suite**

Run: `cd backend && uv run pytest tests/api/ tests/prompts/ tests/oracle/ -v`

Expected: all green. Existing tests that `INSERT` into `decisions` without specifying `villain_profile` still work (server default kicks in). Tests that don't write `system_prompt` get NULL — OK because column is nullable.

**Step 5: Commit**

```bash
git add backend/src/poker_coach/db/migrations/versions/20260418_0003_coach_v2_columns.py \
        backend/src/poker_coach/db/tables.py
git commit -m "feat(db): add villain_profile + system_prompt snapshot columns to decisions"
```

---

## Task 8: Add `villain_profile` to `CreateDecisionRequest`

**Files:**
- Modify: `backend/src/poker_coach/api/schemas.py:37-44`

**Step 1: Update `CreateDecisionRequest`**

In `backend/src/poker_coach/api/schemas.py`:

```python
from poker_coach.prompts.context import VillainProfile  # noqa: TC001


class CreateDecisionRequest(BaseModel):
    session_id: str
    hand_id: str | None = None
    model_preset: str
    prompt_name: str
    prompt_version: str
    game_state: GameState
    retry_of: str | None = None
    villain_profile: VillainProfile = "unknown"
```

**Step 2: Defer tests** — wired in Task 9. Don't commit yet.

---

## Task 9: Wire villain_profile + system_prompt through the routes

**Files:**
- Modify: `backend/src/poker_coach/api/routes/decisions.py` (POST write path, `DecisionListRow`, `DecisionDetail`)
- Modify: `backend/src/poker_coach/api/routes/stream.py:120-146` (read system_prompt, pass to oracle)
- Modify: `backend/tests/api/test_lifecycle.py` (update existing v1 tests to include `villain_profile` field or rely on default; add v2-path tests)

**Step 1: Update `decisions.py` POST handler**

Replace the body of `create_decision` (around line 76 onward):

```python
    renderer = PromptRenderer(prompts_root)
    try:
        variables = state_to_coach_variables(
            body.game_state,
            villain_profile=body.villain_profile if body.prompt_version == "v2" else None,
        )
        rendered = renderer.render(body.prompt_name, body.prompt_version, variables)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"prompt render failed: {exc}") from exc

    system_prompt_snapshot = SYSTEM_PROMPT
    system_prompt_hash_snapshot = hashlib.sha256(
        system_prompt_snapshot.encode("utf-8")
    ).hexdigest()
```

Add the imports at the top:

```python
import hashlib
from poker_coach.oracle.system_prompt import SYSTEM_PROMPT
```

In the `insert(decisions).values(...)` block, add three lines:

```python
                variables=variables,
                villain_profile=body.villain_profile,
                system_prompt=system_prompt_snapshot,
                system_prompt_hash=system_prompt_hash_snapshot,
                provider=spec.provider,
```

**Step 2: Update `DecisionListRow` and `DecisionDetail` models**

In the same file, add `villain_profile: str` to `DecisionListRow`:

```python
class DecisionListRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: str
    created_at: str
    session_id: str
    hand_id: str | None
    model_id: str
    prompt_name: str
    prompt_version: str
    villain_profile: str
    status: str
    parsed_advice: dict[str, Any] | None
    cost_usd: float | None
    latency_ms: int | None
```

And `system_prompt_hash: str | None` to `DecisionDetail`:

```python
class DecisionDetail(DecisionListRow):
    game_state: dict[str, Any]
    template_hash: str
    template_raw: str
    rendered_prompt: str
    system_prompt_hash: str | None
    ...
```

(Full `DecisionDetail` shown in current file — add `system_prompt_hash` after `template_hash`.)

Update the SELECT statement in `list_decisions` to include `decisions.c.villain_profile`, and update both `DecisionListRow(...)` and `DecisionDetail(...)` constructors to populate the new fields. For `get_decision_detail`, since it uses `select(decisions)` (all columns), just add `villain_profile=row.villain_profile` and `system_prompt_hash=row.system_prompt_hash` to the constructor call.

**Step 3: Update `stream.py` to pass system_prompt to the oracle**

In `backend/src/poker_coach/api/routes/stream.py`, extend the SELECT at line 120-130 to include `decisions.c.system_prompt`:

```python
            select(
                decisions.c.template_raw,
                decisions.c.rendered_prompt,
                decisions.c.template_hash,
                decisions.c.prompt_name,
                decisions.c.prompt_version,
                decisions.c.variables,
                decisions.c.provider,
                decisions.c.model_id,
                decisions.c.system_prompt,
            ).where(decisions.c.decision_id == decision_id)
```

Then update the `oracle.advise_stream(rendered, spec)` call (around line 153) to:

```python
            async for event in oracle.advise_stream(
                rendered, spec, system_prompt=row.system_prompt
            ):
```

If `row.system_prompt` is `None` (legacy rows pre-migration), oracles fall back to the imported `SYSTEM_PROMPT` — behavior preserved.

**Step 4: Update the lifecycle tests**

In `backend/tests/api/test_lifecycle.py`:

1. The existing happy-path test at line 139 posts `prompt_version: "v1"` — that path is still valid. The server default for `villain_profile` is `"unknown"`; the request can omit the field. Verify the existing test still passes.

2. Add a new test for the v2 path:

```python
def test_v2_decision_persists_villain_profile_and_system_prompt(
    app_with_factory: Any, migrated_engine: Engine
) -> None:
    with TestClient(app_with_factory) as client:
        resp = client.post("/api/sessions", json={"mode": "live"})
        session_id = resp.json()["session_id"]

        resp = client.post(
            "/api/hands",
            json={"session_id": session_id, "bb": 100, "effective_stack_start": 10_000},
        )
        hand_id = resp.json()["hand_id"]

        resp = client.post(
            "/api/decisions",
            json={
                "session_id": session_id,
                "hand_id": hand_id,
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v2",
                "game_state": _sample_game_state(),
                "villain_profile": "reg",
            },
        )
        assert resp.status_code == 200
        decision_id = resp.json()["decision_id"]

        with migrated_engine.connect() as conn:
            row = conn.execute(
                select(
                    decisions.c.villain_profile,
                    decisions.c.system_prompt,
                    decisions.c.system_prompt_hash,
                    decisions.c.rendered_prompt,
                ).where(decisions.c.decision_id == decision_id)
            ).one()
        assert row.villain_profile == "reg"
        assert row.system_prompt is not None
        assert "solid human regular" in row.system_prompt
        assert len(row.system_prompt_hash) == 64
        # The user prompt reflects the chosen profile.
        assert "reg" in row.rendered_prompt


def test_v2_decision_rejects_invalid_villain_profile(app_with_factory: Any) -> None:
    with TestClient(app_with_factory) as client:
        resp = client.post(
            "/api/decisions",
            json={
                "session_id": "anything",
                "model_preset": "claude-opus-4-7-deep",
                "prompt_name": "coach",
                "prompt_version": "v2",
                "game_state": _sample_game_state(),
                "villain_profile": "whale",
            },
        )
        assert resp.status_code == 422
```

**Step 5: Run the full test suite**

Run: `cd backend && make test`

Expected: all green.

**Step 6: Commit**

```bash
git add backend/src/poker_coach/api/schemas.py \
        backend/src/poker_coach/api/routes/decisions.py \
        backend/src/poker_coach/api/routes/stream.py \
        backend/tests/api/test_lifecycle.py
git commit -m "feat(api): persist villain_profile + system_prompt snapshot on decisions; replay from DB at stream time"
```

---

## Task 10: Frontend — API client types

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts:70-80`

**Step 1: Update `types.ts`**

Add after line 11:

```ts
export type VillainProfile = "reg" | "unknown";
```

Extend `DecisionListRow` and `DecisionDetail`:

```ts
export interface DecisionListRow {
  decision_id: string;
  created_at: string;
  session_id: string;
  hand_id: string | null;
  model_id: string;
  prompt_name: string;
  prompt_version: string;
  villain_profile: string;
  status: string;
  parsed_advice: Advice | null;
  cost_usd: number | null;
  latency_ms: number | null;
}

export interface DecisionDetail extends DecisionListRow {
  game_state: GameState;
  template_hash: string;
  template_raw: string;
  rendered_prompt: string;
  system_prompt_hash: string | null;
  reasoning_text: string | null;
  // ... rest unchanged
}
```

**Step 2: Update `client.ts`**

Modify the `createDecision` signature (lines 70-80):

```ts
export async function createDecision(input: {
  session_id: string;
  hand_id?: string | null;
  model_preset: string;
  prompt_name: string;
  prompt_version: string;
  game_state: GameState;
  retry_of?: string | null;
  villain_profile?: VillainProfile;
}): Promise<{ decision_id: string }> {
  return postJSON("/api/decisions", input);
}
```

Add `VillainProfile` to the imports from `./types`.

**Step 3: Typecheck**

Run: `cd frontend && npm run typecheck`

Expected: PASS. If `History.tsx` consumes `DecisionListRow` / `DecisionDetail`, it now has access to `villain_profile` — typecheck will surface any destructuring mismatches. Update consumers as needed (likely no-op; untouched fields just flow through).

**Step 4: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts
git commit -m "feat(frontend): add VillainProfile type and villain_profile field to DecisionRow types"
```

---

## Task 11: Frontend — villain profile toggle in LiveCoach

**Files:**
- Modify: `frontend/src/components/SetupPanel.tsx` (extend `SetupValues` + toggle UI)
- Modify: `frontend/src/routes/LiveCoach.tsx` (pass villain_profile, bump to v2)

**Step 1: Read existing SetupPanel**

Run: `cat frontend/src/components/SetupPanel.tsx`

**Step 2: Extend SetupValues + add toggle**

Add `villainProfile: VillainProfile` to `SetupValues` and its defaults. Import `VillainProfile` from `../api/types`. Insert a toggle near the existing controls:

```tsx
<label className="flex flex-col gap-1 text-xs text-stone-300">
  Villain profile
  <div className="flex gap-1 rounded bg-stone-800 p-1">
    {(["reg", "unknown"] as const).map((p) => (
      <button
        key={p}
        type="button"
        className={`flex-1 rounded px-2 py-1 text-xs ${
          values.villainProfile === p
            ? "bg-stone-600 text-stone-100"
            : "text-stone-400 hover:text-stone-200"
        }`}
        onClick={() => onChange({ villainProfile: p })}
      >
        {p === "reg" ? "Reg" : "Unknown"}
      </button>
    ))}
  </div>
</label>
```

**Step 3: Update LiveCoach default state + createDecision call**

Around line 46-52:

```tsx
const [setup, setSetup] = useState<SetupValues>({
  heroHole: "AsKd",
  villainHole: "QcQh",
  effectiveStack: 10_000,
  button: "hero",
  presetId: "",
  villainProfile: "unknown",
});
```

Around line 149-156:

```tsx
const { decision_id } = await createDecision({
  session_id: session.sessionId,
  hand_id: session.handId,
  model_preset: setup.presetId,
  prompt_name: "coach",
  prompt_version: "v2",
  game_state: snapshot.state,
  villain_profile: setup.villainProfile,
});
```

**Step 4: Typecheck + frontend tests**

Run: `cd frontend && npm run typecheck && npm test -- --run`

Expected: PASS.

**Step 5: Commit**

```bash
git add frontend/src/components/SetupPanel.tsx frontend/src/routes/LiveCoach.tsx
git commit -m "feat(frontend): add villain profile toggle and switch LiveCoach to coach v2"
```

---

## Task 12: Frontend — villain profile in SpotAnalysis

**Files:**
- Modify: `frontend/src/routes/SpotAnalysis.tsx`

**Step 1: Add state + toggle UI**

Near the other `useState` declarations:

```tsx
const [villainProfile, setVillainProfile] = useState<VillainProfile>("unknown");
```

Import `VillainProfile`. Add toggle UI mirroring `SetupPanel`'s pattern.

**Step 2: Update createDecision**

Replace lines 146-152:

```tsx
createDecision({
  session_id: sessionId,
  model_preset: c.presetId,
  prompt_name: "coach",
  prompt_version: "v2",
  game_state: snapshot.state,
  villain_profile: villainProfile,
}),
```

**Step 3: Typecheck + tests**

Run: `cd frontend && npm run typecheck && npm test -- --run`

Expected: PASS.

**Step 4: Commit**

```bash
git add frontend/src/routes/SpotAnalysis.tsx
git commit -m "feat(frontend): wire villain profile through SpotAnalysis and bump to coach v2"
```

---

## Task 13: Full-stack verification

**Files:** (verification only — no code changes unless issues surface)

**Step 1: Full test suite**

Run: `make test`

Expected: all green.

**Step 2: Lint**

Run: `make lint`

Expected: clean.

**Step 3: E2E**

Run: `make e2e`

Expected: Playwright flow passes. If a prior E2E test asserted on `prompt_version: "v1"` or the exact request payload, update it to v2 + default villain_profile.

**Step 4: Manual smoke via browser**

Run: `make dev` and in a browser:

1. Open Live Coach. Verify the villain profile toggle appears.
2. Play a hand with profile = "reg". Request advice. Check the AdvicePanel shows a coherent recommendation.
3. Play another hand with profile = "unknown". Verify the advice acknowledges population exploits (subjective — the reasoning field should mention fold-tendency or similar).
4. Open DevTools → Network, inspect a recent `POST /api/decisions` payload — `villain_profile` must be present.

**Step 5: Manual smoke via API**

```bash
DECISION_ID=<paste from network tab>
curl -s http://localhost:8000/api/decisions/$DECISION_ID/detail | jq '{villain_profile, system_prompt_hash, prompt_version}'
```

Expected output (example):
```json
{
  "villain_profile": "reg",
  "system_prompt_hash": "a3f2...",
  "prompt_version": "v2"
}
```

Confirms the persisted snapshot path works end-to-end.

**Step 6: Confirm no live v1 references**

Run: `grep -rn 'prompt_version.*v1\|"v1"' frontend/src backend/src`

Expected hits only in:
- `prompts/coach/v1.md` (archival)
- no live call sites

Historical test fixtures (`test_lifecycle.py` still exercises v1 paths intentionally for back-compat coverage) are OK.

**Step 7: Commit only if cleanup surfaced**

If all green with no diffs, no commit. Otherwise:

```bash
git commit -m "fix(...): address leftover issue surfaced during v2 rollout"
```

---

## Post-merge follow-ups (out of scope)

- **Expose villain_profile + system_prompt_hash in History detail UI**: the data is persisted and typed but not yet rendered. Small React addition.
- **Tombstone v1 live usage**: after a soak period, the decisions route could reject `prompt_version: "v1"` from new POSTs while keeping the loader path alive for replay.
- **Auto-detect system prompt drift**: a CI check comparing the latest in-DB `system_prompt_hash` values against the current constant could warn when prompts diverge from past decisions (useful for research reproducibility).
- **Extend villain profiles** (e.g., `nit`, `fish`, `lag`) once the two-option baseline proves useful.
