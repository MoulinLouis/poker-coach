# Mixed-strategy LLM output — design

**Goal:** Make `submit_advice` return a GTO-solver-style mixed strategy (a list of `(action, sizing, frequency)` triplets) instead of a single deterministic verdict, so the UI can show the underlying distribution and a pro reader can evaluate the advice the way they would a solver output.

**Non-goals:** Modifying `SpotAnalysis` comparison layout, changing the Follow-button UX beyond keeping it on the argmax, touching the LLM-advice translation path (`useAdviceTranslation`).

**Current baseline:**
- `submit_advice` tool (see `backend/src/poker_coach/oracle/tool_schema.py`) returns `{ action, to_amount_bb?, reasoning, confidence }` — a single deterministic verdict with a qualitative confidence tag.
- Two prompt versions ship: `prompts/coach/v1.md` (legacy) and `v2.md` (current default, data-only payload).
- Frontend renders the verdict as a large foil-styled action word plus a small sizing line; Follow button applies `advice.action` + `advice.to_amount_bb`.
- `parsed_advice` in the `decisions` table is a JSON column — no SQL migration required for shape extension.

---

## Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | **Solver-style schema** — `strategy: Array<{action, to_amount_bb \| null, frequency}>` with multi-entries per action permitted (polarized sizings) | Matches the mental model of a pro reading a solver output; cleanly expresses "polarized 80% 3x / 20% 7x". |
| 2 | **Additive, not breaking** — new prompt `coach/v3.md` + extended tool schema with `strategy` required on v3, absent on v2 | Zero churn on existing History rows; enables side-by-side v2/v3 evaluation; trivial rollback. |
| 3 | **Follow = argmax(strategy)** | Simplest reading; the mix is still visible in the frequency bars so the pro isn't blind to the alternatives. |
| 4 | **Spot Analysis untouched in this spec** | Keeps the surface of this change tight; the divergence/heatmap view across models lands in a follow-up spec. |

---

## Schema (logical)

Tool input (v3 variant only — v2 schema is unchanged):

```ts
{
  strategy: Array<{
    action: "fold" | "check" | "call" | "bet" | "raise" | "allin",
    to_amount_bb: number | null,   // null for non-sizing actions
    frequency: number               // 0..1
  }>,
  reasoning: string,
  confidence: "low" | "medium" | "high",
  action?: ActionType,              // optional in v3 (derived server-side)
  to_amount_bb?: number | null      // optional in v3 (derived server-side)
}
```

**Validation (strict — reject with `invalid_schema` if violated):**
- Every `action` must be in the spot's `legal_actions` (`illegal_action` if not).
- For `bet` / `raise`: `to_amount_bb` required and within `[min_to_bb, max_to_bb]`.
- For `fold` / `check` / `call` / `allin`: `to_amount_bb` must be `null`.
- At least one entry with `frequency > 0`.
- Sum of frequencies within `[0.98, 1.02]`; outside that → reject. Within the band but `!= 1.0` → normalize by `1/sum` server-side (logged as info, not warning).

**Normalization behavior:**
- Multi-entries with identical `(action, to_amount_bb)`: merge by summing frequencies. Logged as info.
- Entries with `frequency == 0` after parsing: drop silently (treat as implicit 0% omission).
- Post-validation, entries are sorted by frequency desc for deterministic rendering.

**Server-derived fields:**
- `action = argmax(strategy).action`
- `to_amount_bb = argmax(strategy).to_amount_bb`
- The LLM *may* also fill them; if it does, the server-derived values override (source-of-truth is `strategy`).

---

## Prompt v3

New file `prompts/coach/v3.md`. Body is identical to `v2.md` through the legal-actions block; only the trailing "Call `submit_advice`…" instruction changes.

New closing block:

```
Call `submit_advice` now. In the `strategy` field, output the full mixed strategy
as a GTO solver would — one entry per (action, sizing) you actually play, each
with a frequency in [0, 1]. Frequencies across all entries must sum to 1.

Guidelines:
- List only actions you play at least 5% of the time; omit the rest (implicit 0%).
- For bet/raise, you may include up to two sizings (a small and a large) when the
  spot is polarized; one sizing otherwise.
- Frequencies are rounded to 0.05 increments (e.g. 0.35, 0.60, 0.05).
- The primary `action` and `to_amount_bb` fields are derived by the server from
  your strategy — you do not need to fill them.
- `reasoning` is still 2 sentences, 40-60 words, explaining why the mix is what
  it is (what drives the split between the top action and the alternatives).
```

The YAML frontmatter `variables` list stays identical to v2 — no new context variables needed.

---

## Tool schema versioning

`tool_schema.py` currently exports `anthropic_tool_spec()` and `openai_tool_spec()` with no parameters. Change signatures to `anthropic_tool_spec(prompt_version: str)` and `openai_tool_spec(prompt_version: str)`:

- `prompt_version == "v1" | "v2"`: emit the legacy schema (unchanged).
- `prompt_version == "v3"`: emit the new schema with `strategy` required and `action`/`to_amount_bb` optional-nullable.

Oracle dispatch (`anthropic_oracle.py`, `openai_oracle.py`) already receives `rendered: RenderedPrompt` — reads `rendered.version` to parameterize the tool spec builder.

The existing **fixture-snapshot drift test** (one of our non-regression guardrails) grows a second fixture for v3 on both providers.

---

## Pydantic models

```python
# backend/src/poker_coach/oracle/base.py
class StrategyEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    action: ActionType
    to_amount_bb: float | None = None
    frequency: float

class Advice(BaseModel):
    model_config = ConfigDict(frozen=True)
    action: ActionType
    to_amount_bb: float | None = None
    reasoning: str
    confidence: Confidence
    strategy: list[StrategyEntry] | None = None   # null for v2, list for v3
```

A new validator module `oracle/strategy_validator.py` exports:

```python
def normalize_strategy(
    entries: list[dict],
    legal_actions: list[LegalAction],
) -> list[StrategyEntry]
```

Returns the normalized, sorted list or raises `ValueError` (caller translates to `OracleError(kind="invalid_schema")`).

---

## Frontend

**`api/types.ts`:**

```ts
export interface StrategyEntry {
  action: ActionType;
  to_amount_bb: number | null;
  frequency: number;
}
export interface Advice {
  action: ActionType;
  to_amount_bb: number | null;
  reasoning: string;
  confidence: "low" | "medium" | "high";
  strategy: StrategyEntry[] | null;   // nullable for v2 decisions
}
```

**`components/AdvicePanel.tsx`:**
- Under the verdict + sizing line, a new `StrategyBars` sub-component.
- Renders one row per entry (already sorted desc by backend), with:
  - Left: action label (`Check`, `Bet 3bb`, etc.) using existing i18n keys `advice.action.*`, sizing appended via `${sizing}${bbUnit}` when relevant.
  - Bar fill width proportional to `frequency`.
  - Right: percent label (`45%`).
  - Color keyed to action theme (fold=parchment, check/call=jade, bet/raise=gold, allin=coral) — matches `actionTheme` already defined in the file.
  - Argmax entry has a border + subtle glow to mark it as the Follow target.
- If `advice.strategy == null`, the section is not rendered — v2 decisions unchanged visually.

**i18n:** new keys under `advice.strategy.*`:
- `advice.strategy.header` — EN: "Strategy", FR: "Stratégie"
- `advice.strategy.argmaxHint` — EN: "Follow plays the highlighted row", FR: "Follow joue la ligne mise en évidence"

**Follow button:** no behavior change. Still `onFollow(advice.action, advice.to_amount_bb)` where those come from the server-derived argmax.

**History detail view:** if `parsed_advice.strategy` is present, render a compact read-only version of the same bars in the advice section.

---

## Default prompt version

Flip `defaultPromptVersion` (used by `LiveCoach.tsx` when creating a decision) from `"v2"` to `"v3"`. v2 remains selectable in the UI for A/B comparison.

---

## Testing

**Backend:**
- `test_strategy_validator.py` — sum tolerance (0.97 reject, 0.99 normalize, 1.00 pass, 1.02 normalize, 1.05 reject), illegal action rejection, sizing-out-of-range rejection, `to_amount_bb` required for bet/raise, `to_amount_bb` must be null for fold/check/call/allin, duplicate `(action, sizing)` merge, zero-frequency dropping, argmax derivation.
- `test_advice_round_trip.py` — `Advice` with and without `strategy` serializes/deserializes through `model_dump(mode="json")` → `Advice.model_validate(...)`.
- `test_tool_schema_snapshot.py` — fixture JSON for v2 and v3 on both providers (four total), drift test.
- `test_stream.py` (integration) — fake oracle emits a `ToolCallComplete` with a `strategy` field; DB row `parsed_advice` includes the normalized strategy after persistence.
- `test_prompts.py` — v3 template renders cleanly with the same `state_to_coach_variables` payload as v2 (no new variables required).
- Existing `test_no_villain_leak.py` must still pass unchanged — the three-layer villain-card guarantee is orthogonal to output shape.

**Frontend (vitest):**
- `AdvicePanel.test.tsx` — add: renders `StrategyBars` when `strategy` is an array; does not render it when `strategy` is null; argmax row has the highlight class; bar width reflects frequency; existing Follow-button tests continue to pass (Follow still uses `advice.action` argmax).
- New `StrategyBars.test.tsx` — pure component test: sort order preserved, percent labels, accessibility (aria-label on each row).

**E2E:** no new specs. Existing specs run v2 (default in `fixtures`) or use the engine-only path — unchanged.

---

## Rollback

1. Revert the `defaultPromptVersion` flip in `LiveCoach.tsx` (cosmetic — v2 stays available as the default).
2. Drop the v3 entry in the tool-schema-version switch (OK even if DB has v3 decisions — they remain readable in History; just can't be regenerated).
3. Leaving `strategy: list[StrategyEntry] | None` in the Pydantic model is harmless for v2 decisions.

No destructive migration — rollback is a three-line revert.

---

## Out of scope (follow-up specs)

- Spot Analysis divergence view (quantitative disagreement heatmap between N models).
- Confidence derivation from entropy (`confidence` could become derived rather than a separate LLM signal).
- "Training mode" — hide advice until user commits, then reveal.
- Multi-sizing polarization limits (this spec allows multi; an explicit `max 2 sizings per action` policy is left for a follow-up if LLMs misbehave).
