# Poker HU LLM Coach — Claude working notes

Local HU NLHE poker coach. Frontend (React + Vite + Tailwind 4) talks to a FastAPI backend that orchestrates prompt rendering + LLM streaming via an oracle abstraction over Anthropic Messages and OpenAI Responses. Logs every decision to SQLite for replay and research.

## Current model strategy

Overrides the original design doc. Default preset: **`gpt-5.3-codex-xhigh`** (OpenAI primary). Claude is secondary for qualitative comparison. Haiku 4.5 is the fast/cheap exploration path. See `MODEL_PRESETS` in `backend/src/poker_coach/oracle/presets.py`.

## Run

```sh
make install        # uv sync + npm install
make dev            # backend :8000 + vite :5173
make test           # pytest + vitest
make lint           # ruff+format+mypy-strict + eslint+tsc
make e2e            # playwright (needs servers)
make db-upgrade     # alembic upgrade head
```

API keys in `.env` at repo root: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`. Missing keys cause lazy `RuntimeError` at dispatch, not startup.

## Load-bearing gotchas

**These bit me hard and aren't obvious from the code — check first.**
Each one has a full ADR under [`docs/decisions/`](docs/decisions/README.md)
with canaries + linked commits. Skim the index before reinventing a fix.

1. **Async stream final-message methods must be `await`ed.** Both SDKs:
   - `message = await stream.get_final_message()` (Anthropic)
   - `response = await stream.get_final_response()` (OpenAI)
   Without `await`, you get a coroutine object whose `.content` silently defaults to empty → every call errors "no tool_use in response". The unit-test fakes must also use async methods or the bug hides.

2. **Anthropic tool_choice rules with thinking:**
   - `thinking={"type":"enabled","budget_tokens":N}` **rejects** `tool_choice="any"` / `{"type":"tool"}`. Use `tool_choice={"type":"auto"}` + a forceful system prompt. Models without thinking (Haiku preset) can force the tool.
   - `max_tokens` must be **strictly greater** than `thinking.budget_tokens`.
   - Opus 4.7 needs `thinking={"type":"adaptive"}` + `output_config={"effort":"high"}`. The legacy `enabled` form 400s on Opus 4.7 but is still required for Sonnet 4.6 / Haiku 4.5 → dispatch on `spec.thinking_mode`.

3. **Villain hole cards must never reach the LLM.** Three-layer guarantee in `prompts/context.py` + `prompts/coach/v1.md` declared variables + Jinja2 `StrictUndefined`. Any change touching these is gated by `backend/tests/prompts/test_no_villain_leak.py`. Do not weaken.

4. **GameState round-trips must use `model_dump(mode="json")`.** `acted_this_street` is a `frozenset` — default `model_dump` leaves it as `frozenset`, which crashes the JSON column write. The decisions route converts; frontend `engineApply` passes the state we gave it, which came from the backend in JSON mode.

5. **Decision lifecycle is lazy.** `POST /api/decisions` writes an `in_flight` row and returns; no oracle call happens. The oracle fires only when `GET /api/decisions/{id}/stream` atomically claims the row (`UPDATE ... WHERE stream_opened_at IS NULL` → 409 on double-open). This prevents billing orphaned tabs. Sweeper transitions `in_flight` → `abandoned` (30s, no stream) or `timeout` (3min, stream open).

6. **CardPicker is uncontrolled.** The parent's `[string, string] | null` prop can't encode "one slot filled, one empty", so the picker owns slot state locally. If you need a forced reset from the parent, pass a new `key` — do NOT add a prop-syncing `useEffect`.

7. **`deck_snapshot` is rewritten by `/engine/reveal` to reflect user-supplied board cards.** Any code reading `deck_snapshot[4:9]` for anything other than replay reconstruction must read `state.board` instead. Treat `deck_snapshot` positions beyond `[0:4]` (hero + villain holes) as implementation detail of replay, not a reliable source of board cards.

8. **Anthropic system prompt is cacheable; don't trim it.** `system=` is sent as `[{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}]` to cache the tools+system prefix. Anthropic requires >= 1024 tokens (2048 on Haiku) or caching is a silent no-op. Current `SYSTEM_PROMPT` is ~1140 tokens — trimming it below ~1100 kills the cache. `compute_cost` bills cache-write at 1.25x and cache-read at 0.1x the base input rate; changing these multipliers must follow Anthropic's published rates.

## Engine invariants (don't break)

Property tested in `backend/tests/engine/test_invariants.py`. All five must stay green:

1. Chip conservation: `sum(stacks) + pot + sum(committed)` is constant.
2. Street monotonicity: only advances forward.
3. `to_act` consistency: `to_act` is set iff the hand is in progress **AND** `pending_reveal is None`. When `pending_reveal is not None`, `to_act is None` and `legal_actions(state) == []`. Hand progresses only after `apply_reveal` consumes the pending cards.
4. Illegal-action unreachability: anything not in `legal_actions(state)` raises `IllegalAction`.
5. Replay idempotency: use `replay(state)` from `engine.rules` — NOT `reduce(apply_action, ...)`, which breaks at `pending_reveal` boundaries. `replay()` interleaves `apply_action` and `apply_reveal` using `state.reveals`.
6. Deck snapshot board consistency: `deck_snapshot[4 : 4 + len(board)] == board` for every state where `deck_snapshot is not None`.

**Integer chips only.** `bb=100` means 100 chips per BB. No floats in engine math. Display layer divides.

**`deck_snapshot` is authoritative for replay, not `rng_seed`.** Seeds are fragile across Python/RNG versions.

## Test infrastructure

- `backend/tests/conftest.py`: `migrated_engine` (throwaway SQLite + full Alembic upgrade), `sample_pricing`, `test_app_builder(factory)` to build FastAPI apps with fake oracle factories, `api_app` fixture for tests not needing a real oracle.
- Fake oracles: `FakeOracle`/`FakeOracleFactory` in `tests/api/test_lifecycle.py` — take a pre-built list of `OracleEvent` and yield them in order. Use this pattern when testing anything downstream of the oracle.
- Playwright `webServer` spawns uvicorn + vite; `reuseExistingServer: !CI`. No LLM calls in e2e (fake oracle not wired in prod server, so tests stay on engine-path).
- When adding SDK mocks, check whether the real SDK method is `async` — mirror it in the fake or the await pattern masks bugs.

## Project layout signals

- `prompts/<pack>/<version>.md`: YAML frontmatter (`name`, `version`, `description`, `variables` list) + Jinja2 body. Renderer enforces declared-variable invariant with `StrictUndefined`. Git history = prompt history; commits stay manual.
- `config/pricing.yaml`: per-model rates + `snapshot_date` + `snapshot_source`. Every `decisions` row captures the snapshot used so costs survive price updates.
- `docs/plans/2026-04-18-poker-hu-llm-coach-design.md`: full design decisions with attribution. Update alongside code for non-trivial changes.
- `docs/ARCHITECTURE.md`: condensed reference, keep alive.

## What NOT to do

- Do NOT add a prop-syncing `useEffect` to uncontrolled child components — use `key` remount.
- Do NOT hand-parse the LLM output as fallback. Schema-validate the tool call; if invalid, log `status="invalid_response"` and surface to the user. Silent substitution corrupts research data.
- Do NOT return a different model's response on provider error. Retry once on 5xx / rate limit, then hard fail.
- Do NOT add fields to `state_to_coach_variables` that expose villain/deck info. The three leak tests block this.
- Do NOT commit Anthropic/OpenAI API changes without running `context7` or the real API — guessing at param shapes burned multiple cycles (thinking.enabled vs adaptive, stream.get_final_message sync vs async).

## When stuck on a new Anthropic/OpenAI behavior

1. Read the exact error message.
2. `mcp__context7__query-docs` on the SDK for the specific feature.
3. If still unsure, write a 10-line Python script that hits the real API with the `.env` key and print the response — faster than guessing.
4. Record the finding in a commit message so future sessions don't re-derive it.
