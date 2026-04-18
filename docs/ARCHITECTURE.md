# Architecture

Condensed, living reference. Source of truth for design rationale: [`docs/plans/2026-04-18-poker-hu-llm-coach-design.md`](plans/2026-04-18-poker-hu-llm-coach-design.md). This document is updated per-PR alongside the code it describes; do not let it rot.

## At a glance

- **Product:** Local web-based heads-up No-Limit Hold'em coach powered by LLMs. Two modes: live coach during face-to-face play, and spot analysis for post-hoc review.
- **Primary model:** `gpt-5.3-codex` via OpenAI Responses API with `reasoning_effort=xhigh`. Secondary: Claude Opus 4.7 (qualitative comparison) and Claude Haiku 4.5 (prompt exploration).
- **Stack:** Python 3.12 / FastAPI / SQLAlchemy Core / SQLite on the backend; React 18 / Vite / TypeScript / TanStack Query on the frontend. One process per side, orchestrated by `make dev`.
- **Transport:** HTTP + SSE. `POST /api/decisions` creates a row; `GET /api/decisions/{id}/stream` is where the oracle call actually fires. `@microsoft/fetch-event-source` on the frontend.

## Repo layout

```
backend/            Python package (engine, oracle, prompts, api, db)
frontend/           React app (Live Coach, Spot Analysis, History, Prompts, Settings)
prompts/<pack>/     Versioned .md prompt templates (git = history)
config/pricing.yaml Per-model pricing with snapshot_date + snapshot_source
data/               Gitignored SQLite file
docs/               ARCHITECTURE, PROMPTS, RESULTS, plans/
```

## Domain model (Section 2)

Immutable `GameState` snapshots. `apply_action(state, action) -> new_state`. Integer chips only (`bb=100` default); no floats. Both `rng_seed` and `deck_snapshot` populated for live coach hands — `deck_snapshot` is authoritative for replay. `legal_actions(state)` is a pure function the UI and the prompt both consume; `apply_action` raises on illegal input.

**phevaluator** for showdown winner + display label. Never exposed to the prompt — hand-strength reasoning belongs to the LLM.

HU specifics: SB is the button (preflop first, postflop last), no side pots, no multi-way. Uncalled-bet return handled on call resolution; standard NLHE min-raise reopening rule.

## Oracle abstraction (Section 3)

One `Oracle` protocol, two implementations (OpenAI Responses, Anthropic Messages). Returns an `AsyncIterator[OracleEvent]` — `ReasoningDelta`, `ReasoningComplete`, `ToolCallComplete`, `UsageComplete`, `OracleError`. Backend re-emits these as SSE frames.

Single forced tool `submit_advice` with schema `{action, to_amount_bb?, reasoning, confidence}`. Shared Pydantic schema; a ~30-line normalizer emits provider-specific JSON variants. Schema failures log `status="invalid_response"`; legality failures log `status="illegal_action"`. Never silently substituted.

`config/pricing.yaml` drives cost calculation. Reasoning/thinking tokens billed at output rate on both platforms. Each row carries its `pricing_snapshot` (rates + `snapshot_date` + `snapshot_source`) so historical costs survive future price changes.

## Log schema (Section 4)

Four tables: `sessions`, `hands`, `decisions`, `actual_actions`. `decisions` is the centerpiece — one row per LLM call, holding the full `game_state`, `template_raw`, `rendered_prompt`, model params, reasoning text, raw tool input, parsed advice, token usage, cost, `pricing_snapshot`, and `status`.

Key statuses: `in_flight`, `ok`, `invalid_response`, `illegal_action`, `provider_error`, `cancelled`, `abandoned`, `timeout`.

Decision lifecycle:

1. `POST /api/decisions` writes `status=in_flight` and returns `decision_id` without calling the oracle.
2. `GET /api/decisions/{id}/stream` atomically claims (`UPDATE … WHERE stream_opened_at IS NULL`; 0 rows → 409) and runs the oracle. This is where billing starts.
3. Background sweeper: `abandoned` at 30s without stream open, `timeout` at 3min without completion.

`actual_actions` is a separate table so agreement rate derives via JOIN and spot-analysis (no human action) is clean.

Alembic from commit 1. Template bodies stored denormalized per row until ~100k decisions.

## UI (Section 5)

Live Coach is keyboard-first: `f c k b r a` for actions (bet and raise split intentionally), street-aware size presets (`1–4` preflop, `1–5` postflop), `space` for advice, `esc` to cancel, `n` for new hand. Override is silent; divergence shows as an ambient indicator and rolls up into a session-end agreement rate.

Spot Analysis has a Compare mode powered by `useQueries` — fire N models in parallel, one column each.

Streaming UX mirrors Claude.ai: instant "Thinking…" → first token replaces indicator → tool call lands the advice card with a brief highlight.

## Testing (Section 6)

Engine: Hypothesis property tests for chip conservation, street monotonicity, `to_act` consistency, illegal-action unreachability, and replay idempotency. Oracle: snapshot tests on provider schema emission + recorded-fixture replay. API: pytest-asyncio over the full lifecycle. Frontend: Vitest + one Playwright happy path.

## Non-goals

No bot play, no GTO benchmark, no websockets, no multi-table, no tournaments, no ICM, no auth, no auto-villain. Everything else in the design doc.
