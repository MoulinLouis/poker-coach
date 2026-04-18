# Lazy oracle invocation + atomic SSE claim

## Context

Options for running the oracle during a decision lifecycle:

- Fire the provider call in `POST /api/decisions` and stream the result to the frontend — risks billing orphaned tabs when a user closes the page before reading.
- Defer everything to the SSE open — needs a two-step lifecycle.

## Decision

Two steps, lazy:

1. `POST /api/decisions` validates inputs, renders the prompt, inserts a row with `status="in_flight"`, returns `decision_id`. **No oracle call.**
2. `GET /api/decisions/{id}/stream` atomically claims the row (`UPDATE decisions SET stream_opened_at=NOW() WHERE id=? AND stream_opened_at IS NULL`; 0 rows → 409 Conflict). Only after a successful claim does the oracle fire.

A background sweeper transitions stale rows: `in_flight` without `stream_opened_at` after 30s → `status="abandoned"`; `in_flight` with `stream_opened_at > 3min ago` → `status="timeout"`.

## Rationale

- No paid oracle call for tabs that were closed before the stream opened.
- Atomic claim via `UPDATE ... WHERE stream_opened_at IS NULL` is race-free without explicit locking.
- Two status buckets (`abandoned` vs `timeout`) keeps the log honest about what happened.

## Canary

- Lifecycle e2e test `backend/tests/api/test_lifecycle.py::test_double_open_returns_409` proves the atomic claim.
- `test_sweeper_abandoned_and_timeout` proves the sweeper writes the right terminal status.
- If a `POST /api/decisions` implementation starts invoking the oracle directly, billing-per-tab-close regresses.

## Implementing commits

- `0bd28b5` — FastAPI app with routes + SSE + sweeper
- `c0d735c` — lifecycle e2e tests
