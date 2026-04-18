# Three-layer villain-information guard

## Context

The LLM plays as hero. If villain's hole cards or the undealt deck ever reach the prompt, the coaching signal is worthless — the whole project is undermined. This must be prevented structurally, not by discipline.

## Decision

Hidden information is blocked at three independent layers:

1. **`state_to_coach_variables`** (`backend/src/poker_coach/prompts/context.py`) — projects `GameState` to a variables dict. Does **not** emit `villain_hole`, `deck_snapshot`, `rng_seed`.
2. **Prompt frontmatter** — `prompts/coach/v1.md` declares only the variables the body needs. None of them reveal villain info.
3. **Jinja2 `StrictUndefined`** — the renderer rejects any body that references an undeclared variable. So even if someone adds a leak to the body without updating the frontmatter, rendering fails loudly.

## Rationale

Single-layer checks can be regressed by a one-line edit. Three independent layers (projection, declared list, renderer validator) require breaking all three simultaneously to leak.

## Canary

`backend/tests/prompts/test_no_villain_leak.py` — four regression tests that assert (a) context function doesn't emit the forbidden keys, (b) prompt frontmatter doesn't declare them, (c) rendered output does not contain villain's hole cards, (d) rendered output does not contain any undealt deck card. Any change that trips one of those four is the breach.

## Implementing commits

- `a00a74f` — prompt renderer with StrictUndefined + declared variables
- `e76bbc6` — three-layer leak regression tests
