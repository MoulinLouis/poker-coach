# Board Reveal Flow — Design

**Status:** Validated, ready for implementation
**Date:** 2026-04-18

## Context

Today the engine auto-deals the flop, turn, and river from `deck_snapshot[4:9]` during street transitions. That works for seeded/demo hands but breaks the coach's primary use case: the user plays or observes a **real** hand and needs the LLM to see the **actual** cards on the table. Without manual board input, postflop advice is generated against fantasy cards.

This design makes the board user-inputted. After the action that closes a street, a blocking modal opens and the user enters the cards that actually fell. The engine reconciles `deck_snapshot` so the replay invariant continues to hold.

## Goals

- User inputs real flop/turn/river cards as part of a complete hand flow.
- LLM receives the actual board in its prompt when asked for advice on postflop streets.
- Replay determinism preserved under a **new** replay function that interleaves actions and reveals (see Section 1). The old `reduce(apply_action, history, initial_state)` form is replaced.
- Four of the five engine invariants stay green. **Invariant 3 (`to_act` consistency) is deliberately weakened** to allow non-terminal states with `pending_reveal != None`; see Section 3.

## Non-goals (V1)

- Editing a past street's cards (e.g., fixing a mis-entered flop after the turn falls). If wrong, start a new hand.
- Mode toggle between "demo / auto-deal" and "real session / manual input". The tool is a coach — manual input is the primary and only mode.
- Random-board generation in setup. "Deal random" in `SetupPanel` keeps filling holes only.
- **Unknown villain hole cards.** `SetupPanel.tsx:30` and `LiveCoach.tsx:84` still require both villain slots before a hand can start. True live coaching against a real unknown opponent needs a follow-up change to make villain holes optional throughout the stack (prompts, schemas, UI, validation in `/engine/reveal`). This design does not cover that — when it lands, the reveal endpoint's duplicate check must be adjusted to handle `villain_hole is None`.

---

## Section 1 — Engine + API contract

**Principle:** the engine stays authoritative. It signals *when* it needs board cards; the frontend supplies them through a dedicated endpoint; the engine rewrites `deck_snapshot` to stay consistent with the replay guarantee.

### GameState changes (`engine/models.py`)

Add two fields to `GameState`:

```python
pending_reveal: Literal["flop", "turn", "river", "runout"] | None = None
reveals: list[list[str]] = []  # one entry per reveal event, in order
```

- `pending_reveal` gates play: while non-`None`, `to_act is None` and `legal_actions(state) == []`.
- `reveals` is a sibling to `history` (which stays `list[Action]` strict). Each reveal appends one entry: 3 cards for flop, 1 for turn, 1 for river, 5 for an all-in runout.

### Engine changes (`engine/rules.py::_apply_street_transition`)

When a street would open, instead of dealing from `deck_snapshot[4:9]`:

1. Advance `state.street` to the new street (existing logic, including all-in fast-forward to `"showdown"`).
2. Leave `state.board` unchanged.
3. Set `state.pending_reveal`:
   - `"flop"` / `"turn"` / `"river"` for normal transitions.
   - `"runout"` whenever the transition fast-forwards to showdown and the board isn't yet full — this can happen from **preflop, flop, or turn** (see `rules.py:171-182`).
4. Set `state.to_act = None`.

`legal_actions(state)` returns `[]` whenever `pending_reveal is not None`.

### Reveal length per pending_reveal

Length is derived from `state.board`, not hard-coded:

| `pending_reveal` | Expected `len(cards)`            |
|------------------|----------------------------------|
| `"flop"`         | `3` (board is empty)             |
| `"turn"`         | `1` (board has 3)                |
| `"river"`        | `1` (board has 4)                |
| `"runout"`       | `5 - len(state.board)` (1, 2, or 5) |

A preflop-all-in runout reveals 5 cards; a flop-all-in runout reveals 2; a turn-all-in runout reveals 1.

### New endpoint `POST /api/engine/reveal`

**Input:** `{ state: GameState, cards: list[str] }`

**Validation:**
- `state.pending_reveal is not None` (otherwise 409).
- `len(cards)` equals the expected length per the table above.
- Each card is a valid rank+suit string.
- No duplicates with `state.hero_hole`, `state.villain_hole` (if set), or `state.board`.

**Effect:**
- Extend `state.board` with the new cards.
- Append `cards` as a single entry to `state.reveals`.
- Clear `state.pending_reveal`.
- Rewrite `deck_snapshot`: swap positions so `deck_snapshot[4 : 4 + len(new_board)] == new_board` in order. The displaced cards (whatever was at those slots) move to whatever positions the swapped-in cards occupied. This preserves the "no duplicates in deck" invariant while reflecting reality.
- Recompute `state.to_act` via existing logic (may stay `None` if we're at showdown/complete).

### Replay — new function

The current replay form (`backend/tests/engine/test_invariants.py:127`):

```python
replay = reduce(apply_action, final.history, initial_state(final))
```

no longer converges, because `apply_action` now halts at `pending_reveal` without dealing board cards. Replace with a formal `replay(state: GameState) -> GameState`:

```python
def replay(state: GameState) -> GameState:
    s = initial_state(state)
    reveal_cursor = 0
    for action in state.history:
        s = apply_action(s, action)
        while s.pending_reveal is not None:
            s = apply_reveal(s, state.reveals[reveal_cursor])
            reveal_cursor += 1
    assert reveal_cursor == len(state.reveals), "unused reveals"
    return s
```

The ordering is deterministic: reveals are consumed exactly when a street transition sets `pending_reveal`, and `state.reveals` is kept in the order they were applied. The new invariant becomes `replay(state) == state`. `initial_state()` stays unchanged (still reads only `deck_snapshot[0:4]`).

### New invariant

Add to `test_invariants.py`:

```python
# After any reveal, deck_snapshot mirrors the revealed board.
if state.deck_snapshot is not None:
    assert state.deck_snapshot[4 : 4 + len(state.board)] == state.board
```

---

## Section 2 — UI frontend

### New component `BoardPicker.tsx`

Separate from the existing `CardPicker` because:
- `CardPicker` is uncontrolled with 4 fixed slots (h1/h2/v1/v2) and holds "Deal random" logic specific to holes.
- Mixing 3/1/1/5-slot modes would bloat it without benefit.

**Shared primitive:** extract `CardSlot.tsx` (rank + suit selection, duplicate validation) and reuse it in both pickers. If extraction proves noisy, copying is acceptable — they're small.

### Trigger (`LiveCoach.tsx`)

After every `engineApply()` that returns a snapshot, check `state.pending_reveal`. If non-`null`, mount `<BoardPicker>` as a blocking modal overlay.

### Terminal-state checks must account for `pending_reveal`

Two existing checks assume `street in {"showdown","complete"}` means the hand is over. That's now false during a runout:

- `LiveCoach.tsx:174` — `handComplete` must become:

  ```ts
  snapshot.state.pending_reveal === null
    && (snapshot.state.street === "complete" || snapshot.state.street === "showdown")
  ```

  Without this, a preflop-all-in would render `HandSummary` underneath the mandatory reveal modal.

- `PokerTable.tsx:7` — `showVillainHole` must similarly require `state.pending_reveal === null` before exposing villain cards at showdown. Without this, villain holes would leak visually while the runout modal is open, before the user has even seen the river.

**Props:**
- `street: "flop" | "turn" | "river" | "runout"`
- `existingBoard: string[]` — already-revealed cards (shown as locked, for runout context)
- `excludedCards: string[]` — hero hole + villain hole (if set) + existing board; greyed out in the selector
- `onConfirm: (cards: string[]) => void` — calls the new `engineReveal(state, cards)` client method → new state → render resumes normally

### Modal layout

- **Header:** "Révèle le flop" / "Révèle le turn" / "Révèle la river" / "Révèle le run-out (all-in)"
- **Body:**
  - Flop: 3 slots side by side.
  - Turn: 1 slot (with the 3 existing flop cards shown locked to the left).
  - River: 1 slot (with the 4 existing cards shown locked to the left).
  - Runout: grouped as `[flop1][flop2][flop3] | [turn] | [river]` with visual separators. Slots already filled by previous reveals (if any) appear locked on the left; only the remaining positions are editable.
- **Confirm button:** disabled until every editable slot is filled.
- **No Cancel button:** the reveal is mandatory once the street has closed.
- **No "Deal random":** the user must input what they actually see.

### No prop-syncing useEffect

Following the CardPicker ADR: if the parent needs to reset the picker mid-session, pass a new `key`. Don't add an effect that re-syncs props into internal state.

---

## Section 3 — Tests, migration, guardrails

### Backend tests

Add to `backend/tests/engine/test_rules.py`:

- `test_street_transition_sets_pending_reveal`: after the action that closes preflop, assert `state.street == "flop"`, `state.board == []`, `state.pending_reveal == "flop"`, `state.to_act is None`, `legal_actions(state) == []`.
- `test_reveal_board_advances_play`: after `reveal(["Ah","Kd","2s"])`, assert `state.board == ["Ah","Kd","2s"]`, `state.pending_reveal is None`, `state.to_act` recomputed, `state.deck_snapshot[4:7] == ["Ah","Kd","2s"]`.
- `test_reveal_runout_from_preflop_allin`: preflop all-in → `pending_reveal == "runout"` → `reveal([5 cards])` → `street == "showdown"`, `len(board) == 5`.
- `test_reveal_runout_from_flop_allin`: flop all-in (with board already `[c1,c2,c3]`) → `pending_reveal == "runout"` → `reveal([2 cards])` → `street == "showdown"`, `len(board) == 5`.
- `test_reveal_runout_from_turn_allin`: turn all-in (with board already `[c1..c4]`) → `pending_reveal == "runout"` → `reveal([1 card])` → `street == "showdown"`, `len(board) == 5`.
- `test_reveal_runout_rejects_wrong_length`: runout from flop expects 2 cards; passing 5 → `IllegalAction`.
- `test_reveal_rejects_duplicate`: card already in hero hole → `IllegalAction`.
- `test_reveal_rejects_wrong_length`: 2 cards for a flop reveal → `IllegalAction`.
- `test_reveal_rejects_when_no_pending`: calling reveal with `pending_reveal is None` → 409 / `IllegalAction`.

Extend `backend/tests/engine/test_invariants.py`:

- **Invariant 3 (to_act consistency) — rewritten.** Current form (`test_to_act_consistency`, lines 94-101) asserts every non-terminal state has `to_act is not None` and non-empty `legal_actions`. New form:

  ```python
  if state.street in ("showdown", "complete") or state.pending_reveal is not None:
      assert state.to_act is None
      assert legal_actions(state) == []
  else:
      assert state.to_act is not None
      assert legal_actions(state)
  ```

  This is a deliberate contract change — the CLAUDE.md engine-invariants section needs the same update.
- **Invariant 4 (illegal-action unreachable) — tightened** to skip states with `pending_reveal is not None` as well as showdown/complete (same reason: no legal actions exist).
- **Invariant 5 (replay idempotency) — rewritten** to use the new `replay(state)` function (see Section 1) instead of `reduce(apply_action, history, initial_state)`.
- **New invariant:** `deck_snapshot[4 : 4+len(board)] == board` after every reveal.
- Hypothesis `played_hand()` strategy updated to interleave reveal events so the generated state histories exercise both phases.

Add to `backend/tests/api/test_engine_routes.py`:

- `POST /api/engine/reveal` — success case (flop) and each error case (wrong length, duplicate, no pending).

### Frontend tests

- **Vitest `BoardPicker.test.tsx`:** renders N slots per `street` (including the variable-length runout cases), disables Confirm until complete, hides `excludedCards` from the picker grid.
- **Vitest `LiveCoach.test.tsx`** (or component test covering terminal logic): with `snapshot.state.street === "showdown"` but `pending_reveal === "runout"`, assert `HandSummary` is NOT rendered and villain hole is NOT exposed — only the BoardPicker modal is visible.
- **Playwright** (extend `live-coach.spec.ts`): play preflop through → assert modal appears → fill flop → modal closes → ActionBar shows postflop actions → play through to showdown. Add a second scenario: preflop all-in by both players → assert runout modal appears with 5 slots → fill → `HandSummary` appears after reveal. Uses the fake oracle factory so no LLM calls fire.

### DB migration

None. `pending_reveal` and `reveals` serialize into the existing JSON column. Rows written before this change lack the fields; Pydantic defaults (`None`, `[]`) cover them.

### CLAUDE.md guardrail

Add a 7th point to "Load-bearing gotchas":

> **`deck_snapshot` is rewritten by `/engine/reveal` to reflect user-supplied board cards.** Any code that reads `deck_snapshot[4:9]` for anything other than replay reconstruction must read `state.board` instead. Treat `deck_snapshot` positions beyond `[0:4]` (hero+villain holes) as implementation detail of replay, not a reliable source of board cards.

### Existing guardrails that stay green by construction

- **No villain leak** (`test_no_villain_leak.py`): `state_to_coach_variables` already exposes only `state.board` (public info), never `deck_snapshot` or `villain_hole`. The reveal flow doesn't touch these projections.
- **LLM sees real board in prompt:** the temporal guarantee is built into the engine. While `pending_reveal is not None`, `to_act is None` and no decision request can fire. By the time `/api/decisions` is called for the hero's postflop action, `state.board` contains the cards the user just typed in. Confirmed via `prompts/context.py:39` → `prompts/coach/v1.md:8,26`.

---

## Out of scope / future work

- **Optional villain hole cards.** See "Non-goals (V1)". Without this, live-coaching against a real unknown opponent still isn't usable end-to-end — board reveal is a necessary but not sufficient step.
- Editing a past street's cards after a later street has been revealed (requires replaying subsequent actions; no user demand).
- Random-board generation at setup time for offline/demo play.
- A "spot analysis" import path where full board is provided upfront (would skip `pending_reveal` entirely).
- Undo of the last action when `pending_reveal` is active (out of scope; user starts a new hand).
