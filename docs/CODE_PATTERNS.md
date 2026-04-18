<!-- Last verified against code: 2026-04-18 -->
# Code Patterns

Task-indexed. Find the row that matches what you're about to do, follow the
steps, then run the listed tests.

## When adding a…

| Task | Read + touch | Canary tests |
|---|---|---|
| **Model preset** (new selector option) | [§ Add a model preset](#add-a-model-preset) | `backend/tests/oracle/test_presets.py`, `backend/tests/oracle/test_pricing.py` |
| **Prompt pack / version** | [§ Add a prompt pack](#add-a-prompt-pack) | `backend/tests/prompts/test_renderer.py`, `backend/tests/prompts/test_no_villain_leak.py` |
| **API route** | [§ Add an API route](#add-an-api-route) | Route-specific test under `backend/tests/api/` |
| **Engine action type or rule change** | [§ Change the engine](#change-the-engine) | `backend/tests/engine/test_invariants.py`, `backend/tests/engine/test_rules.py` |
| **Oracle event / provider tweak** | [§ Touch oracle normalization](#touch-oracle-normalization) | `backend/tests/oracle/test_{anthropic,openai}_oracle.py` |
| **DB column / table** | [§ Add a migration](#add-a-migration) | `backend/tests/db/test_migrations.py` |
| **React component** | [§ Add a React component](#add-a-react-component) | colocated `*.test.tsx`, plus Playwright spec if user-visible |
| **Load-bearing non-obvious decision** | [§ Record an ADR](#record-an-adr) | Canary block inside the ADR itself |

---

## Add a model preset

Entry: [`backend/src/poker_coach/oracle/presets.py`](../backend/src/poker_coach/oracle/presets.py).

One `ModelSpec` per UI selector option — deliberately a flat registry, not a
model×effort matrix.

1. Add an entry to `MODEL_PRESETS`. Pick the right `thinking_mode` for
   Anthropic: `"adaptive"` for Opus 4.7, `"enabled"` + `thinking_budget` for
   Sonnet 4.6 / Haiku 4.5, omitted for OpenAI. See
   [`decisions/2026-04-18-anthropic-thinking-api-dispatch.md`](decisions/2026-04-18-anthropic-thinking-api-dispatch.md).
2. If the model has a new id, add a row in
   [`config/pricing.yaml`](../config/pricing.yaml) with `input_per_mtok`,
   `output_per_mtok`, `cache_read_per_mtok`, `snapshot_date`, `snapshot_source`.
   Every decision row captures the snapshot, so past cost calculations stay
   stable across price updates.
3. If this should become the default, update `DEFAULT_PRESET_ID` **and**
   the `Current model strategy` section of [`../CLAUDE.md`](../CLAUDE.md).

Do NOT guess at provider param shapes. Run `mcp__context7__query-docs` or a
10-line real-API script first. [ADR](decisions/2026-04-18-anthropic-thinking-api-dispatch.md).

---

## Add a prompt pack

1. Create `prompts/<pack>/<version>.md` with YAML frontmatter:
   `name`, `version`, `description`, `variables` (list of Jinja2 vars you
   reference).
2. Body is Jinja2 under `StrictUndefined`. Every `{{ var }}` in the body
   must appear in the `variables` frontmatter, or render fails closed.
3. If the pack needs new projected vars, extend
   [`backend/src/poker_coach/prompts/context.py`](../backend/src/poker_coach/prompts/context.py).
   **Leak guard: do not expose `villain_hole` or `deck_snapshot[4:9]`.**
   Three tests block this:
   `backend/tests/prompts/test_no_villain_leak.py`.
   [ADR](decisions/2026-04-18-villain-leak-guard.md).
4. Bump the version in the filename — don't rewrite in place. Git + the
   `template_hash` stored on each decision row are how we trace which
   wording produced which output.
5. Document the pack in [`PROMPTS.md`](PROMPTS.md).

---

## Add an API route

Entry: [`backend/src/poker_coach/api/app.py`](../backend/src/poker_coach/api/app.py).

1. New module under `backend/src/poker_coach/api/routes/`. Export a
   `router = APIRouter()`.
2. Register in `app.py` via `app.include_router(yours.router, prefix="/api")`.
3. Dependencies resolve off `app.state`: engine, pricing, oracle_factory,
   prompts_root are all set in the `lifespan`. Keep route modules
   constructor-free — they should read from `request.app.state` (or the
   existing `Depends` helpers in [`api/deps.py`](../backend/src/poker_coach/api/deps.py)).
4. Add tests under `backend/tests/api/` using the `test_app_builder`
   fixture from [`backend/tests/conftest.py`](../backend/tests/conftest.py).
   Use `FakeOracleFactory` (from `test_lifecycle.py`) for anything
   downstream of the oracle.

Decision-lifecycle routes (`/decisions`, `/decisions/{id}/stream`) have
careful lazy semantics — do not rewrite them without reading
[ADR: lazy oracle invocation](decisions/2026-04-18-lazy-oracle-invocation.md).

---

## Change the engine

Entry: [`backend/src/poker_coach/engine/rules.py`](../backend/src/poker_coach/engine/rules.py).

**Integer chips only.** 1 bb = 100 chips. No floats in engine math. Display
layer (`prompts/context.py`, React) divides.

The 6 invariants in [`../CLAUDE.md`](../CLAUDE.md) are property-tested in
`backend/tests/engine/test_invariants.py`. All must stay green.

- New action type → add to `Action` union in `models.py`, `legal_actions`,
  `apply_action`. Any action not returned by `legal_actions(state)` must
  raise `IllegalAction` — tested.
- Street transition → goes through `pending_reveal`, not auto-deal.
  Hand progresses only after `apply_reveal` consumes the reveal. See
  [ADR: integer chips + deck_snapshot](decisions/2026-04-18-integer-chips-deck-snapshot.md).
- Replay code: use `replay(state)` from `engine/rules.py`, not
  `reduce(apply_action, ...)`. The latter breaks at `pending_reveal`
  boundaries because it doesn't interleave `apply_reveal`.
- `GameState` round-trips: always `model_dump(mode="json")`.
  `acted_this_street` is a `frozenset` — default dump crashes the
  JSON column write.

---

## Touch oracle normalization

Entry: [`backend/src/poker_coach/oracle/base.py`](../backend/src/poker_coach/oracle/base.py).

- The `Oracle.advise_stream(...)` contract is provider-agnostic. Events:
  `ReasoningDelta`, `ReasoningComplete`, `ToolCallComplete`,
  `UsageComplete`, `OracleError`. If you add an event type, every
  provider impl must emit or ignore it consistently.
- Fake SDK streams in tests must mirror real async-ness.
  `get_final_message()` and `get_final_response()` are `async` — awaits
  are required. [ADR: async stream await](decisions/2026-04-18-async-stream-await.md).
- Don't force `tool_choice` when Anthropic thinking is enabled — the API
  400s. Rely on a forceful system prompt instead. Haiku (no thinking)
  can still force. [ADR](decisions/2026-04-18-anthropic-tool-choice-with-thinking.md).
- On provider error: retry once on 5xx / rate limit, then hard fail.
  **Never** return a different model's response as fallback — corrupts
  research data.

---

## Add a migration

1. `cd backend && uv run alembic revision -m "describe change"` — generates
   a file under `backend/src/poker_coach/db/migrations/versions/`.
2. Write `upgrade()` **and** `downgrade()`. The migration round-trip test
   at `backend/tests/db/test_migrations.py` runs upgrade → downgrade →
   upgrade and will fail the build if downgrade is wrong.
3. If you're adding a column the coach or decisions code reads, update
   [`backend/src/poker_coach/db/tables.py`](../backend/src/poker_coach/db/tables.py).
4. `make db-upgrade` to apply locally.

---

## Add a React component

Entry: [`frontend/src/components/`](../frontend/src/components/).

- Colocate `Component.tsx` + `Component.test.tsx` (vitest +
  testing-library). Playwright e2e under `frontend/e2e/`.
- The SSE hook is [`frontend/src/api/useAdviceStream.ts`](../frontend/src/api/useAdviceStream.ts)
  — use it, don't roll a second streaming path.
- API types live in [`frontend/src/api/types.ts`](../frontend/src/api/types.ts).
  Keep them in sync with the Pydantic models.
- For cards / hands UI, `CardPicker` is **uncontrolled** — parent passes a
  fresh `key` to force reset, never a prop-syncing `useEffect`.
  [ADR](decisions/2026-04-18-cardpicker-uncontrolled.md).

---

## Record an ADR

When a decision took nontrivial debugging to land and rediscovering it
would cost future sessions time:

1. Add `docs/decisions/YYYY-MM-DD-<slug>.md`.
2. Sections: **Context · Decision · Rationale · Canary · Implementing commit(s)**.
   The **Canary** is the test name or grep pattern that flips if the
   assumption behind the decision breaks.
3. Add the entry to [`decisions/README.md`](decisions/README.md).
4. If the decision contradicts the design plan, link back to the plan
   section being overridden — leave the plan as historical.

Do not update an ADR in place once merged. If the decision is reversed,
write a new ADR that supersedes it.
