# Cross-cutting Review

## Scope

Config (`Makefile`, `pyproject.toml`, `frontend/package.json`, Vite/Playwright configs, pre-commit, CI, `.env.example`, `config/pricing.yaml`), migrations, shared test infra, frontend type definitions, docs (ARCHITECTURE, decisions, plans, README, AGENTS), and coach prompt markdown.

Top themes:
1. **Stale scaffolding** — `@tanstack/react-query` wired up but unused; a completed plan doc still marked in-progress.
2. **Schema drift** — `Action.to_amount` optional-vs-nullable mismatch between backend and frontend types.
3. **Documentation drift** — one ADR's implementation canary still `<pending>` after the commit landed.

---

### [F-1] ADR implementation canaries not updated after commit
- **File:** `docs/decisions/2026-04-19-anthropic-prompt-caching.md:32-35`
- **Severity:** Low
- **Category:** docs
- **Problem:** The "Implementing commits" section is still `<pending>`, but commits `df1a108` (enable prompt caching) and `4be006c` (enrich system prompt) shipped the change.
- **Suggested change:** Replace `<pending>` with the two hashes. Update the canary file/line refs if they've drifted.
- **Breaking risk:** None.

---

### [F-2] `Action.to_amount` optionality mismatch between backend and frontend
- **File:** `frontend/src/api/types.ts:15-19` vs `backend/src/poker_coach/engine/models.py:10-22`
- **Severity:** Low
- **Category:** drift
- **Problem:** Backend `Action` has `to_amount: int | None = None` — required field, nullable value. Frontend types it as `to_amount?: number | null` — optional field. Runtime behavior is fine (callers null-check), but stricter consumers will flag the inconsistency.
- **Suggested change:** In `frontend/src/api/types.ts`, change to `to_amount: number | null` (drop the `?`). Matches the wire format exactly.
- **Breaking risk:** Low — TypeScript compile change only. Call sites already handle `null`; the difference between "absent" and "null" is not observed in this codebase.

---

### [F-3] Redundant Vite port config
- **File:** `frontend/vite.config.ts:8`
- **Severity:** Nit
- **Category:** config
- **Problem:** `server.port: 5173` is Vite's default. Unnecessary clutter.
- **Suggested change:** Delete the line. Keep only `server.proxy`.
- **Breaking risk:** None.

---

### [F-4] `@tanstack/react-query` dependency is unused
- **File:** `frontend/package.json:18` + `frontend/src/main.tsx:1-4, 27-29`
- **Severity:** Low
- **Category:** dead-code
- **Problem:** `QueryClientProvider` wraps the app but no component calls `useQuery` / `useMutation`. The hooks in `api/` use plain `fetch` + manual state (`useTranslation`, `useAdviceStream`). Pure scaffolding.
- **Suggested change:** Remove the dependency from `package.json` and delete the provider wrap in `main.tsx`. If reintroduced later, the install is one command. Alternatively, leave if there's a concrete near-term plan to migrate `useAdviceStream` — but document that plan in a README.
- **Breaking risk:** None — grep confirms no imports beyond `main.tsx`.

---

### [F-5] `QueryClientProvider` — same scaffolding as F-4
- **File:** `frontend/src/main.tsx:1-4, 27-29`
- **Severity:** Nit
- **Category:** dead-code
- **Problem:** The provider wrap is the concrete expression of F-4.
- **Suggested change:** Remove alongside F-4.
- **Breaking risk:** None.

---

### [F-6] Completed translation plan still in `docs/plans/` not `docs/plans/old/`
- **File:** `docs/plans/2026-04-19-translate-advice-fr.md`
- **Severity:** Medium
- **Category:** docs
- **Problem:** Plan is still top-level but commits `ab568d1`, `6776e8c`, `26ec1c9`, `611acc5`, `ba133f8` show the feature shipped. Future Claude sessions will read this and think translation work is open.
- **Suggested change:** `git mv docs/plans/2026-04-19-translate-advice-fr.md docs/plans/old/`. Optionally add a single-line `## Status: shipped YYYY-MM-DD` at the top before the move.
- **Breaking risk:** None.

---

### [F-7] `ConfigDict(extra="allow")` on `DecisionSummary`
- **File:** `backend/src/poker_coach/api/schemas.py:62-68`
- **Severity:** Low
- **Category:** config
- **Problem:** Same as backend-api F-25. Repeated here because it has cross-cutting implications for type-safety contracts with the frontend.
- **Suggested change:** See `backend-api-oracle.md` F-25.
- **Breaking risk:** Low.

---

### [F-8] Pre-commit and CI run the same lint suite
- **File:** `.pre-commit-config.yaml` + `.github/workflows/ci.yml`
- **Severity:** Nit
- **Category:** config
- **Problem:** Pre-commit and CI both run `ruff check`, `ruff format --check`, `mypy`, `eslint`, `tsc`, `pytest`, `npm test`. By design, but rule changes require edits in both places.
- **Suggested change:** Leave as-is. Optional: extract the shared command list into a `Makefile` target (`make lint`) that both hooks call. That way there's one source of truth.
- **Breaking risk:** None.

---

### [F-9] `system_prompt_hash` column has no index
- **File:** `backend/src/poker_coach/db/migrations/versions/20260418_0002_log_schema.py:92-97` (and `0003`)
- **Severity:** Low
- **Category:** migrations
- **Problem:** `system_prompt_hash` is stored but no index. Today, no route filters by it, so no table scan occurs.
- **Suggested change:** Defer. Add an index only when a query actually filters by hash (e.g., "decisions that used system_prompt v2"). Premature indexes waste write cost.
- **Breaking risk:** None.

---

### [F-10] No test for `/api/decisions/{id}/detail` endpoint
- **File:** `backend/tests/api/test_lifecycle.py`
- **Severity:** Low
- **Category:** tests
- **Problem:** The detail endpoint (populates the live-coach detail view) has no automated coverage. A refactor could silently break the response shape.
- **Suggested change:** Add one test: create a decision via `POST`, open the stream, wait for completion via the fake oracle, then `GET /api/decisions/{id}/detail` and assert the contained fields (`game_state`, `template_raw`, `reasoning_text`, `system_prompt`, etc.) are populated. Follow the existing lifecycle test's pattern.
- **Breaking risk:** None — additive test.

---

### [F-11] Makefile comment doesn't reflect Vite fallback-port behavior
- **File:** `Makefile:13`
- **Severity:** Nit
- **Category:** docs
- **Problem:** Comment says `vite :5173`. If :5173 is busy, Vite auto-binds :5174.
- **Suggested change:** Either document the fallback or set `strictPort: true` in `vite.config.ts` to fail loudly on port conflict.
- **Breaking risk:** Low if `strictPort: true` is added — breaks the muscle memory for "run two devs locally". Skip unless it's caused a real mix-up.

---

### [F-12] `villain_profile` variable flow is already enforced
- **File:** `prompts/coach/v2.md:5, 33` + `backend/src/poker_coach/api/routes/decisions.py:84`
- **Severity:** N/A
- **Category:** note
- **Problem:** Investigated whether v2 prompt usage can forget to pass `villain_profile`. Confirmed it's enforced at the route level (conditional on `prompt_version == "v2"`).
- **Suggested change:** None. Add a pytest in `tests/prompts/` that asserts the v2 prompt renders iff `villain_profile` is passed, to cement the contract.
- **Breaking risk:** None — purely an optional new test.

---

### [F-13] `SYSTEM_PROMPT` has no version marker embedded
- **File:** `backend/src/poker_coach/oracle/system_prompt.py:1-12` + `decisions.py:92-93`
- **Severity:** Low
- **Category:** config
- **Problem:** The system prompt snapshot is persisted per decision (good for replay), but there's no inline version or date. Grouping decisions "by system_prompt version" requires post-hoc hash grouping.
- **Suggested change:** Add a module-level constant `SYSTEM_PROMPT_VERSION = "2026-04-19"` and persist it on each decision. Bump on every edit. Cheaper than hashing for analysis queries.
- **Breaking risk:** Low — adds a column (new migration) and a constant. Migrate existing rows with a backfill to a sentinel like `"pre-versioning"`.

---

### [F-14] Playwright e2e not run in CI
- **File:** `.github/workflows/ci.yml:42-43`
- **Severity:** Low
- **Category:** tests
- **Problem:** `make e2e` exists but CI doesn't invoke it. Intentional for MVP.
- **Suggested change:** Document in CLAUDE.md that e2e is local-only until Phase 4. Or add a nightly CI workflow that runs e2e against a built artifact.
- **Breaking risk:** None unless added — adding e2e to main CI slows every PR by ~30s+.

---

### [F-15] `game_state` is both persisted raw and projected for prompt — different purposes
- **File:** `backend/src/poker_coach/api/routes/decisions.py:115` vs `backend/src/poker_coach/prompts/context.py:26-63`
- **Severity:** Low
- **Category:** duplication
- **Problem:** Investigated whether the two touch-points duplicate logic. They don't: one persists the full state for replay (`model_dump(mode="json")`); the other strips villain info for the prompt. Names and intent are different.
- **Suggested change:** Add a docstring in `context.py` reminding the reader that this is the *filtered* projection (villain info stripped) — distinct from the raw decision row's `game_state`. Guards against future regressions.
- **Breaking risk:** None — comment only.

---

### [F-16] `DecisionDetail` class lives in `routes/decisions.py` while `DecisionSummary` is in `schemas.py`
- **File:** `backend/src/poker_coach/api/routes/decisions.py:47`
- **Severity:** Nit
- **Category:** polish
- **Problem:** Inconsistent placement of response models — most are in `schemas.py`, but this one hides in the route file.
- **Suggested change:** Move `DecisionDetail` to `schemas.py`, update imports. Keep `DecisionListRow` in `schemas.py` if it's already there.
- **Breaking risk:** None — internal module restructure.

---

### [F-17] Test client imports real module + mocks one function
- **File:** `frontend/src/api/useTranslation.test.ts:4`
- **Severity:** Nit
- **Category:** tests
- **Problem:** Mocking `translateText` directly on the imported module works but is sensitive to rename. No action needed.
- **Suggested change:** Leave. A typed mock factory is overkill here.
- **Breaking risk:** None.

---

### [F-18] `_DummyOracle` uses unreachable `if False: yield None` to become an async generator
- **File:** `backend/tests/conftest.py:26-30`
- **Severity:** Low
- **Category:** tests
- **Problem:** Unusual pattern — unreachable yield to satisfy the async generator contract before `raise RuntimeError`.
- **Suggested change:** Replace with an explicit `return` after `raise` is never reached — or, cleaner, drop the fake yield and just use:
  ```python
  async def advise_stream(self, *_, **__):
      raise RuntimeError("FakeOracle was called in a test that did not expect to invoke it")
      yield  # make this an async generator (unreachable)
  ```
  Add a comment explaining the yield is syntactic for type detection. Or switch to a proper async generator that yields once then errors — whichever matches how the test uses it.
- **Breaking risk:** None — purely clarifying a confusing construct.

---

## Confidence and caveats

- Most findings are small polish; only F-6 (stale plan) and F-2 (type drift) affect correctness of developer experience.
- The CLAUDE.md gotchas list was spot-checked against code — all still load-bearing.
- Did not verify ADR canary line numbers; F-1's "update the hashes" recommendation assumes the listed canary files still exist at the same lines.
- Only static inspection; tests were not executed.
