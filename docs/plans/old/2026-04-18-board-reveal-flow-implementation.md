# Board Reveal Flow — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make flop/turn/river cards user-inputted via a blocking BoardPicker modal, with engine and API support. Design is frozen at [`2026-04-18-board-reveal-flow-design.md`](2026-04-18-board-reveal-flow-design.md).

**Architecture:** Engine gains `pending_reveal` + `reveals` fields. `_apply_street_transition` sets `pending_reveal` instead of auto-dealing from `deck_snapshot`. New `apply_reveal(state, cards)` extends the board, rewrites `deck_snapshot`, and clears the flag. A new `POST /api/engine/reveal` endpoint exposes this. Frontend mounts a `BoardPicker` modal whenever `state.pending_reveal !== null`. Terminal-state checks in `LiveCoach` and `PokerTable` are tightened to also require `pending_reveal === null`. Replay uses a new `replay(state)` helper that interleaves actions and reveals.

**Tech Stack:** Python + Pydantic + FastAPI (backend), React 19 + Vite + Tailwind 4 + vitest + Playwright (frontend), Hypothesis (property tests).

**Execution order:** one logical change per commit, each commit leaves the repo with `make test` green. Run `make lint` before the final commit.

---

## Phase 1 — Backend engine

### Task 1: Add `pending_reveal` and `reveals` fields to `GameState`

**Files:**
- Modify: `backend/src/poker_coach/engine/models.py:39-66`

**Step 1:** Add to `GameState` after `history`:

```python
pending_reveal: Literal["flop", "turn", "river", "runout"] | None = None
reveals: list[list[str]] = Field(default_factory=list)
```

**Step 2:** Run the full backend suite to confirm no regression.

Run: `cd backend && uv run pytest -q`
Expected: all existing tests pass (defaults are inert).

**Step 3:** Commit.

```bash
git add backend/src/poker_coach/engine/models.py
git commit -m "feat(engine): add pending_reveal and reveals fields to GameState"
```

---

### Task 2: Implement `apply_reveal` primitive + tests (TDD)

`apply_reveal` is a pure function that consumes `pending_reveal`, extends `state.board`, appends to `state.reveals`, rewrites `deck_snapshot`, and recomputes `state.to_act`. Not yet wired into `_apply_street_transition` — that happens in Task 3.

**Files:**
- Modify: `backend/src/poker_coach/engine/rules.py` (add `apply_reveal` + helper)
- Modify: `backend/tests/engine/test_rules.py` (append new test class)

**Step 1: Write failing tests.**

Append to `backend/tests/engine/test_rules.py`:

```python
class TestApplyReveal:
    def _state_with_pending(self, pending: str, board: list[str]) -> GameState:
        """Build a state in a pending_reveal mid-hand posture."""
        deck = [
            # hero, villain holes
            "As","Kd","Qc","Qh",
            # positions 4..8: initial flop/turn/river from seeded deck
            "2c","3d","4h","5s","6c",
            # rest irrelevant
            "7h","8d","9s","Tc","Jd","Qs","Kh","Ac","2s","3h","4d","5c","6d","7c",
            "8s","9h","Th","Jh","Qd","Kc","Ah","2h","3s","4c","5h","6h","7s","8h",
            "9d","Tc","Js","Jc","Kh","Ad","2d","3c",
        ][:52]
        s = start_hand(
            effective_stack=10_000,
            bb=100,
            button="hero",
            hero_hole=("As","Kd"),
            villain_hole=("Qc","Qh"),
            deck_snapshot=deck,
        )
        return s.model_copy(update={
            "pending_reveal": pending,
            "board": list(board),
            "street": {"flop":"flop","turn":"turn","river":"river","runout":"showdown"}[pending],
            "to_act": None,
        })

    def test_reveal_flop_sets_board_and_clears_flag(self) -> None:
        s = self._state_with_pending("flop", [])
        out = apply_reveal(s, ["Ah","Kh","Qh"])
        assert out.board == ["Ah","Kh","Qh"]
        assert out.pending_reveal is None
        assert out.reveals == [["Ah","Kh","Qh"]]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:7] == ["Ah","Kh","Qh"]

    def test_reveal_turn_appends_one_card(self) -> None:
        s = self._state_with_pending("turn", ["Ah","Kh","Qh"])
        out = apply_reveal(s, ["2s"])
        assert out.board == ["Ah","Kh","Qh","2s"]
        assert out.pending_reveal is None
        assert out.reveals == [["2s"]]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:8] == ["Ah","Kh","Qh","2s"]

    def test_reveal_runout_from_preflop_allin(self) -> None:
        s = self._state_with_pending("runout", [])
        out = apply_reveal(s, ["Ah","Kh","Qh","2s","3s"])
        assert out.board == ["Ah","Kh","Qh","2s","3s"]
        assert out.pending_reveal is None
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:9] == ["Ah","Kh","Qh","2s","3s"]

    def test_reveal_runout_from_flop_allin_expects_two_cards(self) -> None:
        s = self._state_with_pending("runout", ["Ah","Kh","Qh"])
        out = apply_reveal(s, ["2s","3s"])
        assert out.board == ["Ah","Kh","Qh","2s","3s"]
        assert out.deck_snapshot is not None
        assert out.deck_snapshot[4:9] == ["Ah","Kh","Qh","2s","3s"]

    def test_reveal_rejects_wrong_length(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Kh"])  # need 3
        s2 = self._state_with_pending("runout", ["Ah","Kh","Qh"])
        with pytest.raises(IllegalAction):
            apply_reveal(s2, ["2s","3s","4s"])  # need 2, got 3

    def test_reveal_rejects_duplicate_with_hero_hole(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["As","Kh","Qh"])  # As is hero_hole[0]

    def test_reveal_rejects_duplicate_with_villain_hole(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Qc","Kh","2s"])  # Qc is villain_hole[0]

    def test_reveal_rejects_duplicate_within_cards(self) -> None:
        s = self._state_with_pending("flop", [])
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Ah","Qh"])

    def test_reveal_rejects_when_no_pending(self) -> None:
        s = fresh_hand()  # preflop, no pending_reveal
        with pytest.raises(IllegalAction):
            apply_reveal(s, ["Ah","Kh","Qh"])
```

**Step 2:** Run tests to confirm they fail with "apply_reveal not defined".

Run: `cd backend && uv run pytest tests/engine/test_rules.py::TestApplyReveal -v`
Expected: FAIL with `NameError: name 'apply_reveal' is not defined`.

**Step 3:** Implement in `backend/src/poker_coach/engine/rules.py` (add after `_apply_street_transition`):

```python
_PENDING_EXPECTED_LEN = {
    "flop": 3,
    "turn": 1,
    "river": 1,
}


def _expected_reveal_len(state: GameState) -> int:
    pending = state.pending_reveal
    if pending is None:
        raise IllegalAction("no pending reveal")
    if pending == "runout":
        return 5 - len(state.board)
    return _PENDING_EXPECTED_LEN[pending]


def _swap_into_board_positions(deck: list[str], cards: list[str], start: int) -> list[str]:
    """Return a deck with `cards` placed at positions [start : start+len(cards)].

    Cards already present elsewhere in the deck get swapped to the positions the
    new cards vacated. Preserves the "52 unique cards" invariant.
    """
    new_deck = list(deck)
    for i, card in enumerate(cards):
        target = start + i
        if new_deck[target] == card:
            continue
        try:
            source = new_deck.index(card)
        except ValueError as exc:
            raise IllegalAction(f"card {card} not in deck_snapshot") from exc
        new_deck[target], new_deck[source] = new_deck[source], new_deck[target]
    return new_deck


def apply_reveal(state: GameState, cards: list[str]) -> GameState:
    """Consume `pending_reveal` by committing user-supplied board cards.

    Validates length, uniqueness (no dupes with holes or existing board, no
    dupes within `cards`), rewrites `deck_snapshot` so positions [4:4+len(board)]
    match the new board in order, and clears `pending_reveal`.
    """
    if state.pending_reveal is None:
        raise IllegalAction("no pending reveal")

    expected = _expected_reveal_len(state)
    if len(cards) != expected:
        raise IllegalAction(
            f"{state.pending_reveal} reveal expects {expected} cards, got {len(cards)}"
        )

    if len(set(cards)) != len(cards):
        raise IllegalAction(f"duplicate cards in reveal: {cards}")

    excluded: set[str] = set(state.hero_hole)
    if state.villain_hole is not None:
        excluded.update(state.villain_hole)
    excluded.update(state.board)
    clash = excluded.intersection(cards)
    if clash:
        raise IllegalAction(f"reveal duplicates existing cards: {sorted(clash)}")

    new_board = [*state.board, *cards]
    new_reveals = [*state.reveals, list(cards)]

    new_deck = state.deck_snapshot
    if new_deck is not None:
        new_deck = _swap_into_board_positions(new_deck, cards, start=4 + len(state.board))

    # to_act is recomputed by whoever next consumes the state. For a runout
    # reveal we are at showdown — to_act stays None. For flop/turn/river the
    # non-button seat acts first postflop (matches _apply_street_transition's
    # existing postflop logic).
    if state.street in ("showdown", "complete"):
        to_act: Seat | None = None
    else:
        to_act = other_seat(state.button)

    return state.model_copy(update={
        "board": new_board,
        "reveals": new_reveals,
        "pending_reveal": None,
        "deck_snapshot": new_deck,
        "to_act": to_act,
    })
```

**Step 4:** Run tests to verify pass.

Run: `cd backend && uv run pytest tests/engine/test_rules.py::TestApplyReveal -v`
Expected: all 9 tests PASS.

**Step 5:** Run full engine suite to verify nothing else broke.

Run: `cd backend && uv run pytest tests/engine -q`
Expected: all tests pass.

**Step 6:** Commit.

```bash
git add backend/src/poker_coach/engine/rules.py backend/tests/engine/test_rules.py
git commit -m "feat(engine): add apply_reveal for user-provided board cards"
```

---

### Task 3: Flip `_apply_street_transition` + update engine tests + rewrite invariants

Biggest task. The engine stops auto-dealing board cards and sets `pending_reveal` instead. Every test that played through a street transition must now insert an `apply_reveal` step. `apply_action` must refuse to run while `pending_reveal` is set. `legal_actions` must return `[]` in that state. Invariants 3, 4, 5 are rewritten to match the new contract.

**Files:**
- Modify: `backend/src/poker_coach/engine/rules.py` (`_apply_street_transition`, `apply_action` guard, `legal_actions` guard, add `replay(state)` helper)
- Modify: `backend/tests/engine/test_rules.py` (update `TestPostflop`, `TestAllIn`, add `fresh_to_flop` helper)
- Modify: `backend/tests/engine/test_invariants.py` (rewrite `played_hand`, `test_to_act_consistency`, `test_illegal_action_unreachable`, `test_replay_idempotency`, add `test_deck_snapshot_matches_board`)

**Step 1: Change the engine.** In `_apply_street_transition`, replace the block that deals board cards from `deck_snapshot` (lines 162-181 of current rules.py) with pending_reveal logic:

```python
def _apply_street_transition(state: GameState) -> GameState:
    new_committed = {"hero": 0, "villain": 0}
    new_pot = state.pot + sum(state.committed.values())

    street_order = ["preflop", "flop", "turn", "river", "showdown"]
    idx = street_order.index(state.street)
    next_street = street_order[idx + 1] if idx + 1 < len(street_order) else "complete"

    both_have_chips = state.stacks["hero"] > 0 and state.stacks["villain"] > 0

    pending_reveal: str | None = None
    if next_street in ("flop", "turn", "river"):
        pending_reveal = next_street
    if not both_have_chips and next_street not in ("showdown", "complete"):
        # Fast-forward to showdown; the remaining board is revealed as a runout
        # only if there are cards left to deal.
        next_street = "showdown"
        if len(state.board) < 5:
            pending_reveal = "runout"
        else:
            pending_reveal = None

    return state.model_copy(update={
        "street": next_street,
        "committed": new_committed,
        "pot": new_pot,
        "to_act": None,
        "last_aggressor": None,
        "last_raise_size": state.bb,
        "raises_open": True,
        "acted_this_street": frozenset(),
        "pending_reveal": pending_reveal,
    })
```

Note: `state.board` is no longer touched here. Remove the `deal_flop`/`deal_turn`/`deal_river` imports if they become unused (they stay used by existing deck helpers; check and leave if referenced elsewhere).

**Step 2:** Update `legal_actions` — add a guard at the top:

```python
def legal_actions(state: GameState) -> list[LegalAction]:
    if state.pending_reveal is not None:
        return []
    if state.street in ("showdown", "complete"):
        return []
    ...
```

**Step 3:** Update `apply_action` — add guard after the existing terminal check:

```python
def apply_action(state: GameState, action: Action) -> GameState:
    if state.street in ("showdown", "complete"):
        raise IllegalAction(f"hand already at {state.street}")
    if state.pending_reveal is not None:
        raise IllegalAction(f"pending reveal ({state.pending_reveal}) must be resolved first")
    ...
```

**Step 4: Add `replay(state)` helper in rules.py** (after `apply_reveal`):

```python
def replay(state: GameState) -> GameState:
    """Reconstruct `state` by replaying its history and reveals from the initial setup.

    Replaces the old `reduce(apply_action, history, initial_state)` form, which
    no longer converges because apply_action halts at pending_reveal.
    """
    s = initial_state(state)
    reveal_cursor = 0
    for action in state.history:
        s = apply_action(s, action)
        while s.pending_reveal is not None:
            if reveal_cursor >= len(state.reveals):
                raise AssertionError("history has pending reveal but no matching entry in state.reveals")
            s = apply_reveal(s, state.reveals[reveal_cursor])
            reveal_cursor += 1
    if reveal_cursor != len(state.reveals):
        raise AssertionError(
            f"unused reveals: consumed {reveal_cursor}, state has {len(state.reveals)}"
        )
    return s
```

**Step 5: Fix `TestPostflop` in `backend/tests/engine/test_rules.py`.**

The `_to_flop` helper needs to consume the flop reveal now. Update:

```python
class TestPostflop:
    _FLOP_CARDS = ["2c", "3d", "4h"]
    _TURN_CARD = "5s"
    _RIVER_CARD = "6c"

    def _to_flop(self) -> GameState:
        s = fresh_hand()
        s = apply_action(s, Action(actor="hero", type="call"))
        s = apply_action(s, Action(actor="villain", type="check"))
        assert s.street == "flop"
        assert s.pending_reveal == "flop"
        s = apply_reveal(s, self._FLOP_CARDS)
        assert s.pending_reveal is None
        assert s.board == self._FLOP_CARDS
        return s

    def test_check_check_advances_street(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="check"))
        s = apply_action(s, Action(actor="hero", type="check"))
        assert s.street == "turn"
        assert s.pending_reveal == "turn"
        s = apply_reveal(s, [self._TURN_CARD])
        assert len(s.board) == 4

    def test_bet_call_advances_street(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.street == "turn"
        assert s.pending_reveal == "turn"
        assert s.pot == 600
        assert s.committed == {"hero": 0, "villain": 0}

    def test_bet_fold_ends_hand(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="fold"))
        assert s.street == "complete"
        assert s.pending_reveal is None

    def test_bet_raise_call(self) -> None:
        s = self._to_flop()
        s = apply_action(s, Action(actor="villain", type="bet", to_amount=200))
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=600))
        s = apply_action(s, Action(actor="villain", type="call"))
        assert s.street == "turn"
        assert s.pending_reveal == "turn"
        assert s.pot == 1_400

    def test_min_bet_is_one_bb(self) -> None:
        s = self._to_flop()
        with pytest.raises(IllegalAction):
            apply_action(s, Action(actor="villain", type="bet", to_amount=50))
```

Import `apply_reveal` at the top of the file if not already.

**Step 6: Fix `TestAllIn`.**

```python
class TestAllIn:
    def test_short_allin_preflop_closes_raises(self) -> None:
        # unchanged — this test doesn't trigger a reveal
        ...

    def test_allin_call_fast_forwards_to_showdown(self) -> None:
        s = start_hand(effective_stack=1_000, bb=100, button="hero", rng_seed=3)
        s = apply_action(s, Action(actor="hero", type="raise", to_amount=300))
        s = apply_action(s, Action(actor="villain", type="allin"))
        assert s.to_act == "hero"
        s = apply_action(s, Action(actor="hero", type="call"))
        assert s.pot == 2_000
        assert s.stacks == {"hero": 0, "villain": 0}
        assert s.street == "showdown"
        assert s.pending_reveal == "runout"
        assert s.board == []  # no auto-deal
        # Reveal the full runout (5 cards) to finish
        s = apply_reveal(s, ["2c","3d","4h","5s","6c"])
        assert len(s.board) == 5
        assert s.pending_reveal is None

    def test_allin_both_equal_stacks(self) -> None:
        # Current test ends mid-hand; extend similarly with a reveal if it
        # asserts postflop state. Check the current body and adjust minimally.
        ...
```

Check the actual current bodies with `rg -n "class TestAllIn" backend/tests/engine/test_rules.py -A 40` and patch each test to `apply_reveal` where previously `len(s.board) == 5` or similar assertions were made without explicit reveals.

**Step 7: Update `backend/tests/engine/test_invariants.py`.**

Top of file — add imports:

```python
from poker_coach.engine.rules import (
    IllegalAction,
    apply_action,
    apply_reveal,
    initial_state,
    legal_actions,
    replay,
    start_hand,
)
```

Constants:

```python
STREET_ORDER = ["preflop", "flop", "turn", "river", "showdown", "complete"]
_RUNOUT_POOL = ["2c","3d","4h","5s","6c","7h","8d","9s","Tc","Jd","Qs","Kh","Ac"]
```

Update `played_hand`:

```python
def _safe_runout_cards(state: GameState, n: int) -> list[str]:
    """Pick n distinct cards not already in state.hero_hole / villain_hole / board."""
    excluded: set[str] = set(state.hero_hole)
    if state.villain_hole is not None:
        excluded.update(state.villain_hole)
    excluded.update(state.board)
    picked: list[str] = []
    for card in _RUNOUT_POOL:
        if len(picked) == n:
            break
        if card not in excluded and card not in picked:
            picked.append(card)
    if len(picked) < n:
        raise AssertionError("runout pool exhausted; add more cards")
    return picked


@st.composite
def played_hand(draw: st.DrawFn) -> list[GameState]:
    effective_stack = draw(st.integers(min_value=200, max_value=50_000))
    bb = draw(st.sampled_from([100, 200, 1_000]))
    if effective_stack <= bb:
        effective_stack = bb + bb
    button: Seat = draw(st.sampled_from(["hero", "villain"]))
    rng_seed = draw(st.integers(min_value=0, max_value=2**30))

    state = start_hand(
        effective_stack=effective_stack,
        bb=bb,
        button=button,
        rng_seed=rng_seed,
    )
    visited = [state]
    for _ in range(100):
        if state.street in ("showdown", "complete") and state.pending_reveal is None:
            break
        if state.pending_reveal is not None:
            need = 5 - len(state.board) if state.pending_reveal == "runout" else {
                "flop": 3, "turn": 1, "river": 1
            }[state.pending_reveal]
            state = apply_reveal(state, _safe_runout_cards(state, need))
            visited.append(state)
            continue
        action = _pick_action(draw, state)
        state = apply_action(state, action)
        visited.append(state)
    return visited
```

Rewrite invariants 3, 4, 5 and add the new deck_snapshot invariant:

```python
@given(states=played_hand())
def test_to_act_consistency(states: list[GameState]) -> None:
    for state in states:
        if state.street in ("showdown", "complete") or state.pending_reveal is not None:
            assert state.to_act is None
            assert legal_actions(state) == []
        else:
            assert state.to_act is not None
            assert legal_actions(state), f"no legal actions for {state.to_act} at {state.street}"


@given(states=played_hand())
def test_illegal_action_unreachable(states: list[GameState]) -> None:
    for state in states:
        if state.street in ("showdown", "complete") or state.pending_reveal is not None:
            continue
        legal_types = {la.type for la in legal_actions(state)}
        all_types = {"fold", "check", "call", "bet", "raise", "allin"}
        for illegal_type in all_types - legal_types:
            try:
                apply_action(
                    state,
                    Action(actor=state.to_act, type=illegal_type),  # type: ignore[arg-type]
                )
            except IllegalAction:
                continue
            raise AssertionError(f"illegal action {illegal_type} was accepted at {state.street}")


@given(states=played_hand())
def test_replay_idempotency(states: list[GameState]) -> None:
    final = states[-1]
    assert replay(final) == final


@given(states=played_hand())
def test_deck_snapshot_matches_board(states: list[GameState]) -> None:
    for state in states:
        if state.deck_snapshot is None:
            continue
        board_len = len(state.board)
        assert state.deck_snapshot[4 : 4 + board_len] == state.board, (
            f"deck_snapshot[4:{4+board_len}] != state.board at {state.street}"
        )
```

Remove the old `reduce` import (`from functools import reduce`) if unused after the rewrite.

**Step 8: Run the full backend test suite.**

Run: `cd backend && uv run pytest -q`
Expected: all tests pass. If Hypothesis finds a counterexample, add it to the plan and fix before committing.

**Step 9: Commit.**

```bash
git add backend/src/poker_coach/engine/rules.py backend/tests/engine/test_rules.py backend/tests/engine/test_invariants.py
git commit -m "feat(engine): switch street transitions to pending_reveal (breaks auto-deal from deck_snapshot)"
```

---

### Task 4: Add `POST /api/engine/reveal` endpoint

**Files:**
- Modify: `backend/src/poker_coach/api/routes/engine.py` (add request model + route)
- Modify: `backend/tests/api/test_engine_routes.py` (add tests)

**Step 1: Write failing tests.**

Add to `backend/tests/api/test_engine_routes.py` (check the existing file shape first with `cat` to match the fixture style):

```python
def test_reveal_flop_returns_updated_snapshot(api_app):
    client = TestClient(api_app)
    # Start a hand, take hero call + villain check to close preflop → pending_reveal="flop"
    start = client.post("/api/engine/start", json={
        "effective_stack": 10_000, "bb": 100, "button": "hero",
        "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
    }).json()
    s = client.post("/api/engine/apply", json={
        "state": start["state"], "action": {"actor":"hero","type":"call"},
    }).json()
    s = client.post("/api/engine/apply", json={
        "state": s["state"], "action": {"actor":"villain","type":"check"},
    }).json()
    assert s["state"]["pending_reveal"] == "flop"

    # Reveal
    r = client.post("/api/engine/reveal", json={
        "state": s["state"], "cards": ["2c","3d","4h"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["state"]["pending_reveal"] is None
    assert body["state"]["board"] == ["2c","3d","4h"]
    assert len(body["legal_actions"]) > 0


def test_reveal_rejects_wrong_length(api_app):
    client = TestClient(api_app)
    start = client.post("/api/engine/start", json={
        "effective_stack": 10_000, "bb": 100, "button": "hero",
        "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
    }).json()
    s = client.post("/api/engine/apply", json={
        "state": start["state"], "action": {"actor":"hero","type":"call"},
    }).json()
    s = client.post("/api/engine/apply", json={
        "state": s["state"], "action": {"actor":"villain","type":"check"},
    }).json()
    r = client.post("/api/engine/reveal", json={
        "state": s["state"], "cards": ["2c","3d"],
    })
    assert r.status_code == 400


def test_reveal_rejects_when_no_pending(api_app):
    client = TestClient(api_app)
    start = client.post("/api/engine/start", json={
        "effective_stack": 10_000, "bb": 100, "button": "hero",
        "hero_hole": ["As","Kd"], "villain_hole": ["Qc","Qh"],
    }).json()
    r = client.post("/api/engine/reveal", json={
        "state": start["state"], "cards": ["2c","3d","4h"],
    })
    assert r.status_code == 400
```

**Step 2:** Run tests — they should fail with 404 (route not defined).

Run: `cd backend && uv run pytest tests/api/test_engine_routes.py -v -k reveal`

**Step 3: Implement the route** in `backend/src/poker_coach/api/routes/engine.py`:

```python
from poker_coach.engine.rules import IllegalAction, apply_action, apply_reveal, legal_actions, start_hand

class RevealRequest(BaseModel):
    state: GameState
    cards: list[str]


@router.post("/engine/reveal", response_model=EngineSnapshot)
def reveal(body: RevealRequest) -> EngineSnapshot:
    try:
        new_state = apply_reveal(body.state, body.cards)
    except IllegalAction as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EngineSnapshot(state=new_state, legal_actions=legal_actions(new_state))
```

**Step 4:** Run tests.

Run: `cd backend && uv run pytest tests/api/test_engine_routes.py -v -k reveal`
Expected: PASS.

**Step 5:** Commit.

```bash
git add backend/src/poker_coach/api/routes/engine.py backend/tests/api/test_engine_routes.py
git commit -m "feat(api): add POST /engine/reveal endpoint"
```

---

## Phase 2 — Frontend

### Task 5: Update TypeScript `GameState` type

**Files:**
- Modify: `frontend/src/api/types.ts:25-45`

**Step 1:** Add to `GameState`:

```ts
pending_reveal: "flop" | "turn" | "river" | "runout" | null;
reveals: string[][];
```

**Step 2:** Run `cd frontend && npx tsc --noEmit` to verify nothing downstream breaks. Any file that reads `GameState` should still compile — the new fields have no consumers yet.

**Step 3:** Commit.

```bash
git add frontend/src/api/types.ts
git commit -m "feat(types): add pending_reveal and reveals to GameState"
```

---

### Task 6: Add `engineReveal` API client method

**Files:**
- Modify: `frontend/src/api/client.ts`

**Step 1:** Add after `engineApply`:

```ts
export async function engineReveal(state: GameState, cards: string[]): Promise<EngineSnapshot> {
  return postJSON("/api/engine/reveal", { state, cards });
}
```

**Step 2:** `cd frontend && npx tsc --noEmit` — should pass.

**Step 3:** Commit.

```bash
git add frontend/src/api/client.ts
git commit -m "feat(client): add engineReveal helper"
```

---

### Task 7: Create `BoardPicker` component with vitest coverage

**Files:**
- Create: `frontend/src/components/BoardPicker.tsx`
- Create: `frontend/src/components/BoardPicker.test.tsx`

**Design notes:**
- Props: `{ street: "flop"|"turn"|"river"|"runout", existingBoard: string[], excludedCards: string[], onConfirm: (cards: string[]) => void }`.
- Derives `expectedLen` from `street` and `existingBoard.length` (runout: `5 - existingBoard.length`).
- Renders N editable slots. Locked slots on the left showing `existingBoard` for turn/river/runout-mid-hand.
- Uses the same rank/suit grid as `CardPicker` — duplicate the grid code for V1 (no shared primitive). Exclude `excludedCards` + locally-picked-cards from the grid (disabled).
- Modal layout: fixed overlay, centered card. `data-testid="board-picker"`.

**Step 1: Write the component tests.**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BoardPicker } from "./BoardPicker";

describe("BoardPicker", () => {
  it("renders 3 slots for flop", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(3);
  });

  it("renders 1 slot for turn with 3 locked flop cards", () => {
    render(
      <BoardPicker
        street="turn"
        existingBoard={["2c","3d","4h"]}
        excludedCards={["As","Kd","2c","3d","4h"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(1);
    expect(screen.getAllByTestId(/^board-locked-/)).toHaveLength(3);
  });

  it("renders 5 slots for runout from preflop all-in", () => {
    render(
      <BoardPicker
        street="runout"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(5);
  });

  it("renders 2 slots for runout from flop all-in", () => {
    render(
      <BoardPicker
        street="runout"
        existingBoard={["2c","3d","4h"]}
        excludedCards={["As","Kd","2c","3d","4h"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(2);
  });

  it("Confirm button disabled until all slots filled", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByTestId("board-picker-confirm")).toBeDisabled();
  });

  it("calls onConfirm with the picked cards in order", () => {
    const onConfirm = vi.fn();
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId("board-grid-Ah"));
    fireEvent.click(screen.getByTestId("board-grid-Kh"));
    fireEvent.click(screen.getByTestId("board-grid-Qh"));
    fireEvent.click(screen.getByTestId("board-picker-confirm"));
    expect(onConfirm).toHaveBeenCalledWith(["Ah","Kh","Qh"]);
  });

  it("hides excluded cards from the grid", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    // Excluded cards should be disabled (not clickable) or absent
    const asBtn = screen.queryByTestId("board-grid-As");
    // Allow either "absent" or "disabled"; assert it's not clickable.
    if (asBtn) expect(asBtn).toBeDisabled();
  });
});
```

**Step 2: Run to confirm they fail** (component doesn't exist).

Run: `cd frontend && npx vitest run src/components/BoardPicker.test.tsx`
Expected: FAIL with "Cannot find module './BoardPicker'".

**Step 3: Implement `BoardPicker.tsx`.** Model the grid code after `CardPicker.tsx` but with the reveal-specific shape. Key logic:

```tsx
import { useMemo, useState } from "react";
import { PlayingCard } from "./PlayingCard";

const RANKS = ["A","K","Q","J","T","9","8","7","6","5","4","3","2"] as const;
const SUITS = ["s","h","d","c"] as const;

const HEADERS: Record<string, string> = {
  flop: "Révèle le flop",
  turn: "Révèle le turn",
  river: "Révèle la river",
  runout: "Révèle le run-out (all-in)",
};

export function BoardPicker({
  street,
  existingBoard,
  excludedCards,
  onConfirm,
}: {
  street: "flop" | "turn" | "river" | "runout";
  existingBoard: string[];
  excludedCards: string[];
  onConfirm: (cards: string[]) => void;
}) {
  const expectedLen = useMemo(() => {
    if (street === "runout") return 5 - existingBoard.length;
    return street === "flop" ? 3 : 1;
  }, [street, existingBoard.length]);

  const [slots, setSlots] = useState<(string | null)[]>(() =>
    Array.from({ length: expectedLen }, () => null),
  );
  const [activeIdx, setActiveIdx] = useState<number>(0);

  const used = useMemo(
    () => new Set([...excludedCards, ...slots.filter((x): x is string => x != null)]),
    [excludedCards, slots],
  );

  const allFilled = slots.every((x) => x != null);

  const pickCard = (code: string) => {
    if (used.has(code) && slots[activeIdx] !== code) return;
    const next = [...slots];
    next[activeIdx] = code;
    setSlots(next);
    const nextEmpty = next.findIndex((x) => x == null);
    if (nextEmpty >= 0) setActiveIdx(nextEmpty);
  };

  const confirm = () => {
    if (!allFilled) return;
    onConfirm(slots.filter((x): x is string => x != null));
  };

  return (
    <div
      data-testid="board-picker"
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
    >
      <div className="bg-stone-900 rounded-2xl p-6 ring-1 ring-white/10 max-w-2xl w-full flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-stone-100">{HEADERS[street]}</h2>

        <div className="flex items-center gap-3 flex-wrap">
          {existingBoard.map((c, i) => (
            <div key={`locked-${i}`} data-testid={`board-locked-${i}`} className="opacity-60">
              <PlayingCard code={c} size="md" />
            </div>
          ))}
          {existingBoard.length > 0 && slots.length > 0 && (
            <div className="w-px h-14 bg-white/10" />
          )}
          {slots.map((code, i) => (
            <button
              key={`slot-${i}`}
              data-testid={`board-slot-${i}`}
              onClick={() => setActiveIdx(i)}
              className={`rounded-md p-0.5 transition ${
                activeIdx === i
                  ? "ring-2 ring-amber-400 shadow-lg shadow-amber-500/30"
                  : "ring-1 ring-white/10 hover:ring-white/30"
              }`}
            >
              {code ? (
                <PlayingCard code={code} size="md" />
              ) : (
                <div className="w-12 h-16 rounded-md border-2 border-dashed border-white/20" />
              )}
            </button>
          ))}
        </div>

        <div
          className="grid gap-1 bg-stone-950 rounded-lg p-2 ring-1 ring-white/5"
          style={{ gridTemplateColumns: `auto repeat(${RANKS.length}, minmax(0, 1fr))` }}
        >
          {SUITS.map((suit) => (
            <SuitRow key={suit} suit={suit} used={used} onPick={pickCard} />
          ))}
        </div>

        <button
          data-testid="board-picker-confirm"
          onClick={confirm}
          disabled={!allFilled}
          className="self-end px-4 py-2 rounded-md bg-amber-500 text-stone-950 font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-400 transition"
        >
          Confirmer
        </button>
      </div>
    </div>
  );
}

function SuitRow({
  suit,
  used,
  onPick,
}: {
  suit: (typeof SUITS)[number];
  used: Set<string>;
  onPick: (code: string) => void;
}) {
  const glyph = suit === "s" ? "♠" : suit === "h" ? "♥" : suit === "d" ? "♦" : "♣";
  const color = suit === "h" || suit === "d" ? "text-red-400" : "text-stone-200";
  return (
    <>
      <div className={`flex items-center justify-center text-lg pr-1 ${color}`} aria-hidden>
        {glyph}
      </div>
      {RANKS.map((rank) => {
        const code = rank + suit;
        const isUsed = used.has(code);
        return (
          <button
            key={code}
            data-testid={`board-grid-${code}`}
            disabled={isUsed}
            onClick={() => onPick(code)}
            className={`aspect-[5/7] rounded ${
              isUsed ? "opacity-30 cursor-not-allowed" : "hover:scale-110 hover:z-10 transition-transform"
            }`}
          >
            <PlayingCard code={code} size="sm" />
          </button>
        );
      })}
    </>
  );
}
```

**Step 4:** Run tests.

Run: `cd frontend && npx vitest run src/components/BoardPicker.test.tsx`
Expected: all 7 tests PASS.

**Step 5:** Commit.

```bash
git add frontend/src/components/BoardPicker.tsx frontend/src/components/BoardPicker.test.tsx
git commit -m "feat(ui): add BoardPicker component for user-input flop/turn/river/runout"
```

---

### Task 8: Wire BoardPicker into LiveCoach + fix `handComplete`

**Files:**
- Modify: `frontend/src/routes/LiveCoach.tsx` (add reveal handler, mount modal, fix `handComplete`)

**Step 1:** Add import:

```ts
import { engineReveal, /* existing imports */ } from "../api/client";
import { BoardPicker } from "../components/BoardPicker";
```

**Step 2:** Add handler (after `applyAction`):

```ts
const applyReveal = useCallback(
  async (cards: string[]) => {
    if (!snapshot) return;
    try {
      const next = await engineReveal(snapshot.state, cards);
      setSnapshot(next);
    } catch (err) {
      setError(String(err));
    }
  },
  [snapshot],
);
```

**Step 3:** Fix `handComplete`:

```ts
const handComplete = useMemo(() => {
  if (!snapshot) return false;
  if (snapshot.state.pending_reveal !== null) return false;
  return snapshot.state.street === "complete" || snapshot.state.street === "showdown";
}, [snapshot]);
```

**Step 4:** Mount modal in the render. Inside the `{snapshot && (...)}` block, above or below the `<PokerTable>` but inside the outer flex container so it overlays correctly:

```tsx
{snapshot.state.pending_reveal !== null && (
  <BoardPicker
    street={snapshot.state.pending_reveal}
    existingBoard={snapshot.state.board}
    excludedCards={[
      ...snapshot.state.hero_hole,
      ...(snapshot.state.villain_hole ?? []),
      ...snapshot.state.board,
    ]}
    onConfirm={applyReveal}
  />
)}
```

**Step 5:** Run frontend typecheck + existing tests.

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: all pass.

**Step 6:** Commit.

```bash
git add frontend/src/routes/LiveCoach.tsx
git commit -m "feat(live-coach): mount BoardPicker on pending_reveal, gate handComplete"
```

---

### Task 9: Fix `PokerTable` terminal check for villain reveal

**Files:**
- Modify: `frontend/src/components/PokerTable.tsx:7`

**Step 1:** Change:

```tsx
const showVillainHole = state.street === "showdown" || state.street === "complete";
```

to:

```tsx
const showVillainHole =
  state.pending_reveal === null &&
  (state.street === "showdown" || state.street === "complete");
```

**Step 2:** Run `cd frontend && npx tsc --noEmit && npx vitest run`. Expected: green.

**Step 3:** Commit.

```bash
git add frontend/src/components/PokerTable.tsx
git commit -m "fix(poker-table): only expose villain hole after pending_reveal resolves"
```

---

## Phase 3 — Integration tests + docs

### Task 10: Extend Playwright `live-coach.spec.ts` with reveal scenarios

**Files:**
- Modify: `frontend/e2e/live-coach.spec.ts`

**Step 1:** Add a second test case that plays preflop call/check, expects the BoardPicker modal, fills the flop, and continues. Then a third test for preflop all-in → runout picker. Keep the existing happy-path test intact.

Example shape (confirm exact selectors against current spec):

```ts
test("reveals flop after preflop closes", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("start-hand").click();
  // ... preflop actions to close the street (hero call, villain check)
  await expect(page.getByTestId("board-picker")).toBeVisible();
  await page.getByTestId("board-grid-2c").click();
  await page.getByTestId("board-grid-3d").click();
  await page.getByTestId("board-grid-4h").click();
  await page.getByTestId("board-picker-confirm").click();
  await expect(page.getByTestId("board-picker")).toBeHidden();
  await expect(page.getByTestId("action-bar")).toBeVisible();
});
```

Pull the real selector names by reading `frontend/src/components/ActionBar.tsx` for `data-testid` usage before writing the test.

**Step 2:** Start dev servers and run playwright:

```bash
make dev  # in one shell
cd frontend && npx playwright test live-coach.spec.ts
```

Expected: all scenarios green.

**Step 3:** Commit.

```bash
git add frontend/e2e/live-coach.spec.ts
git commit -m "test(e2e): cover board reveal flow in live-coach spec"
```

---

### Task 11: Update CLAUDE.md load-bearing gotchas

**Files:**
- Modify: `CLAUDE.md`

**Step 1:** After gotcha #6 (CardPicker uncontrolled), add:

```markdown
7. **`deck_snapshot` is rewritten by `/engine/reveal` to reflect user-supplied board cards.** Any code reading `deck_snapshot[4:9]` for anything other than replay reconstruction must read `state.board` instead. Treat `deck_snapshot` positions beyond `[0:4]` (hero + villain holes) as implementation detail of replay, not a reliable source of board cards.
```

Also update the engine-invariants section (invariant 3) to reflect the new contract:

> 3. `to_act` consistency: `to_act` is set iff the hand is in progress **AND** `pending_reveal is None`. When `pending_reveal is not None`, `to_act is None` and `legal_actions(state) == []`. Hand progresses only after `apply_reveal` consumes the pending cards.

**Step 2:** Commit.

```bash
git add CLAUDE.md
git commit -m "docs: add deck_snapshot / pending_reveal gotchas to CLAUDE.md"
```

---

## Phase 4 — Final sweep

### Task 12: Full lint + tests + smoke

**Step 1:** Run the lint gates.

Run: `make lint`
Expected: ruff + format + mypy-strict + eslint + tsc all green. Fix anything that surfaces (typically: unused imports in `rules.py` from the deck helpers no longer called in `_apply_street_transition`).

**Step 2:** Run the full test suite.

Run: `make test`
Expected: all pytest + vitest green.

**Step 3:** Run end-to-end once more.

Run: `make e2e`
Expected: all playwright green.

**Step 4:** Manual smoke test.

```bash
make dev
```
- Start a hand, play preflop (`call` → `check`) — expect BoardPicker for flop.
- Fill flop, confirm — expect ActionBar postflop.
- Play flop (`bet` → `call`) — expect turn picker.
- Continue through river to showdown.
- Start another hand, go preflop all-in (both players) — expect runout picker with 5 slots; fill and confirm; expect HandSummary.
- Verify villain hole cards are NOT visible while the runout picker is open.
- Verify advice flow works postflop (request advice → stream → apply hero action).

**Step 5:** If smoke is clean, no commit — plan complete.

---

## Commit sequence summary

```
feat(engine): add pending_reveal and reveals fields to GameState
feat(engine): add apply_reveal for user-provided board cards
feat(engine): switch street transitions to pending_reveal (breaks auto-deal from deck_snapshot)
feat(api): add POST /engine/reveal endpoint
feat(types): add pending_reveal and reveals to GameState
feat(client): add engineReveal helper
feat(ui): add BoardPicker component for user-input flop/turn/river/runout
feat(live-coach): mount BoardPicker on pending_reveal, gate handComplete
fix(poker-table): only expose villain hole after pending_reveal resolves
test(e2e): cover board reveal flow in live-coach spec
docs: add deck_snapshot / pending_reveal gotchas to CLAUDE.md
```

Each commit leaves `make test` green. Task 3 is the single commit that breaks and then re-greens test_rules.py / test_invariants.py in one shot.

---

## Skills to use during execution

- **superpowers:test-driven-development** — mandatory for Tasks 2, 4, 7 (write test → red → implement → green → commit).
- **superpowers:verification-before-completion** — before claiming any task done, run the exact commands in that task's Step N and confirm expected output.
- **codex:rescue** — if stuck for more than a few minutes on a specific task, hand it off with the task number + symptom.
