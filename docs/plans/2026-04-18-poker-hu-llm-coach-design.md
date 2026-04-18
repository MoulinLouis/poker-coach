# Poker HU LLM Coach — Design Document

- **Date:** 2026-04-18
- **Status:** Design phase complete; implementation starting at Phase 0
- **Author:** Louis (sole code contributor)

---

## Context

Local-only web-based poker coach powered by large language models. Two modes:

1. **Live coach** — two humans play heads-up No-Limit Hold'em face to face. Hero receives real-time coaching on every decision. Villain plays without assistance. The LLM sees hero's cards, board, stacks, and action history, not villain's cards.
2. **Spot analysis** — manual entry of a poker spot (positions, stacks, cards, board, action history). The LLM recommends an action with reasoning.

**Not RTA.** Not connected to any real poker room.

**The prompt engineering is the project.** Different prompt structures produce dramatically different quality of advice. The system must make iteration on prompts and comparison between models painless.

## Model strategy

Primary default: **GPT-5.3-codex with `reasoning.effort="xhigh"`** — best published poker benchmark (-16 bb/100 vs GTO Wizard), ~$0.06/decision, 82% cheaper than Claude Opus 4.7 at comparable quality (per pricing analysis).

Full UI selector:

| Selector id | Provider | Model | Effort / budget | Use case |
|---|---|---|---|---|
| `gpt-5.3-codex-xhigh` | OpenAI | `gpt-5.3-codex` | `reasoning_effort=xhigh` | Default, deep reasoning |
| `gpt-5.4-medium` | OpenAI | `gpt-5.4` | `reasoning_effort=medium` | Balanced speed/quality |
| `claude-opus-4-7-deep` | Anthropic | `claude-opus-4-7` | `thinking_budget=8192` | Qualitative comparison |
| `claude-haiku-4-5-min` | Anthropic | `claude-haiku-4-5-20251001` | `thinking_budget=1024` | Prompt exploration, volume |

This overrides CLAUDE.md's "Claude primary; GPT in a later phase" — the oracle abstraction is multi-provider from day one.

API idioms:

- **OpenAI:** Responses API (`client.responses.stream`), not Chat Completions. `previous_response_id` preserves encrypted chain-of-thought across turns; `store=True` default.
- **Anthropic:** Messages API with `thinking={"type":"enabled","budget_tokens":N}`. Signed `thinking` blocks preserve reasoning across turns. `temperature` forced to 1 when thinking enabled.
- **Both:** tool use with forced schema; reasoning/thinking tokens billed at output rate.

---

## Section 1 — Stack & topology

**Python 3.12 + FastAPI + SQLAlchemy Core + Pydantic** backend; **React 18 + Vite + TypeScript + TanStack Query** frontend; **SQLite** datastore; **single-process local deploy**.

Rationale:

- Python wins for first-class Anthropic and OpenAI SDKs, plus the "prompt engineering is the project" mandate makes pandas/Jupyter analysis trivial without a language switch.
- React is the right tool for the live-coach UX: keyboard-heavy, card-grid input, streaming reasoning display. HTMX-style server rendering would fight the keyboard flow.
- SQLAlchemy **Core (not ORM)**: the schema is append-only, JSON-heavy log. ORM identity maps and lazy loading add bureaucracy.
- SQLite with JSON1 extension: plenty for single-user local. Alembic from day 1 — log schema is the highest-churn surface.
- TanStack Query earns its keep because of multi-model parallel queries (Compare mode in Spot Analysis uses `useQueries` across N selected models).
- Streaming handled by `@microsoft/fetch-event-source` (supports POST + SSE with JSON body, proper reconnect + backoff). Dedicated `useAdviceStream` hook owns the live SSE; on terminal event, writes payload into TanStack Query cache via `queryClient.setQueryData`. Streaming and caching cleanly separated.

Repo layout:

```
backend/   engine, oracle, prompts, api, logging
frontend/  React app
prompts/   versioned .md templates (git = history)
config/    pricing.yaml
data/      sqlite file (gitignored)
docs/      architecture, prompts, results, plans
```

Deploy: `make dev` runs FastAPI on :8000 and Vite on :5173; Vite proxies `/api` to backend. No Docker for MVP.

Rejected: TypeScript-everywhere / Next.js — cleaner mono-language, but Python's lead on data analysis and poker tooling wins.

---

## Section 2 — Game state engine & domain model

**Representation: immutable `GameState` snapshots.** `apply_action(state, action) -> new_state`. Snapshots serialize cleanly into the decision log; replay is folding action sequences; tests are pure-function assertions.

### Pydantic models (`backend/src/poker_coach/engine/models.py`)

```python
Seat = Literal["hero", "villain"]
Street = Literal["preflop", "flop", "turn", "river", "showdown", "complete"]
ActionType = Literal["fold", "check", "call", "bet", "raise", "allin"]

class Action(BaseModel):
    actor: Seat
    type: ActionType
    to_amount: int | None   # "raise to X" semantics; chips, not bb

class GameState(BaseModel):
    hand_id: str
    effective_stack: int           # chips
    bb: int                        # chips per big blind (bb=100 default)
    button: Seat                   # HU: SB acts first preflop, BB first postflop
    hero_hole: tuple[str, str]
    board: list[str]               # 0/3/4/5 cards
    street: Street
    stacks: dict[Seat, int]
    committed: dict[Seat, int]     # chips in pot this street
    pot: int                       # settled pot from prior streets
    to_act: Seat | None
    last_aggressor: Seat | None
    min_raise: int
    history: list[Action]
    rng_seed: int | None           # for deterministic-generated hands
    deck_snapshot: list[str] | None  # 52 cards in dealing order; authoritative
```

### Reproducibility

- `deck_snapshot` is authoritative. `rng_seed` alone is fragile across Python/RNG version changes.
- **Live coach:** both populated (seeded shuffle records into `deck_snapshot`).
- **Spot analysis:** neither needed; state is already fully specified by user input.
- Visibility: `deck_snapshot` never rendered into prompt or UI beyond what the current street reveals.

### Rules engine

- **Units: integer chips.** `bb=100` means effective 10000 = 100bb. Display layer divides. Floats in poker = eventual rounding bugs; non-negotiable.
- **Legal-action derivation:** pure function `legal_actions(state) -> list[LegalAction]` returns structured options with min/max amounts. UI greys out illegal buttons; advice prompt includes the list verbatim so the LLM cannot recommend illegal actions.
- `apply_action` raises `IllegalAction` for anything not in `legal_actions(state)` — defense in depth.
- **HU specifics handled:** SB-is-button (preflop first, postflop last), no side pots (HU only), no multi-way.
- **Uncalled-bet / change return:** when caller's committed chips < aggressor's, the excess returns to the aggressor before pot settlement. Also covers the all-in-over-shorter-stack case.
- **Min-raise reopening rule:** all-in below a full min-raise does not re-open action for the raiser (standard NLHE).

### Input adapters

- Live coach: `start_hand(stacks, bb, button, hero_hole) -> GameState`, then `apply_action` as each action happens.
- Spot analysis: form collects positions/stacks/board/hole/history; same `start_hand` + fold over history yields identical `GameState`. One engine, two entry points.

### Hand evaluator

**phevaluator** for showdown winner determination + display label ("pair of kings", "flush"). Purpose-built for hand eval; no engine-module baggage. Scope: showdown only. **Never exposed to the LLM prompt** — hand-strength reasoning is what the LLM is there for.

### Out of MVP

No straddles, ante, run-it-twice, rake modeling. Future additions don't touch stored snapshots — old snapshots never had those fields.

### Testing

Hypothesis property tests for invariants:

1. **Chip conservation:** `sum(stacks.values()) + pot + sum(committed.values()) == initial_total_chips`
2. **Street monotonicity:** streets only advance forward.
3. **`to_act` consistency:** after `apply_action`, either hand is complete OR `to_act` is set AND `legal_actions(state)` is non-empty for that actor.
4. **Illegal-action unreachability:** `apply_action` is never reachable with an action not in `legal_actions(state)`.
5. **Replay idempotency:** `reduce(apply_action, state.history, initial_state(state)) == state`. Most important invariant — if replay drifts, prompt iteration collapses.

Plus hand-written cases for every edge rule (min-raise reopening, all-in-below-min, uncalled-bet return, HU SB-button acting order).

---

## Section 3 — Oracle abstraction (multi-provider)

### Interface — one `Oracle` protocol, two implementations

```python
class Oracle(Protocol):
    def advise_stream(
        self, rendered: RenderedPrompt, spec: ModelSpec,
    ) -> AsyncIterator[OracleEvent]: ...
```

`OracleEvent` is a discriminated union: `ReasoningDelta`, `ReasoningComplete`, `ToolCallComplete` (carries parsed `Advice`), `UsageComplete` (tokens + computed cost), `OracleError`. Backend emits these as SSE frames; frontend's `useAdviceStream` consumes.

### ModelSpec: preset, not matrix

Each UI selector row is one baked spec. No model × effort cross product. Adding a selector option = one dict entry.

### Forced structured output

Single tool `submit_advice` with schema:

```json
{
  "action": {"enum": ["fold","check","call","bet","raise","allin"]},
  "to_amount_bb": {"type": "number", "minimum": 0},
  "reasoning": {"type": "string"},
  "confidence": {"enum": ["low","medium","high"]}
}
```

- **OpenAI Responses:** `tool_choice={"type":"function","name":"submit_advice"}`. Strict mode requires `additionalProperties:false` + all fields in `required` (nullable for optionals).
- **Anthropic Messages:** `tool_choice={"type":"tool","name":"submit_advice"}`. More permissive dialect.
- **Shared Pydantic schema.** A ~30-line normalizer emits two provider-specific JSON variants. Unit test both outputs against a fixture to catch dialect drift.
- `to_amount_bb` in BB (LLM-friendly); backend converts to chips via `state.bb`.
- **Confidence** logged only. Never consumed by code for filtering or weighting. LLMs are poorly calibrated on self-confidence. Research notebook will study correlation with agreement rates later.

### Reasoning preservation

Not needed for MVP single-turn decisions; abstraction must not destroy it. OpenAI: retain `response.id`. Anthropic: keep signed `thinking` blocks in assistant content. Both stored in decision log — replay and future multi-turn cost zero rework.

### Pricing + cost

`config/pricing.yaml` maps `model_id` → `{input_per_mtok, output_per_mtok}`. Reasoning/thinking tokens billed at output rate on both platforms.

Cost computed when `UsageComplete` arrives and **written into the log at that moment**, along with `pricing_snapshot` including `snapshot_date` (ISO timestamp of price validity) and `snapshot_source` (e.g., `"anthropic_api_docs_2026-04-18"` or `"manual_config"`). Historical rows survive future price changes with the actual cost at time of call.

### Error handling

Two-layer validation:

1. Pydantic validates tool input against shared schema. Schema failures → `OracleError` event + log `status="invalid_response"` with `raw_tool_input` preserved verbatim.
2. Legality check: parsed action re-checked against `legal_actions(state)`. Mismatches → log `status="illegal_action"`.

Both surface in UI as "invalid response, retry?" — never silently substituted. Retry creates a new decision row with `retry_of=<prev_id>`.

Retry once on 5xx / rate-limit with exponential backoff. Hard fail otherwise — no silent fallback to a different model (would corrupt comparison data).

### SSE forwarding (provider → backend → frontend)

- Event-by-event, no buffering. FastAPI `StreamingResponse(media_type="text/event-stream")` with `async def` generator — Starlette flushes each `yield`.
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- **Disconnect:** `async with client.responses.stream(...)` / `async with client.messages.stream(...)` — both SDKs cancel upstream HTTP on context exit. Client disconnect → `asyncio.CancelledError` into generator → `async with` unwinds → upstream closes. Provider billing stops.
- Cancellation writes `status="cancelled"` with partial reasoning preserved.

---

## Section 4 — Prompt versioning, log schema, decision lifecycle

### Prompt files

`prompts/<pack>/<version>.md`. Nested for sibling packs (`coach`, future `explainer`). YAML frontmatter + Jinja2 body:

```markdown
---
name: coach
version: v1
description: Baseline HU coach prompt with explicit legal-action list
variables: [hero_hole, board, street, pot_bb, effective_bb, history, legal_actions]
---
You are coaching a hero in heads-up No-Limit Hold'em...
```

Renderer loads file → validates declared variables → computes `template_hash = sha256(template_bytes)` → renders with Jinja2.

**Both `template_raw` and `rendered_prompt` hit the log.** Git is semantic history; `template_hash` catches stealth edits that forget to bump `version`.

### Tables (SQLAlchemy Core, JSON via SQLite JSON1)

**`sessions`** — `session_id`, `started_at`, `ended_at`, `mode` (`live`|`spot`), `notes`.

**`hands`** — `hand_id`, `session_id`, `bb`, `effective_stack_start`, `deck_snapshot` (JSON), `rng_seed`, `winner`, `showdown_state` (JSON, nullable).

**`decisions`** — one row per LLM call:

| Group | Columns |
|---|---|
| IDs | `decision_id` (ULID), `session_id`, `hand_id` (nullable for spot), `retry_of` (nullable), `created_at`, `stream_opened_at` (nullable), `latency_ms` |
| Input | `game_state` (JSON), `prompt_name`, `prompt_version`, `template_hash`, `template_raw`, `rendered_prompt`, `variables` (JSON) |
| Model | `provider`, `model_id`, `reasoning_effort`, `thinking_budget`, **`temperature`** (first-class column), `other_params` (JSON, schema-unstable by design) |
| Response | `reasoning_text`, `raw_tool_input` (JSON), `parsed_advice` (JSON), `status` (`ok` / `invalid_response` / `illegal_action` / `provider_error` / `cancelled` / `abandoned` / `timeout` / `in_flight`), `error_message` |
| Accounting | `input_tokens`, `output_tokens`, `reasoning_tokens`, `total_tokens`, `cost_usd`, `pricing_snapshot` (JSON, with `snapshot_date` and `snapshot_source`) |

**`actual_actions`** — separate table. `decision_id` FK, `action_type`, `to_amount`, `taken_at`. Separates "what the coach said" from "what the human did." Agreement rate derivable via JOIN. Cleanly handles spot-analysis (no action taken) and multi-decision-per-action cases.

Indexes: `(session_id)`, `(hand_id)`, `(model_id, prompt_version)`, `(status)`, `(created_at)`. ULID gives time-sortable `decision_id`.

Alembic migrations from commit 1.

**Template deduplication (denormalized for MVP):** `template_raw` stored on every decision. Disk is cheap; no JOINs to read a decision. Refactor to a `prompt_templates` table keyed by hash only if volume exceeds ~100k decisions.

### Decision lifecycle

1. `POST /api/decisions` with `{session_id, hand_id?, model_spec_id, prompt_name, prompt_version}`.
   - Backend materializes `GameState`, renders prompt, writes `status="in_flight"` row, **returns `decision_id` immediately. Does NOT start the oracle call.**
2. Frontend opens SSE on `GET /api/decisions/{decision_id}/stream`.
   - Backend atomically claims: `UPDATE decisions SET stream_opened_at=NOW() WHERE id=? AND stream_opened_at IS NULL`. 0 rows → 409 Conflict (double-open protection).
   - On successful claim, invokes `Oracle.advise_stream`, forwards SSE events.
3. On terminal event: backend UPDATEs row to final `status`.
4. Hero's actual action posts to `POST /api/actions` with `decision_id`. Live mode: this also drives `engine.apply_action`.

### Timeout sweeper

Single async task spawned in FastAPI `lifespan`, runs every 30s. Two thresholds:

- `stream_opened_at IS NULL AND created_at < now()-30s` → `status="abandoned"` (user closed tab before opening SSE; no API cost incurred).
- `stream_opened_at < now()-3min AND status='in_flight'` → `status="timeout"` (crash or hang; UI may show soft warning for near-threshold rows).

---

## Section 5 — UI surface

Top-level nav: **Live Coach · Spot Analysis · History · Prompts · Settings**. Always-visible **cost footer** at the bottom.

### Live Coach (critical screen)

Two-pane layout.

**Left pane — table state:** two seats (hero/villain) with stack in BB, pot, board, button indicator, current-actor halo. Cards rendered as SVG glyphs. Hero's hole cards face-up; villain's face-down unless showdown.

**Right pane — action + advice:**

- Legal-action row: only legal actions rendered as buttons. Hotkeys: `f` fold, `c` call, `k` check, `b` bet, `r` raise, `a` all-in. **`b` and `r` split** (never legal simultaneously).
- Size input: number field in BB with street-aware presets:
  - **Preflop:** `1` = min-raise, `2` = 2.5bb, `3` = 3bb, `4` = 3.5bb.
  - **Postflop:** `1` = 33% pot, `2` = 50%, `3` = 75%, `4` = pot, `5` = 150% (overbet).
  - Any digit typed directly = manual BB size.
  - Illegal sizes validated frontend (greyed) AND backend (`IllegalAction`).
- `Enter` confirms size. `space` requests advice (or auto-mode toggle in Settings). `esc` cancels in-flight SSE.
- Advice panel streaming UX states (parallels Claude.ai):
  1. `space` pressed → immediate **"Thinking…"** indicator.
  2. First reasoning token → indicator replaced by streaming text.
  3. Tool call received → advice card appears with brief highlight animation.
- **Override UX:** silent. Hero just presses the desired action hotkey. Divergence captured in `decisions.parsed_advice` vs `actual_actions.action_type`. **"Diverged from advice"** ambient indicator on the action panel. Session-end summary: "Agreement rate: X%".
- **Villain's turn:** hero clicks what villain did via same legal-action buttons scoped to villain. No LLM call.
- **New hand:** `n` → modal for hero hole, effective stack, button → engine generates `deck_snapshot` + `rng_seed`, deals, enters preflop.
- **Showdown:** when reached, modal prompts for villain's hole cards. Required for complete logs (future "what would LLM think with full info?" analysis). Skippable if villain folded.

### Spot Analysis

Single form: positions, effective stack, hero hole, board (0/3/4/5), structured action history (rows of actor/type/size).

**Compare mode:** multi-select of (model × prompt_version) pairs up to 3; `useQueries` fires in parallel; results render in resizable side-by-side columns. Each column independently streams its reasoning and lands its advice with its own cost.

### History

Filter bar: session / model / prompt_version / status / date range.

Row click → detail: full `game_state` as mini-table, `template_raw` with diff toggle vs latest of that pack, `rendered_prompt`, reasoning, raw tool input, parsed advice, actual action, tokens, cost, latency.

**Replay button:** duplicates the decision with a new (model, prompt_version), sets `retry_of` — the "retry this spot with prompt v2" workflow.

### Prompts

List of packs (`coach` + future), each showing versions annotated with the git commit that added them. Markdown editor for the current draft; preview renders against the last decision's variables or a built-in sample. Undeclared-variable lint. Save writes a new `vN.md`; git commit stays manual (no auto-commits during iteration).

### Settings

Default model spec, advice trigger (manual/auto), hotkey remap, per-model thinking-budget overrides. Persisted in SQLite `settings` table.

### Cost footer

Always visible: `session $0.23 · all-time $4.17`. Click expands to per-(model, effort) breakdown with token counts. Queries aggregate `decisions.cost_usd`.

### Keyboard philosophy

Live Coach is keyboard-first. Every critical-path action has a hotkey. `?` opens cheatsheet overlay.

### Future (deferred, not MVP)

**Auto-villain** mode: villain plays random legal actions. Speeds up solo dev + demos. Out of scope for MVP.

---

## Section 6 — Testing, deployment, sequencing, non-goals

### Engine tests (`backend/tests/engine/`)

pytest + Hypothesis. Five invariants from Section 2 + hand-written fixtures (min-raise reopening, all-in-below-min, uncalled-bet return, HU SB-button preflop order). Showdown tests assert phevaluator agreement on canonical spots.

**Gate:** no UI work until engine tests green.

### Oracle tests (`backend/tests/oracle/`)

Snapshot tests on shared Pydantic schema → provider-specific JSON emissions (catches OpenAI/Anthropic dialect drift). SDKs mocked with recorded fixtures — one real streaming interaction per provider captured, then replayed. Double-open idempotency (409). Cancellation verifies upstream closure.

### API tests (`backend/tests/api/`)

pytest-asyncio + `httpx.AsyncClient`. Full decision lifecycle: POST, SSE open/stream/finalize, client-disconnect (→`cancelled`), 30s no-open (→`abandoned`), 3min no-finalize (→`timeout`). Alembic migration round-trip per migration.

### Frontend tests

Vitest for pure components (action panel, cost footer). Playwright for one e2e happy path on Live Coach: new hand → villain 3-bet → space for advice → stream visible → override → next hand → session summary shows agreement rate.

### Tooling

Python: `uv` + `pyproject.toml`, `ruff` (format + lint), `mypy --strict`. TS: npm, `eslint`, `tsc`, `prettier`. Pre-commit runs all. GitHub Actions: three parallel jobs (backend, frontend, e2e) gate merges to main. `.env.example` committed.

### Sequencing

| Phase | Surface | Gate |
|---|---|---|
| 0 | Repo skeleton, CI, dev loop, Alembic base | `make dev` + `make test` green |
| 1 | Engine + phevaluator + showdown | Hypothesis invariants green |
| 2 | Anthropic oracle + one prompt pack + log schema | Recorded-fixture replay green |
| 3 | FastAPI + SSE + decision lifecycle + sweeper | Lifecycle e2e green (curl) |
| 4 | React Live Coach | Playwright happy path green |
| 5 | OpenAI Responses oracle + multi-model Compare | Both providers pass schema tests |
| 6 | History + Prompts editor + cost footer breakdowns | Manual acceptance |

Engine + oracle front-loaded because retrofitting correctness is painful; UI last because it's the most replaceable surface.

### Documentation as first-class deliverables

Updated per-PR, not at the end:

- `README.md` — install + run + demo screenshots
- `docs/ARCHITECTURE.md` — condensed sections 1–6; kept alive
- `docs/PROMPTS.md` — prompt pack reference + per-pack design notes
- `docs/RESULTS.md` — end-of-project quantitative analysis (model comparison, agreement rates, cost breakdowns)

### Explicit non-goals (locked in)

- No bot play (Slumbot, DecisionHoldem — DecisionHoldem also wouldn't fit on 32GB host)
- No GTO benchmark
- No websockets (SSE suffices)
- No multi-table / tournaments / ICM
- No auth
- No auto-villain (future)

---

## Open questions

None blocking. Future questions expected to emerge during:

- Phase 2, when the first real prompt pack reveals how much poker-theory scaffolding belongs in-prompt vs. as worked examples.
- Phase 5, when OpenAI and Anthropic reasoning-preservation idioms meet in a shared abstraction — may need revision.

## Decision log (attributed)

| # | Decision | Attribution |
|---|---|---|
| 1 | Hero operates the UI themselves | User |
| 2 | Prompt editor + versioned files in repo, replay later | Claude proposed D, user confirmed with enhanced log requirements (template + rendered + pricing snapshot) |
| 3 | Extended thinking + forced tool call for structured output | Claude proposed D, user confirmed pending Context7 verification |
| 4 | Full HU state machine + form adapter for spot analysis | Claude proposed C, user agreed |
| 5 | Manual hotkey + auto-mode toggle for advice trigger | Claude proposed C; user superseded with revised model strategy (multi-provider from day 1) |
| 6 | GPT-5.3-codex xhigh primary; Claude Opus secondary; Haiku for volume | User (pricing analysis) |
| 7 | Python + React + SQLite; SQLAlchemy Core | Claude proposed; user confirmed with Core requirement |
| 8 | TanStack Query + `@microsoft/fetch-event-source` | Claude proposed; user confirmed contingent on multi-model use case |
| 9 | Integer chips, `bb=100`; no floats | User — non-negotiable |
| 10 | phevaluator for showdown only; not in prompt | User |
| 11 | `rng_seed` + `deck_snapshot` for reproducibility; deck_snapshot authoritative | User; Claude refined to deck-authoritative |
| 12 | Shared Pydantic schema + provider normalizer | Claude proposed; user confirmed with strict-mode OpenAI requirements |
| 13 | Write resolved cost + pricing_snapshot per row; snapshot_date + snapshot_source | User |
| 14 | Lazy oracle invocation: POST returns id, oracle fires on SSE open; `stream_opened_at` + 30s abandoned sweeper | User |
| 15 | Split bet/raise hotkeys; street-aware size presets; silent override + divergence indicator | User |
| 16 | Showdown villain cards modal; streaming UX states | User |
| 17 | Atomic Phase 0: 6 Conventional Commits | Claude proposed; user chose commit-1-first-then-pause |
