# ActionBar Pro Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `frontend/src/components/ActionBar.tsx` to match the UX of top poker sites (PokerStars / GGPoker / WPT Global): a bet-sizing slider with tick marks at presets, flanking `−` / `+` nudge buttons, a prominent amount readout in bb, and a 3-column action-button grid whose primary button embeds the bet amount. Same polished UI on hero turns and villain-record turns.

**Architecture:** Split the ActionBar into two files — a pure `sizing.ts` module (presets + clamp + fire-type resolution), unit-tested in isolation, and the visual `ActionBar.tsx` that composes the sizing helpers with React state. No hotkeys in ActionBar; `useHotkeys` hook stays alive for `LiveCoach.tsx` callers. Slider uses a native `<input type="range">` for accessibility with a visual overlay. Integer chips are the source of truth; bb is display-only.

**Reset strategy:** `sizeChips` is component-local state. Because `LiveCoach.tsx:249` re-renders the same `ActionBar` instance across hero→villain and street transitions, a stale `sizeChips` from the previous spot would bleed into the next one — for example, a 3bb open sticking around when the new spot's min-raise is 5bb, causing an `IllegalAction` on the backend. We fix this two ways:

1. **Parent remount via `key`** (primary): `LiveCoach.tsx` passes `key={\`${hand_id}:${history.length}:${to_act}\`}` so every spot transition unmounts the old ActionBar and mounts a fresh one with `sizeChips = sizingLegal.min_to`. This is the same pattern CLAUDE.md gotcha #6 prescribes for `CardPicker`.
2. **Defensive clamp in `resolveFireType`** (belt-and-suspenders): the fire path always clamps `sizeChips` into `[min_to, max_to]` before dispatching, so even if a bug leaks a stale value past the remount, the backend never sees an illegal amount.

**Call semantics:** the backend's `LegalAction(type="call")` carries no `min_to`/`max_to` (see `backend/src/poker_coach/engine/models.py:25-30` and `rules.py:111-114`); the call amount is derived from state — specifically `state.committed[opponent] - state.committed[actor]` (the delta to put in) or `state.committed[opponent]` (the to-amount). The dispatched `Action.to_amount` is `null` for call. The Call button label uses the delta derived from state, not any field on the `LegalAction`.

**Tech Stack:** React 18, Tailwind 4, TypeScript, Vitest + React Testing Library, Playwright.

---

## Pre-flight

Read these before starting:

- `frontend/src/components/ActionBar.tsx` — current component being replaced.
- `frontend/src/api/types.ts` — `GameState`, `LegalAction`, `Action`, `ActionType`, `Seat` shapes.
- `frontend/src/routes/LiveCoach.tsx:247-265` — how ActionBar is wired (`heroAction` / `applyAction`, `requestAdvice`, `adviceDisabled`).
- `frontend/src/hooks/useHotkeys.ts` — hook stays, but ActionBar no longer uses it. `LiveCoach.tsx:195` still uses it.
- `frontend/e2e/live-coach.spec.ts:45-47` — uses `size-input` which disappears; must be updated.
- `frontend/src/components/PlayingCard.test.tsx` — test-file style reference.

Run the existing test baseline once so you know the starting state:

```sh
cd frontend && npm run test && cd ..
```

Expected: all tests pass (no ActionBar tests exist yet).

---

## Task 1: Extract sizing helpers into a pure module

**Files:**
- Create: `frontend/src/components/actionBar/sizing.ts`

**Step 1: Write the module**

Create `frontend/src/components/actionBar/sizing.ts`:

```ts
import type { ActionType, GameState, LegalAction } from "../../api/types";

export interface Preset {
  label: string;
  toChips: number;
  kind: "min" | "ratio" | "max";
}

export type SizeableType = "bet" | "raise";

export interface LegalByType {
  fold?: LegalAction;
  check?: LegalAction;
  call?: LegalAction;
  bet?: LegalAction;
  raise?: LegalAction;
  allin?: LegalAction;
}

export function legalByType(legal: LegalAction[]): LegalByType {
  return Object.fromEntries(legal.map((l) => [l.type, l])) as LegalByType;
}

export function sizeableType(lbt: LegalByType): SizeableType | null {
  if (lbt.raise) return "raise";
  if (lbt.bet) return "bet";
  return null;
}

export function clampChips(chips: number, la: LegalAction): number {
  if (la.min_to == null || la.max_to == null) return chips;
  if (chips < la.min_to) return la.min_to;
  if (chips > la.max_to) return la.max_to;
  return Math.round(chips);
}

export function bbToChips(bb: number, state: GameState): number {
  return Math.round(bb * state.bb);
}

export function chipsToBb(chips: number, state: GameState): number {
  return chips / state.bb;
}

// Snap-to-chip presets for the given street. All returned presets are clamped
// into [min_to, max_to]; any that would collapse onto min (other than `min`
// itself) are deduped.
export function getPresets(state: GameState, la: LegalAction): Preset[] {
  if (la.min_to == null || la.max_to == null) return [];
  const min = la.min_to;
  const max = la.max_to;
  const raw: Preset[] =
    state.street === "preflop"
      ? [
          { label: "min", toChips: min, kind: "min" },
          { label: "2.5x", toChips: bbToChips(2.5, state), kind: "ratio" },
          { label: "3x", toChips: bbToChips(3, state), kind: "ratio" },
          { label: "3.5x", toChips: bbToChips(3.5, state), kind: "ratio" },
        ]
      : postflopRaw(state, la);
  const filtered = raw
    .map((p) => ({ ...p, toChips: clampChips(p.toChips, la) }))
    .filter((p, i, arr) =>
      p.kind === "min" ? true : arr.findIndex((q) => q.toChips === p.toChips) === i,
    );
  return [...filtered, { label: "max", toChips: max, kind: "max" }];
}

function postflopRaw(state: GameState, la: LegalAction): Preset[] {
  const pot = state.pot + state.committed.hero + state.committed.villain;
  const actorCommitted =
    state.to_act === "hero" ? state.committed.hero : state.committed.villain;
  const min = la.min_to!;
  return [
    { label: "min", toChips: min, kind: "min" },
    { label: "33%", toChips: actorCommitted + Math.round(pot * 0.33), kind: "ratio" },
    { label: "50%", toChips: actorCommitted + Math.round(pot * 0.5), kind: "ratio" },
    { label: "75%", toChips: actorCommitted + Math.round(pot * 0.75), kind: "ratio" },
    { label: "pot", toChips: actorCommitted + pot, kind: "ratio" },
    { label: "1.5x", toChips: actorCommitted + Math.round(pot * 1.5), kind: "ratio" },
  ];
}

// Resolves the ActionType + to_amount to dispatch when the user confirms the
// sizing. If the sizing hits the max AND `allin` is legal, prefer `allin`.
// Defensive clamp: even if the caller's `sizeChips` is stale and below min_to
// (e.g. because the legal min changed between renders), the dispatched amount
// is clamped into [min_to, max_to] so the backend never sees an IllegalAction.
export function resolveFireType(
  sizeChips: number,
  lbt: LegalByType,
): { type: ActionType; to: number } | null {
  const s = sizeableType(lbt);
  if (!s) return null;
  const la = lbt[s]!;
  if (la.max_to == null || la.min_to == null) return null;
  const clamped = clampChips(sizeChips, la);
  if (clamped >= la.max_to && lbt.allin?.max_to != null) {
    return { type: "allin", to: lbt.allin.max_to };
  }
  return { type: s, to: clamped };
}

export function potForDisplay(state: GameState): number {
  return state.pot + state.committed.hero + state.committed.villain;
}

// Pot-ratio % for the amount the actor would *add* beyond what's already
// committed. Returns null preflop (ratio framing is not useful preflop).
export function sizingPotPct(
  sizeChips: number,
  state: GameState,
): number | null {
  if (state.street === "preflop") return null;
  const pot = potForDisplay(state);
  if (pot === 0) return null;
  const actorCommitted =
    state.to_act === "hero" ? state.committed.hero : state.committed.villain;
  const delta = sizeChips - actorCommitted;
  return (delta / pot) * 100;
}
```

**Step 2: Commit**

```sh
git add frontend/src/components/actionBar/sizing.ts
git commit -m "feat(frontend): extract ActionBar sizing helpers into pure module"
```

---

## Task 2: Unit tests for sizing helpers

**Files:**
- Create: `frontend/src/components/actionBar/sizing.test.ts`

**Step 1: Write the tests**

```ts
import { describe, expect, it } from "vitest";
import {
  clampChips,
  getPresets,
  legalByType,
  resolveFireType,
  sizingPotPct,
} from "./sizing";
import type { GameState, LegalAction } from "../../api/types";

function baseState(overrides: Partial<GameState> = {}): GameState {
  return {
    hand_id: "h",
    bb: 100,
    effective_stack: 10000,
    button: "hero",
    hero_hole: ["As", "Kd"],
    villain_hole: null,
    board: [],
    street: "preflop",
    stacks: { hero: 10000, villain: 10000 },
    committed: { hero: 50, villain: 100 },
    pot: 0,
    to_act: "hero",
    last_aggressor: "villain",
    last_raise_size: 100,
    raises_open: true,
    acted_this_street: [],
    history: [],
    rng_seed: null,
    deck_snapshot: null,
    pending_reveal: null,
    reveals: [],
    ...overrides,
  };
}

describe("clampChips", () => {
  it("clamps below min up to min", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(50, la)).toBe(200);
  });

  it("clamps above max down to max", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(20000, la)).toBe(10000);
  });

  it("rounds to integer chips", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(250.6, la)).toBe(251);
  });
});

describe("getPresets preflop", () => {
  it("produces min, ratios, and max", () => {
    const state = baseState();
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    const presets = getPresets(state, la);
    expect(presets.map((p) => p.label)).toEqual(["min", "2.5x", "3x", "3.5x", "max"]);
    expect(presets[0].toChips).toBe(200);
    expect(presets[1].toChips).toBe(250);
    expect(presets[2].toChips).toBe(300);
    expect(presets[3].toChips).toBe(350);
    expect(presets.at(-1)!.toChips).toBe(10000);
  });

  it("clamps ratio presets that fall below min to the min value (dedup removes them)", () => {
    const state = baseState();
    // min_to=400 wipes out 2.5x=250 and 3x=300 and 3.5x=350 — they all clamp
    // to 400 which matches `min`, so they dedup away.
    const la: LegalAction = { type: "raise", min_to: 400, max_to: 10000 };
    const labels = getPresets(state, la).map((p) => p.label);
    expect(labels).toEqual(["min", "max"]);
  });
});

describe("getPresets postflop", () => {
  it("computes ratios off pot + committed", () => {
    const state = baseState({
      street: "flop",
      pot: 600,
      committed: { hero: 0, villain: 0 },
      to_act: "hero",
    });
    const la: LegalAction = { type: "bet", min_to: 100, max_to: 10000 };
    const presets = getPresets(state, la);
    expect(presets.map((p) => p.label)).toEqual([
      "min", "33%", "50%", "75%", "pot", "1.5x", "max",
    ]);
    expect(presets.find((p) => p.label === "pot")!.toChips).toBe(600);
    expect(presets.find((p) => p.label === "75%")!.toChips).toBe(450);
  });
});

describe("resolveFireType", () => {
  it("returns raise when not at max", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(300, lbt)).toEqual({ type: "raise", to: 300 });
  });

  it("returns allin when sizing is at or above max and allin is legal", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(10000, lbt)).toEqual({ type: "allin", to: 10000 });
  });

  it("returns bet when only bet is legal", () => {
    const lbt = legalByType([{ type: "bet", min_to: 100, max_to: 10000 }]);
    expect(resolveFireType(500, lbt)).toEqual({ type: "bet", to: 500 });
  });

  it("returns null when nothing is sizeable", () => {
    // call and fold carry no min_to/max_to — the call amount is derived from state.
    const lbt = legalByType([{ type: "fold" }, { type: "call" }]);
    expect(resolveFireType(500, lbt)).toBeNull();
  });

  it("clamps a below-min stale size up to min_to before dispatching", () => {
    // Guards against sizeChips bleeding across spot transitions (e.g. hero
    // opens 3bb, new min raise for the next spot is 5bb, and the stale 3bb
    // would otherwise crash the backend with IllegalAction).
    const lbt = legalByType([
      { type: "raise", min_to: 500, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(300, lbt)).toEqual({ type: "raise", to: 500 });
  });

  it("clamps an above-max size down to max_to and routes to allin", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(99999, lbt)).toEqual({ type: "allin", to: 10000 });
  });
});

describe("sizingPotPct", () => {
  it("returns null preflop", () => {
    expect(sizingPotPct(500, baseState())).toBeNull();
  });

  it("computes pct of pot for the delta", () => {
    const state = baseState({
      street: "flop",
      pot: 600,
      committed: { hero: 0, villain: 0 },
      to_act: "hero",
    });
    expect(sizingPotPct(300, state)).toBe(50);
  });
});
```

**Step 2: Run tests and verify they pass**

```sh
cd frontend && npx vitest run src/components/actionBar/sizing.test.ts && cd ..
```

Expected: all tests pass.

**Step 3: Commit**

```sh
git add frontend/src/components/actionBar/sizing.test.ts
git commit -m "test(frontend): unit tests for ActionBar sizing helpers"
```

---

## Task 3: Rewrite ActionBar — component tests first

**Files:**
- Create: `frontend/src/components/ActionBar.test.tsx`

These tests describe the new behavior. They will fail until Task 4 lands.

**Step 1: Write the failing component tests**

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActionBar } from "./ActionBar";
import type { GameState, LegalAction, Seat } from "../api/types";

function state(overrides: Partial<GameState> = {}): GameState {
  return {
    hand_id: "h",
    bb: 100,
    effective_stack: 10000,
    button: "hero",
    hero_hole: ["As", "Kd"],
    villain_hole: null,
    board: [],
    street: "preflop",
    stacks: { hero: 10000, villain: 10000 },
    committed: { hero: 50, villain: 100 },
    pot: 0,
    to_act: "hero",
    last_aggressor: "villain",
    last_raise_size: 100,
    raises_open: true,
    acted_this_street: [],
    history: [],
    rng_seed: null,
    deck_snapshot: null,
    pending_reveal: null,
    reveals: [],
    ...overrides,
  };
}

// Mirrors backend/src/poker_coach/engine/rules.py:legal_actions when hero is
// SB facing a 1bb BB — call has NO min_to/max_to; its amount is derived from
// state.committed[opponent].
const raiseLegal: LegalAction[] = [
  { type: "fold" },
  { type: "call" },
  { type: "raise", min_to: 200, max_to: 10000 },
  { type: "allin", min_to: 10000, max_to: 10000 },
];

function renderHero(legal: LegalAction[] = raiseLegal, s: Partial<GameState> = {}) {
  const onAction = vi.fn();
  render(
    <ActionBar
      state={state(s)}
      legal={legal}
      actor={"hero" as Seat}
      onAction={onAction}
    />,
  );
  return { onAction };
}

describe("ActionBar — header", () => {
  it("shows 'Your turn' for hero", () => {
    renderHero();
    expect(screen.getByText(/your turn/i)).toBeInTheDocument();
  });

  it("shows 'Villain to act' + data-entry hint for villain", () => {
    const onAction = vi.fn();
    render(
      <ActionBar
        state={state({ to_act: "villain" })}
        legal={raiseLegal}
        actor="villain"
        onAction={onAction}
      />,
    );
    expect(screen.getByText(/villain to act/i)).toBeInTheDocument();
    expect(screen.getByText(/click what villain just did/i)).toBeInTheDocument();
  });
});

describe("ActionBar — sizing panel", () => {
  it("renders preset pills for preflop", () => {
    renderHero();
    for (const label of ["min", "2.5x", "3x", "3.5x", "max"]) {
      expect(screen.getByTestId(`preset-${label}`)).toBeInTheDocument();
    }
  });

  it("clicking a preset updates the amount readout", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("3.0");
  });

  it("slider change updates the amount readout", () => {
    renderHero();
    const slider = screen.getByTestId("size-slider") as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "400" } });
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("4.0");
  });

  it("+ button nudges up by 1bb; - button nudges down by 1bb", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x")); // 3bb = 300 chips
    fireEvent.click(screen.getByTestId("size-plus"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("4.0");
    fireEvent.click(screen.getByTestId("size-minus"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("3.0");
  });

  it("does not render a sizing panel when no raise/bet is legal", () => {
    renderHero([{ type: "fold" }, { type: "call", min_to: 100 }]);
    expect(screen.queryByTestId("size-slider")).not.toBeInTheDocument();
    expect(screen.queryByTestId("preset-min")).not.toBeInTheDocument();
  });
});

describe("ActionBar — action buttons", () => {
  it("fold fires action 'fold'", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("action-fold"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "fold",
      to_amount: null,
    });
  });

  it("call fires action 'call' with to_amount: null (backend derives from state)", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("action-call"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "call",
      to_amount: null,
    });
  });

  it("call button label shows the bb delta derived from state.committed", () => {
    // hero committed 50, villain committed 100, bb=100 → call delta = 50 chips = 0.5bb
    renderHero(raiseLegal, {
      committed: { hero: 50, villain: 100 },
      to_act: "hero",
    });
    expect(screen.getByTestId("action-call")).toHaveTextContent(/call.*0\.5.*bb/i);
  });

  it("raise fires action 'raise' with the current slider amount", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    fireEvent.click(screen.getByTestId("action-raise"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "raise",
      to_amount: 300,
    });
  });

  it("raise button label embeds the bet amount in bb", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    expect(screen.getByTestId("action-raise")).toHaveTextContent(/raise to.*3\.0.*bb/i);
  });

  it("clicking max preset turns the primary button into all-in and fires 'allin'", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("preset-max"));
    const primary = screen.getByTestId("action-raise");
    expect(primary).toHaveTextContent(/all[- ]?in/i);
    fireEvent.click(primary);
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "allin",
      to_amount: 10000,
    });
  });

  it("defensively clamps a stale below-min size when re-rendered with new legal", () => {
    // Same ActionBar instance, new legal props (simulates LiveCoach NOT
    // remounting). The previous 3bb=300 sizeChips should be visually clamped
    // up to the new min_to=600, and firing dispatches the clamped amount so
    // the backend never sees an illegal raise.
    const onAction = vi.fn();
    const { rerender } = render(
      <ActionBar
        state={state()}
        legal={raiseLegal}
        actor="hero"
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId("preset-3x")); // sets sizeChips = 300
    const tighterLegal: LegalAction[] = [
      { type: "fold" },
      { type: "call" },
      { type: "raise", min_to: 600, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ];
    rerender(
      <ActionBar
        state={state()}
        legal={tighterLegal}
        actor="hero"
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId("action-raise"));
    expect(onAction).toHaveBeenLastCalledWith({
      actor: "hero",
      type: "raise",
      to_amount: 600,
    });
  });
});

describe("ActionBar — advise affordance", () => {
  it("shows advise button only when onRequestAdvice is provided", () => {
    const onAction = vi.fn();
    const onRequestAdvice = vi.fn();
    render(
      <ActionBar
        state={state()}
        legal={raiseLegal}
        actor="hero"
        onAction={onAction}
        onRequestAdvice={onRequestAdvice}
      />,
    );
    expect(screen.getByTestId("request-advice")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("request-advice"));
    expect(onRequestAdvice).toHaveBeenCalled();
  });

  it("hides advise button when onRequestAdvice is not provided (villain turn)", () => {
    const onAction = vi.fn();
    render(
      <ActionBar
        state={state({ to_act: "villain" })}
        legal={raiseLegal}
        actor="villain"
        onAction={onAction}
      />,
    );
    expect(screen.queryByTestId("request-advice")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run and verify the tests fail**

```sh
cd frontend && npx vitest run src/components/ActionBar.test.tsx && cd ..
```

Expected: the file fails compilation or most assertions fail, because the new ActionBar does not exist yet. This is fine — Task 4 implements it.

**Step 3: Commit**

```sh
git add frontend/src/components/ActionBar.test.tsx
git commit -m "test(frontend): failing tests for redesigned ActionBar"
```

---

## Task 4: Rewrite ActionBar implementation

**Files:**
- Modify (full rewrite): `frontend/src/components/ActionBar.tsx`

**Step 1: Replace file content**

```tsx
import { useMemo, useState } from "react";
import type { Action, GameState, LegalAction, Seat } from "../api/types";
import {
  clampChips,
  getPresets,
  legalByType,
  type Preset,
  resolveFireType,
  sizeableType,
  sizingPotPct,
} from "./actionBar/sizing";

export function ActionBar({
  state,
  legal,
  actor,
  onAction,
  onRequestAdvice,
  adviceDisabled,
}: {
  state: GameState;
  legal: LegalAction[];
  actor: Seat;
  onAction: (a: Action) => void;
  onRequestAdvice?: () => void;
  adviceDisabled?: boolean;
}) {
  const lbt = useMemo(() => legalByType(legal), [legal]);
  const sized = sizeableType(lbt);
  const sizingLegal = sized ? lbt[sized]! : null;
  const presets = useMemo<Preset[]>(
    () => (sizingLegal ? getPresets(state, sizingLegal) : []),
    [state, sizingLegal],
  );

  const initialChips = sizingLegal?.min_to ?? 0;
  const [sizeChips, setSizeChips] = useState<number>(initialChips);

  const nudge = (deltaChips: number) => {
    if (!sizingLegal) return;
    setSizeChips((prev) => clampChips(prev + deltaChips, sizingLegal));
  };

  const fireSizing = () => {
    const resolved = resolveFireType(sizeChips, lbt);
    if (!resolved) return;
    onAction({ actor, type: resolved.type, to_amount: resolved.to });
  };

  const fireFixed = (type: "fold" | "check" | "call") => {
    const la = lbt[type];
    if (!la) return;
    // call/check/fold carry no amount on the LegalAction; the backend derives
    // the call amount from state.committed (see engine/models.py).
    onAction({ actor, type, to_amount: null });
  };

  // Delta the actor must put in to call, derived from state (not legal).
  const callDeltaChips = (() => {
    const other = actor === "hero" ? "villain" : "hero";
    return Math.max(0, state.committed[other] - state.committed[actor]);
  })();

  const fireAllIn = () => {
    if (!lbt.allin?.max_to) return;
    onAction({ actor, type: "allin", to_amount: lbt.allin.max_to });
  };

  const bb = state.bb;
  // Clamp for display so a stale sizeChips (e.g. across a spot transition
  // where the parent didn't remount) can never render an out-of-range
  // readout or a slider thumb that disagrees with the native range input.
  const effectiveSizeChips = sizingLegal ? clampChips(sizeChips, sizingLegal) : sizeChips;
  const sizeBb = effectiveSizeChips / bb;
  const potPct = sizingLegal ? sizingPotPct(effectiveSizeChips, state) : null;
  const atMax =
    sizingLegal?.max_to != null && effectiveSizeChips >= sizingLegal.max_to;
  const actorLabel = actor === "hero" ? "Your turn" : "Villain to act";

  return (
    <div
      className={`rounded-xl p-4 flex flex-col gap-3 ring-1 ${
        actor === "hero"
          ? "bg-stone-900/90 ring-white/10"
          : "bg-stone-900/70 ring-white/5"
      }`}
      data-testid="action-bar"
      data-actor={actor}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-stone-100">{actorLabel}</span>
        <div className="flex items-center gap-3">
          {actor === "villain" && (
            <span className="text-xs text-stone-400">Click what villain just did</span>
          )}
          {onRequestAdvice && (
            <button
              data-testid="request-advice"
              onClick={onRequestAdvice}
              disabled={adviceDisabled}
              className="text-xs font-semibold text-amber-400 hover:text-amber-300 disabled:opacity-40 transition"
            >
              advise
            </button>
          )}
        </div>
      </div>

      {sizingLegal && sizingLegal.min_to != null && sizingLegal.max_to != null && (
        <SizingPanel
          state={state}
          la={sizingLegal}
          presets={presets}
          sizeChips={effectiveSizeChips}
          onSetChips={(c) => setSizeChips(clampChips(c, sizingLegal))}
          onNudge={nudge}
          sizeBb={sizeBb}
          potPct={potPct}
        />
      )}

      <div className="grid grid-cols-3 gap-2">
        <ActionSlot
          testId="action-fold"
          visible={Boolean(lbt.fold)}
          onClick={() => fireFixed("fold")}
          tone="neutral"
          label="Fold"
        />
        <ActionSlot
          testId={lbt.check ? "action-check" : "action-call"}
          visible={Boolean(lbt.check || lbt.call)}
          onClick={() => fireFixed(lbt.check ? "check" : "call")}
          tone="info"
          label={
            lbt.check
              ? "Check"
              : `Call ${(callDeltaChips / bb).toFixed(1)}bb`
          }
        />
        {sizingLegal ? (
          <button
            data-testid="action-raise"
            onClick={atMax && lbt.allin ? fireAllIn : fireSizing}
            className={`h-14 rounded-xl font-semibold text-white shadow transition active:scale-[0.98] flex flex-col items-center justify-center leading-tight ${
              atMax && lbt.allin
                ? "bg-gradient-to-b from-red-500 to-red-700 hover:from-red-400 hover:to-red-600"
                : "bg-gradient-to-b from-emerald-500 to-emerald-700 hover:from-emerald-400 hover:to-emerald-600"
            }`}
          >
            {atMax && lbt.allin ? (
              <>
                <span className="text-xs opacity-80">All-in</span>
                <span className="text-base tabular-nums">{sizeBb.toFixed(1)}bb</span>
              </>
            ) : (
              <>
                <span className="text-xs opacity-80">
                  {sized === "raise" ? "Raise to" : "Bet"}
                </span>
                <span className="text-base tabular-nums">{sizeBb.toFixed(1)}bb</span>
              </>
            )}
          </button>
        ) : lbt.allin ? (
          <ActionSlot
            testId="action-allin"
            visible
            onClick={fireAllIn}
            tone="allin"
            label={`All-in ${((lbt.allin.max_to ?? 0) / bb).toFixed(1)}bb`}
          />
        ) : (
          <div />
        )}
      </div>
    </div>
  );
}

function SizingPanel({
  state,
  la,
  presets,
  sizeChips,
  onSetChips,
  onNudge,
  sizeBb,
  potPct,
}: {
  state: GameState;
  la: LegalAction;
  presets: Preset[];
  sizeChips: number;
  onSetChips: (c: number) => void;
  onNudge: (deltaChips: number) => void;
  sizeBb: number;
  potPct: number | null;
}) {
  const min = la.min_to!;
  const max = la.max_to!;
  const activeLabel = presets.find((p) => p.toChips === sizeChips)?.label;

  return (
    <div className="rounded-lg bg-black/30 ring-1 ring-white/5 p-3 flex flex-col gap-3">
      <div className="flex gap-1.5 flex-wrap">
        {presets.map((p) => {
          const isMax = p.kind === "max";
          const active = activeLabel === p.label;
          return (
            <button
              key={p.label}
              data-testid={`preset-${p.label}`}
              onClick={() => onSetChips(p.toChips)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                active
                  ? isMax
                    ? "bg-red-500/20 ring-1 ring-red-400 text-red-100"
                    : "bg-emerald-500/20 ring-1 ring-emerald-400 text-emerald-100"
                  : isMax
                    ? "bg-red-500/10 text-red-200 hover:bg-red-500/20"
                    : "bg-white/5 text-stone-200 hover:bg-white/15"
              }`}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <button
          data-testid="size-minus"
          onClick={() => onNudge(-state.bb)}
          className="h-9 w-9 rounded-lg bg-white/5 hover:bg-white/15 text-stone-100 text-lg font-bold transition disabled:opacity-40"
          disabled={sizeChips <= min}
          aria-label="Decrease size by 1bb"
        >
          −
        </button>
        <div className="relative flex-1 h-9 flex items-center">
          <div className="absolute inset-x-0 h-2 rounded-full bg-stone-700 pointer-events-none" />
          <div
            className="absolute h-2 rounded-full bg-emerald-500 pointer-events-none"
            style={{ width: `${pct(sizeChips, min, max)}%` }}
          />
          {presets.map((p) => (
            <span
              key={p.label}
              className={`absolute w-0.5 h-3 rounded-full pointer-events-none ${
                p.kind === "max" ? "bg-red-400" : "bg-white/60"
              }`}
              style={{ left: `calc(${pct(p.toChips, min, max)}% - 1px)` }}
            />
          ))}
          <input
            type="range"
            min={min}
            max={max}
            step={1}
            value={sizeChips}
            onChange={(e) => onSetChips(Number(e.target.value))}
            data-testid="size-slider"
            aria-label="Bet size in chips"
            className="relative w-full appearance-none bg-transparent cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:ring-2 [&::-webkit-slider-thumb]:ring-emerald-400 [&::-webkit-slider-thumb]:shadow [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-emerald-400"
          />
        </div>
        <button
          data-testid="size-plus"
          onClick={() => onNudge(state.bb)}
          className="h-9 w-9 rounded-lg bg-white/5 hover:bg-white/15 text-stone-100 text-lg font-bold transition disabled:opacity-40"
          disabled={sizeChips >= max}
          aria-label="Increase size by 1bb"
        >
          +
        </button>
      </div>

      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <span
            data-testid="size-readout-bb"
            className="text-3xl font-bold tabular-nums text-stone-50"
          >
            {sizeBb.toFixed(1)}
          </span>
          <span className="text-xs text-stone-400">bb</span>
        </div>
        <span className="text-xs text-stone-400 tabular-nums">
          = {sizeChips /* receives clamped effective value from parent */} chips
          {potPct != null ? ` · ${Math.round(potPct)}% pot` : ""}
        </span>
      </div>
    </div>
  );
}

function pct(value: number, min: number, max: number): number {
  if (max === min) return 0;
  return ((value - min) / (max - min)) * 100;
}

function ActionSlot({
  testId,
  visible,
  onClick,
  tone,
  label,
}: {
  testId: string;
  visible: boolean;
  onClick: () => void;
  tone: "neutral" | "info" | "allin";
  label: string;
}) {
  if (!visible) return <div />;
  const toneClass =
    tone === "neutral"
      ? "bg-stone-700 hover:bg-stone-600 text-stone-100"
      : tone === "info"
        ? "bg-sky-700 hover:bg-sky-600 text-white"
        : "bg-gradient-to-b from-red-500 to-red-700 hover:from-red-400 hover:to-red-600 text-white";
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className={`h-14 rounded-xl font-semibold shadow transition active:scale-[0.98] ${toneClass}`}
    >
      {label}
    </button>
  );
}
```

**Step 2: Run unit tests**

```sh
cd frontend && npx vitest run src/components/actionBar src/components/ActionBar.test.tsx && cd ..
```

Expected: all tests pass.

**Step 3: Typecheck + lint**

```sh
cd frontend && npm run typecheck && npm run lint && cd ..
```

Expected: no errors. If eslint complains about the unused `useHotkeys` import or old helpers, make sure they were removed in the rewrite.

**Step 4: Commit**

```sh
git add frontend/src/components/ActionBar.tsx
git commit -m "feat(frontend): redesign ActionBar with slider, presets, and 3-button grid"
```

---

## Task 5: Force ActionBar remount across spot transitions in LiveCoach

**Files:**
- Modify: `frontend/src/routes/LiveCoach.tsx`

Without this, the same `ActionBar` instance keeps its stale `sizeChips` across hero→villain turns, street changes, and new hands. The defensive clamp inside `resolveFireType` prevents backend errors, but users would see confusing "default sizing" that doesn't actually default to the new min.

**Step 1: Locate the existing ActionBar render**

`frontend/src/routes/LiveCoach.tsx:249-265` — find the `<ActionBar` JSX.

**Step 2: Add a `key` prop**

Insert a `key` expression as the first prop:

```tsx
<ActionBar
  key={`${snapshot.state.hand_id}:${snapshot.state.history.length}:${snapshot.state.to_act}`}
  state={snapshot.state}
  legal={snapshot.legal_actions}
  actor={snapshot.state.to_act}
  ...
/>
```

Rationale: `hand_id` changes on new hand; `history.length` monotonically increases within a hand on every action; `to_act` changes even when history doesn't (e.g. villain-to-act after hero-to-act would otherwise share a state slot). Together these cover every spot boundary. This is the same key-remount pattern CLAUDE.md gotcha #6 prescribes for `CardPicker`.

**Step 3: Typecheck**

```sh
cd frontend && npm run typecheck && cd ..
```

Expected: no errors.

**Step 4: Commit**

```sh
git add frontend/src/routes/LiveCoach.tsx
git commit -m "fix(frontend): remount ActionBar on spot transitions to reset sizing"
```

---

## Task 6: Update AdvicePanel copy (no more "press space")

**Files:**
- Modify: `frontend/src/components/AdvicePanel.tsx:33-38`

Task 4 removed the `space` hotkey from `ActionBar`. The advice panel still tells users to press space — ships a real UX regression otherwise.

**Step 1: Apply edit**

Old (`AdvicePanel.tsx:33-38`):

```tsx
      {stream.status === "idle" && (
        <p className="text-sm opacity-60">
          Press <kbd className="px-1 rounded bg-white/10">space</kbd> on hero's turn to ask
          the coach.
        </p>
      )}
```

New:

```tsx
      {stream.status === "idle" && (
        <p className="text-sm opacity-60">
          Click <span className="font-semibold text-amber-300">advise</span> on hero's turn
          to ask the coach.
        </p>
      )}
```

**Step 2: Lint**

```sh
cd frontend && npm run lint && cd ..
```

Expected: no errors.

**Step 3: Commit**

```sh
git add frontend/src/components/AdvicePanel.tsx
git commit -m "docs(frontend): update AdvicePanel copy after hotkey removal"
```

---

## Task 7: Update Playwright e2e spec

**Files:**
- Modify: `frontend/e2e/live-coach.spec.ts`

`size-input` no longer exists; the test must drive the slider by clicking a preset.

**Step 1: Apply edit**

Replace lines 45-47 in `frontend/e2e/live-coach.spec.ts`:

Old:
```ts
  // Raise to 3bb via the size-input + raise button
  await page.getByTestId("size-input").fill("3");
  await page.getByTestId("action-raise").click();
```

New:
```ts
  // Raise to 3bb via the preset pill + raise button
  await page.getByTestId("preset-3x").click();
  await expect(page.getByTestId("size-readout-bb")).toHaveText("3.0");
  await page.getByTestId("action-raise").click();
```

**Step 2: Run e2e** (requires backend + frontend; use `make e2e` which spawns both)

```sh
make e2e
```

Expected: both specs pass.

**Step 3: Commit**

```sh
git add frontend/e2e/live-coach.spec.ts
git commit -m "test(e2e): drive ActionBar via preset pill after slider redesign"
```

---

## Task 8: Full test + lint sweep and manual browser smoke

**Step 1: Full test + lint**

```sh
make test && make lint
```

Expected: all green. Fix any regressions before moving on.

**Step 2: Browser smoke check**

Start dev servers (`make dev`), open the frontend at http://localhost:5173, and walk through:

1. Click **New hand** → ActionBar appears with preflop presets (`min / 2.5x / 3x / 3.5x / max`), slider defaulting to min.
2. Click `3x` pill → readout shows `3.0 bb`, slider thumb moves to the `3x` tick.
3. Click `+` twice → readout shows `5.0 bb` (thumb moves).
4. Drag slider to far right → primary button swaps to red "All-in" with `100.0bb`.
5. Click max preset → same red all-in label; click fires all-in.
6. Start a new hand, raise preflop (e.g. 3x), villain raises (click villain preset `3x` then primary raise to send them to 9bb), now the slider resets to the new min raise — **not** the stale 3bb. Readout shows the new min, not `3.0 bb`.
7. Click call on hero's turn to continue; flop appears.
8. On flop, sizing panel shows postflop presets (`min / 33% / 50% / 75% / pot / 1.5x / max`), readout now also shows `% pot`.
9. Call label shows the correct delta (e.g. after villain bets 3bb into a 4bb pot, hero's call button reads `Call 3.0bb`, not `Call 0.0bb`).
10. Flip hero/villain turn behavior: during villain-to-act, the header reads "Villain to act" and the advise button is gone.
11. Open the AdvicePanel in its idle state → copy reads "Click **advise** on hero's turn…", no mention of space.

If any step looks wrong visually, note it and iterate on `ActionBar.tsx` before claiming done.

**Step 3: Final commit (if any visual tweak was needed)**

```sh
git add frontend/src/components/ActionBar.tsx
git commit -m "style(frontend): ActionBar polish after browser smoke"
```

---

## Notes / gotchas

- `useHotkeys` hook stays — `LiveCoach.tsx:195` still imports it for `n`/`Escape`. Do not delete the hook file.
- The advise button moved from the action row (bottom-right amber button) into the header strip as a text-link. This is deliberate — it's a coach meta-action, not a real poker action.
- When `bet`/`raise` is not legal but `allin` is (rare), `ActionBar` still renders an `action-allin` button via `ActionSlot` fallback in the third slot. Kept for completeness; no test currently covers this path because it doesn't appear in the current engine flow for HU NLHE, but the fallback prevents a blank button.
- Integer chips are the source of truth. bb is display-only (`sizeChips / state.bb`). Never parse bb strings for sizing math — that was the old fragility.
- The `villain` turn uses the exact same sizing + action machinery. The only differences are the header label, the missing advise button, and the slightly muted container ring.
- **Reset-across-spots is a parent concern.** ActionBar owns `sizeChips` locally (like `CardPicker` — see CLAUDE.md gotcha #6). Do NOT add a prop-syncing `useEffect` inside ActionBar to watch `legal` changes — that's the anti-pattern the gotcha warns about. The key-remount in `LiveCoach` plus the defensive clamp in `resolveFireType` are the correct layering.
- **Call has no `min_to` / `max_to`.** Per `backend/src/poker_coach/engine/models.py:25-30` and `rules.py:114`, only `bet` / `raise` / `allin` carry amount bounds. `Action.to_amount` for call/check/fold is always `null`. The call button's label derives its bb delta from `state.committed[opponent] - state.committed[actor]`, never from a field on the `LegalAction`.
