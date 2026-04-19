# Backend Engine Review

## Scope

Reviewed 8 files: `engine/models.py`, `engine/rules.py`, `engine/deck.py`, `engine/showdown.py`, `engine/__init__.py`, `translation.py`, `ids.py`, `settings.py` (~480 LOC core + ~600 LOC tests).

Top themes:
1. Load-bearing invariants are well-guarded by property tests — no correctness issues found.
2. A single production `assert` on financial state that disappears under `python -O`.
3. Dead deck helpers only used by tests, plus small consistency nits.

---

### [F-1] Assertion in production code should be explicit error
- **File:** `backend/src/poker_coach/engine/rules.py:377`
- **Severity:** Medium
- **Category:** quality
- **Problem:** Line 377 uses `assert la.min_to is not None and la.max_to is not None` as a type guard after dictionary lookup of a known-valid `LegalAction`. Assertions are disabled under `python -O`, and this is production code handling chip state. The check is logically safe (action.type was validated, `legal_by_type[action.type]` exists) but the pattern is risky.
- **Suggested change:** Replace with an explicit guard:
  ```python
  if la.min_to is None or la.max_to is None:
      raise IllegalAction("legal_actions invariant violated: min_to/max_to missing")
  ```
  This ensures the check survives optimization flags and is explicit about the error condition.
- **Breaking risk:** Low — the invariant is sound. Changing `assert` to an explicit raise eliminates a silent failure mode under `-O`. Property tests in `backend/tests/engine/test_invariants.py` continue to pass because valid actions never hit this branch.

---

### [F-2] Overly defensive getattr on SDK content blocks
- **File:** `backend/src/poker_coach/translation.py:62`
- **Severity:** Low
- **Category:** quality
- **Problem:** Line 62 uses `getattr(b, "type", None)` on protocol-typed message content blocks. The SDK's content block type has a guaranteed `type` attribute; this defensive pattern is unnecessary and defeats type narrowing.
- **Suggested change:** Replace with direct access:
  ```python
  parts = [b.text for b in message.content if b.type == "text"]
  ```
  If you want extra safety at the SDK boundary, add one assertion at the point of the SDK call instead of inside the list comprehension.
- **Breaking risk:** None — the SDK guarantees `type`. If this ever changes, mypy-strict would catch it.

---

### [F-3] Unused deck helpers `deal_flop` / `deal_turn` / `deal_river`
- **File:** `backend/src/poker_coach/engine/deck.py:29-38`
- **Severity:** Low
- **Category:** dead-code
- **Problem:** `deal_flop()`, `deal_turn()`, `deal_river()` are defined but never imported by production code. Tests import them but the position semantics are already documented in `seeded_shuffle()`.
- **Suggested change:** Delete lines 29-38. Update any test using these helpers to use the documented slice positions directly (`deck[4:7]`, `deck[7]`, `deck[8]`) — matches how the engine itself reads them.
- **Breaking risk:** Low — only test imports break. Fix tests in the same commit. No production code path is affected.

---

### [F-4] `street_order` list re-allocated on every street transition
- **File:** `backend/src/poker_coach/engine/rules.py:155`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** `_apply_street_transition()` creates a fresh `["preflop", "flop", "turn", "river", "showdown"]` list on every call. Module-level constants are already used elsewhere in the file (`_PENDING_EXPECTED_LEN` at line 186).
- **Suggested change:** Hoist to module level:
  ```python
  _STREET_ORDER = ("preflop", "flop", "turn", "river", "showdown")
  ```
  Use a tuple (immutable). Update the single call site to reference `_STREET_ORDER`.
- **Breaking risk:** None — pure refactor.

---

### [F-5] Duplicate `STREET_ORDER` definition between rules.py and tests
- **File:** `backend/src/poker_coach/engine/rules.py:155` and `backend/tests/engine/test_invariants.py:15`
- **Severity:** Low
- **Category:** duplication
- **Problem:** Test file keeps its own copy of the street ordering. If the list ever changes, both places must be updated.
- **Suggested change:** After F-4 lands, import the module-level constant into the test:
  ```python
  from poker_coach.engine.rules import _STREET_ORDER
  ```
  Delete the duplicate local `STREET_ORDER` in the test.
- **Breaking risk:** None — test-only refactor.

---

### [F-6] Aggressive action types repeated inline
- **File:** `backend/src/poker_coach/engine/rules.py:368` (and similar sites)
- **Severity:** Nit
- **Category:** quality
- **Problem:** Membership checks `action.type in ("bet", "raise", "allin")` are repeated. `ActionType` is already a `Literal` in `models.py`; consolidating the "aggressive" subset would document intent.
- **Suggested change:** Add near the top of `rules.py`:
  ```python
  _AGGRESSIVE_TYPES: frozenset[ActionType] = frozenset({"bet", "raise", "allin"})
  ```
  Use at call sites. Keep it module-private — no need to expose it.
- **Breaking risk:** None — purely cosmetic.

---

### [F-7] `new_deck.index(card)` in `apply_reveal` hot path
- **File:** `backend/src/poker_coach/engine/rules.py:202-218`
- **Severity:** Low
- **Category:** efficiency
- **Problem:** Line 214 calls `new_deck.index(card)` inside the reveal loop. `list.index` is O(n), so this is O(n·k) over k revealed cards. For a 52-card deck and ≤5 reveals per runout, this is negligible.
- **Suggested change:** Only optimize if profiling shows a hotspot. If you do: build the lookup once before the loop:
  ```python
  card_positions = {card: i for i, card in enumerate(new_deck)}
  ```
  Current code is clear and correct; leave it unless measurable.
- **Breaking risk:** None if done carefully. The property tests enforce `deck_snapshot[4:4+len(board)] == board` so a wrong-position swap would be caught.

---

### [F-8] `TranslationResult` uses `@dataclass` while every other value object uses Pydantic
- **File:** `backend/src/poker_coach/translation.py:39-42`
- **Severity:** Nit
- **Category:** consistency
- **Problem:** The rest of the project uses `BaseModel` with `model_config = ConfigDict(frozen=True)` for value objects. `TranslationResult` breaks this pattern with `@dataclass(frozen=True)`.
- **Suggested change:** Convert for consistency:
  ```python
  class TranslationResult(BaseModel):
      model_config = ConfigDict(frozen=True)
      translation: str
      cost_usd: float
  ```
  Or: if the dataclass is intentional (e.g., avoiding Pydantic validation on a simple pair), leave it and add a one-line comment explaining why.
- **Breaking risk:** None — both are immutable named records. Callers that use positional or keyword construction continue to work.

---

## Confidence and caveats

- The engine subsystem is well-structured; critical invariants (chip conservation, street monotonicity, replay idempotency, deck-snapshot consistency) are guarded by property tests.
- No findings suggest correctness violations — all flagged issues are quality/efficiency polish.
- The `assert` at line 377 (F-1) is the most actionable from a safety standpoint, though unlikely to manifest in practice because `legal_actions()` never produces a malformed `LegalAction`.
- Tests were not executed during this review (read-only scope).
