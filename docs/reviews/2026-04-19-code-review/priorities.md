# Priorities — Action Plan

Consolidated, ranked list of findings across all four reviews. None of these are breaking changes when applied as written. Anything touching a CLAUDE.md invariant is flagged explicitly.

## Severity summary

| Severity | Count |
|---|---|
| High | 1 |
| Medium | 6 |
| Low | 40 |
| Nit | 28 |
| **Total** | **75** |

## High priority (do first)

### 1. Convert `SpotAnalysis` to Tailwind
- **Finding:** [frontend F-1](frontend.md#f-1-spotanalysis-uses-inline-styles-instead-of-tailwind)
- **File:** `frontend/src/routes/SpotAnalysis.tsx:173-367`
- **Why it's highest:** Visible visual inconsistency; entire route diverges from Tailwind 4 used everywhere else.
- **Effort:** One focused commit. No test impact.

## Medium priority (next batch)

### 2. Add observability to silent `except` blocks
Three catch-alls swallow errors with zero logging:
- [backend-api F-13](backend-api-oracle.md#f-13-sweeper-errors-silently-suppressed) — `sweeper.py:79`
- [backend-api F-12](backend-api-oracle.md#f-12-contextlibsuppressexception-on-sse-error-emit-path) — `stream.py:206`
- [backend-api F-5](backend-api-oracle.md#f-5-malformed-prompt-frontmatter-silently-yields-a-half-populated-list-entry) — `prompts.py:74`

Each is a one-line `logger.exception(...)` fix. No behavior change, major observability win.

### 3. Replace production `assert` with explicit raise
- **Finding:** [engine F-1](backend-engine.md#f-1-assertion-in-production-code-should-be-explicit-error)
- **File:** `engine/rules.py:377`
- **Why:** `python -O` silently bypasses assertions; this guards chip-math correctness.

### 4. Delete unused `@tanstack/react-query` scaffolding
- **Findings:** [cross-cutting F-4](cross-cutting.md#f-4-tanstackreact-query-dependency-is-unused), [F-5](cross-cutting.md#f-5-queryclientprovider--same-scaffolding-as-f-4)
- **Files:** `frontend/package.json:18`, `frontend/src/main.tsx`
- **Why:** Real dead code; removing it clarifies the actual data-flow model.

### 5. Archive completed translation plan
- **Finding:** [cross-cutting F-6](cross-cutting.md#f-6-completed-translation-plan-still-in-docsplans-not-docsplansold)
- **Command:** `git mv docs/plans/2026-04-19-translate-advice-fr.md docs/plans/old/`
- **Why:** Future sessions will misread in-flight status.

### 6. Harden prompt save (TOCTOU)
- **Finding:** [backend-api F-22](backend-api-oracle.md#f-22-prompt-save-writevalidateunlink-has-a-toctou-window)
- **File:** `prompts.py:130-137`
- **Why:** Between write and unlink, a concurrent reader sees the invalid file. Single-user local MVP, so the risk is small but the fix is free.

### 7. Stabilize `SpotAnalysis` column hook pattern
- **Finding:** [frontend F-8](frontend.md#f-8-spotanalysis-remounts-usecolumn-hooks-on-every-preset-toggle)
- **File:** `routes/SpotAnalysis.tsx:71-74`
- **Why:** Violates rules-of-hooks stability; one bad state-branch would crash the route. Add a test alongside the fix.

## Low-priority cleanups (batch when convenient)

### Type safety and schema drift
- [backend-api F-1/F-2](backend-api-oracle.md#f-1-stringly-typed-decision-status-in-schemas) — `DecisionStatus` Literal.
- [cross-cutting F-2](cross-cutting.md#f-2-actionto_amount-optionality-mismatch-between-backend-and-frontend) — `Action.to_amount` optional-vs-nullable.
- [backend-api F-25](backend-api-oracle.md#f-25-extraallow-on-decisionsummary-hides-schema-drift) — tighten `extra="allow"`.

### Duplication
- [frontend F-4](frontend.md#f-4-parsehole-duplicated-in-3-places) — consolidate `parseHole`.
- [frontend F-5](frontend.md#f-5-suit-glyphs--colors-duplicated-between-boardpicker-and-cardpicker) — consolidate suit glyph/color maps.
- [frontend F-6](frontend.md#f-6-advicepanel-spins-up-two-independent-translation-hooks) — hoist `useTranslation` in `AdvicePanel`.
- [frontend F-15](frontend.md#f-15-agreement-rate-formula-duplicated) — extract `agreementPct`.
- [backend-api F-6](backend-api-oracle.md#f-6-reasoning-assembly-pattern-duplicated-across-oracles) — share post-stream reasoning assembly.

### Minor efficiency
- [engine F-4](backend-engine.md#f-4-street_order-list-re-allocated-on-every-street-transition) — hoist `_STREET_ORDER` to module level.
- [backend-api F-3](backend-api-oracle.md#f-3-linear-preset-lookup-in-streampy) — build `PRESETS_BY_MODEL` index.
- [backend-api F-15](backend-api-oracle.md#f-15-system-prompt-hash-re-computed-on-every-decision-create) — compute `SYSTEM_PROMPT_HASH` at import.
- [frontend F-3](frontend.md#f-3-costfooter-polling-never-backs-off-on-failure) — `CostFooter` backoff on failure.

### Dead code
- [engine F-3](backend-engine.md#f-3-unused-deck-helpers-deal_flop--deal_turn--deal_river) — delete `deal_flop`/`deal_turn`/`deal_river`.

### Observability
- [frontend F-11](frontend.md#f-11-stream-parse-errors-logged-as-parse-error-stringerr) — richer `useAdviceStream` parse-error logging.
- [cross-cutting F-1](cross-cutting.md#f-1-adr-implementation-canaries-not-updated-after-commit) — update ADR canaries.
- [backend-api F-7](backend-api-oracle.md#f-7-undocumented-fallback-for-openai-reasoning_tokens-field) — comment OpenAI reasoning-tokens fallback.

## Nits (stash for a rainy day)

Everything else — formatting, single-use constants, redundant casts, style consistency. See individual review files. Only worth touching if you're already in the file.

## Don't touch (flagged but load-bearing)

- `CardPicker` uncontrolled pattern — intentional, documented.
- `OracleFactory` Protocol — load-bearing for `FakeOracleFactory` in tests.
- `villain_profile` conditional in `context.py` — required by v1/v2 split invariant.
- `ActionBar` double-clamp — tests assert both layers.

## Suggested commit sequence

If you want a single session's worth of clean-up commits (each a separate `feat:`/`refactor:`/`docs:`/`chore:` per CLAUDE.md conventions):

1. `chore(docs): archive completed translation plan` — F-6
2. `chore(frontend): remove unused react-query scaffolding` — F-4/F-5
3. `refactor(engine): hoist _STREET_ORDER to module constant` — engine F-4/F-5
4. `refactor(engine): replace production assert with explicit IllegalAction` — engine F-1
5. `refactor(api): add logger.exception to sweeper and SSE error paths` — backend-api F-12/F-13
6. `refactor(api): index MODEL_PRESETS by (model_id, provider) for O(1) lookup` — backend-api F-3
7. `refactor(api): DecisionStatus Literal + DecisionDetail moved to schemas` — backend-api F-1, cross-cutting F-16
8. `refactor(frontend): extract parseHole + suit maps to utils/cards` — frontend F-4/F-5
9. `refactor(frontend): hoist useTranslation call up to AdvicePanel` — frontend F-6
10. `refactor(frontend): convert SpotAnalysis to Tailwind 4` — frontend F-1
11. `refactor(api): prompt save via temp-file + atomic rename` — backend-api F-22
12. `refactor(frontend): stabilize SpotAnalysis column hook count` — frontend F-8

Each commit is reviewable in isolation and reverts cleanly. None break public contracts.
