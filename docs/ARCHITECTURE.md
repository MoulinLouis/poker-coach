# Architecture — orientation

This file is **where to look**, not what to know. Design rationale lives in
[`docs/plans/2026-04-18-poker-hu-llm-coach-design.md`](plans/2026-04-18-poker-hu-llm-coach-design.md).
Non-obvious decisions live in [`docs/decisions/`](decisions/README.md).
Session-level working notes live in [`CLAUDE.md`](../CLAUDE.md) at the repo
root.

## Topology

Local web app. React 18 + Vite + Tailwind 4 frontend → FastAPI backend →
SQLite for logging + filesystem for versioned prompts. Oracle abstraction
over Anthropic Messages and OpenAI Responses with a forced
`submit_advice` tool for structured output.

## Where things live

| Concern | Path | Notes |
|---|---|---|
| HU NLHE engine | `backend/src/poker_coach/engine/` | Immutable GameState; Hypothesis property tests |
| Oracle abstraction | `backend/src/poker_coach/oracle/` | `base.py` = protocol + events, `anthropic_oracle.py` / `openai_oracle.py` = impls |
| Model preset registry | `backend/src/poker_coach/oracle/presets.py` | One entry per UI selector option |
| Prompt renderer | `backend/src/poker_coach/prompts/` | Jinja2 + frontmatter, `StrictUndefined` |
| Prompt packs | `prompts/<pack>/<version>.md` | Git = history |
| Pricing + cost calc | `backend/src/poker_coach/oracle/pricing.py` + `config/pricing.yaml` | Snapshot saved with every decision |
| FastAPI app + routes | `backend/src/poker_coach/api/` | `app.py` is the factory; `routes/` is per-concern |
| Log schema | `backend/src/poker_coach/db/tables.py` + `db/migrations/` | Alembic from commit 1 |
| React app shell | `frontend/src/App.tsx` | 4-tab nav + CostFooter |
| Live Coach | `frontend/src/routes/LiveCoach.tsx` + `components/` | PokerTable, ActionBar, AdvicePanel, CardPicker, SetupPanel, HandSummary |
| SSE hook | `frontend/src/api/useAdviceStream.ts` | `@microsoft/fetch-event-source` |
| E2E tests | `frontend/e2e/` | Playwright; webServer spawns both servers |

## Decision lifecycle (one pass)

1. Frontend renders Live Coach, user clicks "advise" on hero's turn.
2. `POST /api/decisions` — backend validates inputs, renders prompt, writes an `in_flight` row, returns `decision_id`. **No oracle call yet.** ([ADR](decisions/2026-04-18-lazy-oracle-invocation.md))
3. Frontend opens SSE via `GET /api/decisions/{id}/stream`. Backend atomically claims the row (409 on double-open), invokes the provider-appropriate oracle, forwards `OracleEvent`s as SSE frames.
4. On terminal event, backend updates row with final status + parsed advice + tokens + cost.
5. Frontend renders advice card. Hero's actual click posts to `POST /api/actions` referencing `decision_id`; divergence from advice is logged and rolled up into session agreement rate.

## Component contracts

- `Oracle.advise_stream(RenderedPrompt, ModelSpec) -> AsyncIterator[OracleEvent]` — provider-agnostic. Events: `ReasoningDelta`, `ReasoningComplete`, `ToolCallComplete`, `UsageComplete`, `OracleError`.
- `apply_action(GameState, Action) -> GameState` — pure, raises `IllegalAction` on anything not in `legal_actions(state)`.
- `PromptRenderer.render(pack, version, variables) -> RenderedPrompt` — validates declared vs supplied vs referenced variables; fails closed.

## Testing map

| Layer | Where | What it guards |
|---|---|---|
| Engine properties | `backend/tests/engine/test_invariants.py` | 5 invariants over Hypothesis-generated play |
| Engine scenarios | `backend/tests/engine/test_rules.py` | Hand-picked edge cases (min-raise, all-in short, etc.) |
| Oracle normalization | `backend/tests/oracle/test_{anthropic,openai}_oracle.py` | Fake streams → OracleEvent sequence |
| Leak guard | `backend/tests/prompts/test_no_villain_leak.py` | Three-layer guarantee — do not skip |
| Migration round-trip | `backend/tests/db/test_migrations.py` | Upgrade → downgrade → upgrade |
| API lifecycle | `backend/tests/api/test_lifecycle.py` | Full create → stream → finalize, plus sweeper |
| Frontend unit | `frontend/src/components/*.test.tsx` | vitest + testing-library |
| E2E | `frontend/e2e/*.spec.ts` | Playwright happy paths (no LLM) |

## Commands

```
make install     # uv sync + npm install
make dev         # uvicorn :8000 + vite :5173
make test        # pytest + vitest
make lint        # ruff + mypy + eslint + tsc
make e2e         # playwright
make db-upgrade  # alembic upgrade head
```

## Where to go from here

- Adding a new model preset → `oracle/presets.py` + `config/pricing.yaml` + the right `thinking_mode` branch ([ADR](decisions/2026-04-18-anthropic-thinking-api-dispatch.md)).
- Adding a new prompt pack → new dir under `prompts/`, declare variables in frontmatter; `prompts/context.py` may need to expose new projected vars — check the leak guard still holds.
- Adding a new API endpoint → new module under `backend/src/poker_coach/api/routes/`, register in `app.py`, add pytest under `backend/tests/api/`.
- Debugging unexplained SDK behavior → step 1 is `mcp__context7__query-docs`, step 2 is a 10-line script against the real API with `.env` credentials, step 3 is an ADR in `docs/decisions/`.
