# Parallel Session Prompts

Four copy-paste prompts to execute the 12-commit cleanup from [priorities.md](priorities.md). Launch each session in its own terminal — they operate on isolated git worktrees and can run fully in parallel.

## How to use

1. Open 4 Claude Code sessions (or 4 terminals).
2. Paste the **Preamble** + **one** session prompt into each.
3. Each session creates its own worktree off `main`, commits atomically, and reports back.
4. After all sessions finish: review the branches, merge/rebase into `main` in any order (no conflicts expected across sessions; Session D's two commits are internally sequential).

---

## Preamble (paste at the top of every session)

> You have superpowers. Create a git worktree off `main` with the branch name given below; work entirely inside that worktree. Read `docs/reviews/2026-04-19-code-review/README.md` and `priorities.md` for context. Respect the "Don't touch" list from priorities.md: CardPicker uncontrolled pattern, OracleFactory Protocol, villain_profile conditional in prompts/context.py, ActionBar double-clamp. Run `make test` and `make lint` after each commit. Produce one atomic Conventional Commit per finding — do not batch unrelated changes into one commit. Stop if tests or lint fail; never bypass hooks with `--no-verify`. When finished, report the branch name and every commit hash produced.

---

## Session A — Easy cleanups

**Branch:** `chore/review-cleanup-a`

Produce 4 commits in order:

1. `chore(docs): archive translation-advice-fr plan`
   - `git mv docs/plans/2026-04-19-translate-advice-fr.md docs/plans/old/`
   - Reference: cross-cutting F-6.

2. `chore(frontend): remove unused react-query scaffolding`
   - Drop `@tanstack/react-query` from `frontend/package.json`.
   - Remove `QueryClientProvider` wrap + imports from `frontend/src/main.tsx`.
   - Re-run `npm install` in `frontend/` to refresh the lockfile.
   - Reference: cross-cutting F-4, F-5.

3. `refactor(engine): hoist _STREET_ORDER to module constant`
   - Define module-level `_STREET_ORDER: tuple[...]` in `backend/src/poker_coach/engine/rules.py`; use inside `_apply_street_transition`.
   - Replace the duplicate `STREET_ORDER` in `backend/tests/engine/test_invariants.py` with an import.
   - Reference: engine F-4, F-5.

4. `refactor(engine): raise IllegalAction instead of asserting min/max_to`
   - Replace the `assert la.min_to is not None and la.max_to is not None` at `engine/rules.py:377` with an explicit `raise IllegalAction("legal_actions invariant violated: min_to/max_to missing")`.
   - Reference: engine F-1.

---

## Session B — Backend API + oracle

**Branch:** `refactor/review-api-b`

Produce 4 commits in order:

1. `refactor(api): log silent exceptions in sweeper, SSE finalize, prompt listing`
   - Add `logger.exception(...)` (use an appropriate module logger) to the catch-all blocks at `backend/src/poker_coach/api/sweeper.py:79`, `backend/src/poker_coach/api/routes/stream.py:206`, and `backend/src/poker_coach/api/routes/prompts.py:74`.
   - Behavior must stay unchanged — only add logging.
   - Reference: backend-api F-5, F-12, F-13.

2. `refactor(oracle): O(1) preset lookup by (model_id, provider)`
   - In `backend/src/poker_coach/oracle/presets.py`, build module-level `PRESETS_BY_MODEL: dict[tuple[str, str], ModelSpec]`.
   - Replace the linear scan in `backend/src/poker_coach/api/routes/stream.py:60-64` with a dict lookup.
   - Reference: backend-api F-3.

3. `refactor(api): DecisionStatus literal and consolidate response models`
   - Add `DecisionStatus = Literal["in_flight", "ok", "invalid_response", "illegal_action", "provider_error", "cancelled", "abandoned", "timeout"]` in `backend/src/poker_coach/api/schemas.py`.
   - Retype `DecisionSummary.status` and `DecisionListRow.status` to `DecisionStatus`.
   - Move `DecisionDetail` from `backend/src/poker_coach/api/routes/decisions.py` into `schemas.py`; update imports.
   - Reference: backend-api F-1, F-2; cross-cutting F-16.

4. `refactor(api): atomic prompt save via temp-file + rename`
   - Replace the write/validate/unlink flow in `backend/src/poker_coach/api/routes/prompts.py:130-137` with: write to `target.with_suffix(target.suffix + ".tmp")`, validate (by rendering from the temp path or by parsing `body.content` directly), then `tmp.rename(target)` on success / `tmp.unlink(missing_ok=True)` on failure.
   - Reference: backend-api F-22.

---

## Session C — Frontend shared utils + AdvicePanel

**Branch:** `refactor/review-frontend-c`

Produce 2 commits in order:

1. `refactor(frontend): centralize parseHole and suit maps in utils/cards`
   - Create `frontend/src/utils/cards.ts` exporting `parseHole(input: string): [string, string] | null` and a single `SUITS` map (glyph + color).
   - Replace duplicates in: `routes/LiveCoach.tsx`, `routes/SpotAnalysis.tsx`, `components/SetupPanel.tsx`, `components/BoardPicker.tsx`, `components/CardPicker.tsx`.
   - Use `SUITS` in `components/PlayingCard.tsx` where it reduces local duplication.
   - Reference: frontend F-4, F-5.

2. `refactor(frontend): hoist useTranslation to AdvicePanel root`
   - Move the `useTranslation(...)` calls out of `ThinkingBlock` and `AdviceCard` (inside `components/AdvicePanel.tsx`) up into the `AdvicePanel` component itself.
   - Pass `displayedReasoning`, `loading`, `error`, and toggle callback down as props.
   - Preserve the `mountedRef` StrictMode guard inside `useTranslation`.
   - Verify `components/AdvicePanel.test.tsx` still passes.
   - Reference: frontend F-6.

---

## Session D — SpotAnalysis refactor

**Branch:** `refactor/review-spot-d`

Produce 2 commits in order (same file — must be sequential within this session):

1. `style(frontend): convert SpotAnalysis from inline styles to Tailwind`
   - Rewrite `frontend/src/routes/SpotAnalysis.tsx:173-367` replacing every `style={{...}}` and raw hex color with Tailwind 4 classes.
   - Match the visual language of `components/SetupPanel.tsx` (ring-1 ring-white/5, bg-stone-900, text-red-500 for errors, etc.).
   - No logic changes — pure visual refactor.
   - Reference: frontend F-1 (High severity).

2. `refactor(frontend): stabilize SpotAnalysis column hook count`
   - Refactor the `useColumn` call pattern so hook count is stable across preset toggles: allocate a fixed-size array of column slots, call `useColumn` unconditionally for each slot (with optional preset), and render slots conditionally.
   - Add a vitest in `frontend/src/routes/SpotAnalysis.test.tsx` (create if missing) that toggles presets in sequence and confirms no React hook-count error.
   - Reference: frontend F-8.

---

## Post-session checklist (for you, the operator)

After all 4 sessions finish:

- [ ] `git branch --list | grep review` — confirm 4 branches exist.
- [ ] Each session reported `make test` + `make lint` green for every commit.
- [ ] Review diffs: `git diff main...chore/review-cleanup-a`, etc.
- [ ] Merge/rebase into `main` — any order. No cross-session conflicts expected.
- [ ] `git worktree remove <path>` to clean up after merge.
