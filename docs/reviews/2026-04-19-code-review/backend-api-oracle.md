# Backend API + Oracle Review

## Scope

~1,228 LOC across `api/app.py`, `api/deps.py`, `api/schemas.py`, `api/oracle_factory.py`, `api/sweeper.py`, all 9 route modules, `oracle/{base,anthropic_oracle,openai_oracle,presets,pricing,system_prompt,tool_schema}.py`, `prompts/{context,renderer}.py`, `db/tables.py`, `db/engine.py`, `main.py`, and the coach prompt markdown.

Top themes:
1. **Observability gaps.** Several `except Exception: pass` blocks silently swallow errors (sweeper, SSE finalization, prompt listing).
2. **Duplication between Anthropic and OpenAI oracles.** Shape-specific code that must stay separate; reasoning-assembly pattern that can share a helper.
3. **Stringly-typed status codes.** Decision status is `str` in schemas; the allowed set is documented but not type-enforced.

---

### [F-1] Stringly-typed decision status in schemas
- **File:** `backend/src/poker_coach/api/schemas.py:66`, `backend/src/poker_coach/api/routes/decisions.py:41, 168`
- **Severity:** Medium
- **Category:** schema
- **Problem:** `DecisionSummary.status` and `DecisionListRow.status` are typed as `str`, even though rows only ever hold `in_flight|ok|invalid_response|illegal_action|provider_error|cancelled|abandoned|timeout`. Pydantic would catch typos if this were a `Literal`.
- **Suggested change:** Add at the top of `schemas.py`:
  ```python
  DecisionStatus = Literal[
      "in_flight", "ok", "invalid_response", "illegal_action",
      "provider_error", "cancelled", "abandoned", "timeout",
  ]
  ```
  Replace `status: str` usages in `DecisionSummary`, `DecisionListRow`, and the `list_decisions` query filter. Cross-reference the set with `docs/decisions/` to ensure no value is missing.
- **Breaking risk:** Low — purely additive validation for read-side responses. Pydantic will accept the same values it already accepts; unexpected values start 500ing (which is what we want).

---

### [F-2] `OracleError.kind` already uses Literal — apply same to status
- **File:** `backend/src/poker_coach/oracle/base.py:90-95`
- **Severity:** Low
- **Category:** schema
- **Problem:** `OracleError.kind` is already a `Literal[...]` with validated values. The inconsistency is that decision-status in schemas is not. Group with F-1.
- **Suggested change:** Apply F-1 to match this pattern project-wide.
- **Breaking risk:** None.

---

### [F-3] Linear preset lookup in `stream.py`
- **File:** `backend/src/poker_coach/api/routes/stream.py:60-64`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** `_find_preset_for(row)` iterates `MODEL_PRESETS.values()` linearly, re-running on every stream open. `decisions.py` uses `MODEL_PRESETS.get(preset_id)` directly.
- **Suggested change:** In `oracle/presets.py`, add a module-level secondary index:
  ```python
  PRESETS_BY_MODEL: dict[tuple[str, str], ModelSpec] = {
      (s.model_id, s.provider): s for s in MODEL_PRESETS.values()
  }
  ```
  Replace `_find_preset_for(row)` with `PRESETS_BY_MODEL.get((row.model_id, row.provider))`.
- **Breaking risk:** Low — internal refactor; covered by `tests/api/test_lifecycle.py` stream paths.

---

### [F-4] Catch-all `Exception` in prompt render fails to distinguish user vs server errors
- **File:** `backend/src/poker_coach/api/routes/decisions.py:89`
- **Severity:** Low
- **Category:** quality
- **Problem:** Generic `except Exception` wraps both `PromptVariableError` (user input → 400) and unexpected bugs (should be 500) into a single 400 response. Loses the distinction.
- **Suggested change:** Order specifically:
  ```python
  try:
      rendered = renderer.render(...)
  except PromptVariableError as exc:
      raise HTTPException(status_code=400, detail=f"prompt render failed: {exc}")
  ```
  Let unexpected exceptions propagate to the default 500 handler (or add a dedicated `except Exception` that logs before raising 500).
- **Breaking risk:** Low — clarifies error semantics; existing 400-on-user-error behavior preserved.

---

### [F-5] Malformed prompt frontmatter silently yields a half-populated list entry
- **File:** `backend/src/poker_coach/api/routes/prompts.py:74`
- **Severity:** Low
- **Category:** quality
- **Problem:** When listing prompts, a corrupted template produces an entry with `description=None` and no warning. Corruption is invisible in the UI.
- **Suggested change:** Log the exception with context before swallowing:
  ```python
  logger.warning("malformed template %s/%s at %s: %s", pack, version, path, exc)
  ```
  Consider adding `malformed: bool` to the response so the frontend can flag the row.
- **Breaking risk:** None — pure observability add.

---

### [F-6] Reasoning-assembly pattern duplicated across oracles
- **File:** `backend/src/poker_coach/oracle/anthropic_oracle.py:120-144`, `backend/src/poker_coach/oracle/openai_oracle.py:86-106`
- **Severity:** Low
- **Category:** duplication
- **Problem:** Both oracles collect reasoning chunks into a list, join, and yield `ReasoningComplete`. The SDK-specific extraction differs (`thinking_delta` vs `reasoning.delta`), but the post-stream assembly is identical.
- **Suggested change:** Add to `oracle/base.py`:
  ```python
  def assemble_reasoning(chunks: list[str]) -> ReasoningComplete:
      return ReasoningComplete(text="".join(chunks))
  ```
  Call from both oracles after their SDK-specific delta loops. Keep the delta extraction itself SDK-specific.
- **Breaking risk:** None — cosmetic dedup. The shape of `ReasoningComplete` is unchanged.

---

### [F-7] Undocumented fallback for OpenAI reasoning_tokens field
- **File:** `backend/src/poker_coach/oracle/openai_oracle.py:140-146`
- **Severity:** Low
- **Category:** quality
- **Problem:** Reasoning tokens come from `output_tokens_details.reasoning_tokens` with a `usage.reasoning_tokens` fallback — but the fallback path is silent. Future readers won't know which OpenAI API version each branch serves.
- **Suggested change:** One-line comment above the extraction:
  ```python
  # OpenAI SDK: reasoning_tokens moved under output_tokens_details in recent releases;
  # the top-level usage.reasoning_tokens fallback covers older SDK versions.
  ```
- **Breaking risk:** None — comment only.

---

### [F-8] Redundant `float()` cast on SQLAlchemy sum results
- **File:** `backend/src/poker_coach/api/routes/cost.py:72, 78-79`
- **Severity:** Nit
- **Category:** polish
- **Problem:** `float(row.total or 0.0)` — `SUM()` already returns a float, and `or 0.0` already ensures a float literal. The cast is noise.
- **Suggested change:** Drop to `cost_usd=row.total or 0.0`.
- **Breaking risk:** None.

---

### [F-9] Two separate existence SELECTs where one query suffices
- **File:** `backend/src/poker_coach/api/routes/decisions.py:96-106`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** `create_decision` issues one SELECT to check session_id exists, then (optionally) a second for hand_id. Both could be collapsed or parallelized.
- **Suggested change:** Modest win, optional:
  ```python
  session_row = conn.execute(select(sessions.c.session_id).where(sessions.c.session_id == body.session_id)).first()
  hand_row = conn.execute(select(hands.c.hand_id).where(hands.c.hand_id == body.hand_id)).first() if body.hand_id else None
  ```
  The real improvement is legibility — keep the two-query form if you prefer clarity.
- **Breaking risk:** Low — transaction semantics unchanged (same `begin()` block).

---

### [F-10] `OracleFactory` Protocol has only one production implementation
- **File:** `backend/src/poker_coach/api/deps.py:19-20`
- **Severity:** Nit
- **Category:** over-abstraction
- **Problem:** The `OracleFactory` Protocol is satisfied by exactly one concrete class (`DefaultOracleFactory`). Tests use `FakeOracleFactory`, which is the documented reason for the Protocol — so this is a **test-substitutability** pattern, not over-abstraction.
- **Suggested change:** No change. The Protocol earns its weight by enabling `FakeOracleFactory` in tests without `unittest.mock`. Leave as is and add a one-line docstring if clarity matters.
- **Breaking risk:** High if removed — test infrastructure in `tests/api/test_lifecycle.py` depends on substituting fake factories.

---

### [F-11] `_StreamState` dataclass over-engineered for a per-request container
- **File:** `backend/src/poker_coach/api/routes/stream.py:50-58`
- **Severity:** Nit
- **Category:** polish
- **Problem:** `_StreamState` is instantiated fresh per stream; `default_factory=dict` is correct but unnecessary ceremony for a plain record.
- **Suggested change:** Keep as-is if you value the typed accessor; otherwise inline as local variables inside `generate()`. Not worth churning.
- **Breaking risk:** None.

---

### [F-12] `contextlib.suppress(Exception)` on SSE error-emit path
- **File:** `backend/src/poker_coach/api/routes/stream.py:206`
- **Severity:** Low
- **Category:** quality
- **Problem:** If writing the error SSE frame itself fails, the failure is completely silent. Bugs in the error-emit code never surface.
- **Suggested change:** Narrow the suppression and log anything unexpected:
  ```python
  with contextlib.suppress(ConnectionError, asyncio.CancelledError):
      await send_sse_error(...)
  ```
  Or keep the broad suppress but add `logger.exception(...)` inside a narrower handler.
- **Breaking risk:** None — surfacing errors that were previously silent helps debugging. Does not change the happy path.

---

### [F-13] Sweeper errors silently suppressed
- **File:** `backend/src/poker_coach/api/sweeper.py:79`
- **Severity:** Medium
- **Category:** quality
- **Problem:** `except Exception: pass` hides connection drops, constraint violations, or migration locks. The sweeper loop keeps ticking, invisibly broken.
- **Suggested change:**
  ```python
  except Exception:
      logger.exception("sweeper tick failed")
  ```
  Behavior unchanged; observability massively improved.
- **Breaking risk:** None.

---

### [F-14] `500` returned for missing-preset data consistency error
- **File:** `backend/src/poker_coach/api/routes/stream.py:133-138`
- **Severity:** Low
- **Category:** quality
- **Problem:** When a decision row references a (model_id, provider) pair that doesn't match any preset, the route returns 500. This is a data-consistency condition (presets removed after the row was written), closer to a 400/422.
- **Suggested change:** Return 422 with a specific detail:
  ```python
  raise HTTPException(status_code=422, detail=f"no preset found for {row.provider}/{row.model_id}")
  ```
- **Breaking risk:** Low — no client currently relies on the 500 shape for this case. Verify in the frontend that any generic 5xx handler isn't specialized.

---

### [F-15] System prompt hash re-computed on every decision create
- **File:** `backend/src/poker_coach/api/routes/decisions.py:92-93`
- **Severity:** Nit
- **Category:** polish
- **Problem:** The `hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()` is computed inside each request, but `SYSTEM_PROMPT` is a module-level constant.
- **Suggested change:** In `oracle/system_prompt.py` add:
  ```python
  SYSTEM_PROMPT_HASH: str = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
  ```
  Import and use in `decisions.py`.
- **Breaking risk:** None.

---

### [F-16] Truthiness filters in `list_decisions` treat empty strings as "all"
- **File:** `backend/src/poker_coach/api/routes/decisions.py:192-199`
- **Severity:** Nit
- **Category:** polish
- **Problem:** `if session_id:` conflates None and `""`. FastAPI should never pass an empty string unless the client explicitly sends one, but `is not None` is clearer.
- **Suggested change:** Switch to `is not None` for each filter guard. Matches SQLAlchemy convention used elsewhere.
- **Breaking risk:** None — behavior only differs on the edge where a client sends `?session_id=`.

---

### [F-17] Stream finalize path on BrokenPipeError
- **File:** `backend/src/poker_coach/api/routes/stream.py:206`
- **Severity:** Low
- **Category:** quality
- **Problem:** Paired with F-12. When a client disconnects, `BrokenPipeError` should be expected (not a warning). Narrow the handler to distinguish.
- **Suggested change:** After F-12, explicitly short-circuit on `BrokenPipeError` without logging to avoid warning-spam on normal disconnects.
- **Breaking risk:** None.

---

### [F-18] Health endpoint has no logic (informational only)
- **File:** `backend/src/poker_coach/api/routes/health.py`
- **Severity:** Nit
- **Category:** note
- **Problem:** Correct as-is. Called out only to confirm intentional minimalism.
- **Suggested change:** None. Optionally add a DB ping (`SELECT 1`) if this becomes a liveness probe target.
- **Breaking risk:** None.

---

### [F-19] Conditional `villain_profile` injection is load-bearing — don't touch
- **File:** `backend/src/poker_coach/prompts/context.py:61-62`
- **Severity:** N/A
- **Category:** note
- **Problem:** The branching on `villain_profile is not None` is required by the v1/v2 split (CLAUDE.md invariant #3). Flagged only to explicitly note it must stay.
- **Suggested change:** None.
- **Breaking risk:** High if changed — would break v1 prompt replay and/or leak villain info into v1 rendering.

---

### [F-20] Defensive `.isoformat() if r.created_at else ""` on non-nullable column
- **File:** `backend/src/poker_coach/api/routes/decisions.py:206`
- **Severity:** Nit
- **Category:** polish
- **Problem:** `created_at` has `server_default=func.now()`, so the `if r.created_at else ""` branch is unreachable. The `""` fallback is also a semantic lie — it would violate the response's ISO-datetime contract if ever hit.
- **Suggested change:** Drop the ternary to `r.created_at.isoformat()`.
- **Breaking risk:** Low — only regresses on a real DB corruption scenario where `created_at` is unexpectedly NULL, in which case a 500 is more correct than a silent `""`.

---

### [F-21] `get_decision_detail` selects whole row vs `get_decision` selecting 4 columns
- **File:** `backend/src/poker_coach/api/routes/decisions.py:149, 228`
- **Severity:** Nit
- **Category:** polish
- **Problem:** Inconsistent patterns for reading from the `decisions` table — one endpoint lists columns explicitly, the other uses `select(decisions)`. Detail endpoint genuinely needs most columns, so `select(decisions)` is acceptable.
- **Suggested change:** Leave as-is. Each route's column list matches its need.
- **Breaking risk:** None.

---

### [F-22] Prompt save write/validate/unlink has a TOCTOU window
- **File:** `backend/src/poker_coach/api/routes/prompts.py:130-137`
- **Severity:** Medium
- **Category:** quality
- **Problem:** Current flow: write file → validate → delete on failure. Between write and unlink, another request could read the invalid file and render a broken decision.
- **Suggested change:** Write-to-temp + atomic rename:
  ```python
  tmp = target.with_suffix(target.suffix + ".tmp")
  tmp.write_text(body.content, encoding="utf-8")
  try:
      PromptRenderer(PROMPTS_DIR).load(pack, body.version)  # validates via temp path
  except PromptVariableError:
      tmp.unlink(missing_ok=True)
      raise HTTPException(status_code=400, detail=...)
  tmp.rename(target)
  ```
  Verify that `PromptRenderer.load` can load from the tmp path, or validate by parsing `body.content` directly before touching the filesystem.
- **Breaking risk:** Low — improves atomicity. Ensure the renderer's caching (if any) doesn't stick around after the move.

---

### [F-23] Prompt save's URL-version vs frontmatter-version check is implicit
- **File:** `backend/src/poker_coach/api/routes/prompts.py:113-116`
- **Severity:** Low
- **Category:** quality
- **Problem:** The URL's `version` is validated by regex; the frontmatter's `version` is checked indirectly via `PromptRenderer.load` raising if they don't match. Works, but the relationship is easy to miss.
- **Suggested change:** Before writing, parse `body.content` as YAML frontmatter and assert `parsed["version"] == body.version`. Add an explicit 400 if they diverge.
- **Breaking risk:** None.

---

### [F-24] `coalesce` vs `or 0.0` inconsistency in cost queries
- **File:** `backend/src/poker_coach/api/routes/cost.py:40-53`
- **Severity:** Low
- **Category:** quality
- **Problem:** `all_time_total` uses `func.coalesce(sum, 0.0)`; `session_total` uses `.scalar_one() or 0.0`. Both work; the inconsistency is cosmetic.
- **Suggested change:** Pick one convention and apply both places. `coalesce` at the SQL level is preferable because it keeps the default inside the query.
- **Breaking risk:** None.

---

### [F-25] `extra="allow"` on `DecisionSummary` hides schema drift
- **File:** `backend/src/poker_coach/api/schemas.py:63`
- **Severity:** Low
- **Category:** schema
- **Problem:** `ConfigDict(extra="allow")` lets any extra DB column pass through to the response without a schema update. If a future migration adds a field and no one updates the response model, clients silently start receiving it without type safety.
- **Suggested change:** Change to `extra="ignore"` if the permissiveness is accidental, or add a docstring explaining why `allow` is intentional. `extra="forbid"` is too strict for a read-side response.
- **Breaking risk:** Low — `ignore` drops unknown fields instead of echoing them, which is the safer default. Verify the frontend doesn't rely on any echoed-back unknown fields (shouldn't — it types responses against `api/types.ts`).

---

## Confidence and caveats

- Review was static; no routes were exercised.
- Oracle findings are read against CLAUDE.md's SDK rules (async awaits, thinking-mode dispatch, cache threshold). None of the suggested changes touch those invariants.
- The Anthropic/OpenAI duplication is constrained by SDK shape — only the post-stream assembly is a real dedup candidate.
- `FakeOracleFactory` in `tests/api/test_lifecycle.py` is the protocol's reason to exist; treat it as load-bearing.
