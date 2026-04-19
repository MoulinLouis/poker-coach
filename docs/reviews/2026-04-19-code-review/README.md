# Code Review — 2026-04-19

Project-wide review for AI slop, dead code, duplication, inefficiency, and polish opportunities. Findings are read-only; no code has been modified.

## Method

Four Explore subagents ran in parallel, each with narrow scope and a hard constraint not to edit files. Each was given the CLAUDE.md load-bearing invariants to avoid suggesting anything that would regress documented behavior.

## Output files

| File | Scope | Findings |
|---|---|---|
| [backend-engine.md](backend-engine.md) | Poker engine (`engine/`, `translation.py`, `ids.py`, `settings.py`) | 8 |
| [backend-api-oracle.md](backend-api-oracle.md) | FastAPI routes, oracle, prompts, DB tables | 25 |
| [frontend.md](frontend.md) | React components, routes, hooks, API client | 24 |
| [cross-cutting.md](cross-cutting.md) | Config, build, tests, migrations, docs, prompts | 18 |
| [priorities.md](priorities.md) | Consolidated high/medium-severity action plan | — |

## Total

75 findings across four areas. Skewed toward Low/Nit — the codebase is generally healthy. The concrete actionable issues cluster in:

1. **Observability gaps** — catch-all `except Exception` blocks that swallow errors without logging (sweeper, SSE finalization, prompt listing).
2. **Schema/type drift** — stringly-typed status fields; backend/frontend optionality mismatch on `Action.to_amount`.
3. **Dead scaffolding** — `@tanstack/react-query` provider wrapping the app but never used; a stale plan doc; deal_flop/turn/river helpers only used by tests.
4. **Visual inconsistency** — `routes/SpotAnalysis.tsx` uses inline styles + hex colors; rest of the app is Tailwind 4.
5. **Minor efficiency** — linear preset scan in `stream.py`, redundant float casts, missing module-level constants.

## How to consume

- Start with [priorities.md](priorities.md) for a ranked action plan.
- Each finding has: file:line, severity, category, problem, suggested change, and a **breaking risk** assessment with the test(s) that would catch a regression.
- None of the suggested changes are breaking when applied as written. Anything with breaking risk > Low is flagged explicitly.

## Caveats

- No runtime profiling — efficiency findings are from reading the code, not measurement.
- e2e tests in `frontend/e2e/` were skimmed, not deeply reviewed.
- Hypothesis shrinking behavior in engine invariant tests was not exercised.
- Some ADR "canary" references were not verified against current line numbers.
