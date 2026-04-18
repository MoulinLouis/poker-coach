# Live Coach UI/UX Upgrade — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform Live Coach from a plain-HTML debug UI into a real-feeling poker interface with a visual table, SVG playing cards, a keyboard-driven action bar, and a polished advice panel.

**Architecture:** Split the one-file `LiveCoach.tsx` into focused presentational components (PokerTable, Seat, Board, PlayingCard, Pot, ActionBar, AdvicePanel, HandSummary) plus a `useHotkeys` hook. Keep the existing API wiring and state management in LiveCoach; components stay pure and prop-driven.

**Tech Stack:**
- **Tailwind CSS 4** via `@tailwindcss/vite` plugin — zero-config, utility-first
- **Hand-built SVG playing cards** — no card library dep; full control over style
- **No Framer Motion / Radix / shadcn** — Tailwind transitions cover card reveal + advice entrance; components stay dep-free
- **`@testing-library/react` + vitest** for component-level assertions

**Rejected alternatives:**
- Framer Motion — adds ~50kb gzipped for animations we can do in ~10 lines of CSS. Add later if needed.
- shadcn/ui — pulls Radix + a dozen primitives for a 2-page app. Overkill.
- Playing card npm package (e.g., `react-playing-card`) — pinning dep + style for something that's ~40 lines of SVG is worse.

---

## Execution order

All tasks live on a single working branch. Commit after each task. Run `make lint` and the relevant tests before each commit. The Playwright happy-path test at the end must stay green.

---

### Task 1: Install Tailwind 4 + index.css

**Files:**
- Modify: `frontend/package.json` — add `tailwindcss@^4`, `@tailwindcss/vite@^4`
- Modify: `frontend/vite.config.ts` — register the Tailwind plugin
- Create: `frontend/src/index.css` — `@import "tailwindcss";` + custom theme tokens (felt green, card colors, suit reds/blacks)
- Modify: `frontend/src/main.tsx` — `import "./index.css"`

**Step 1:** Install deps.

```bash
cd frontend && npm install --save-dev tailwindcss@^4 @tailwindcss/vite@^4
```

**Step 2:** Update `vite.config.ts`.

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
```

**Step 3:** Create `frontend/src/index.css`.

```css
@import "tailwindcss";

@theme {
  --color-felt: #0e5a33;
  --color-felt-dark: #083d22;
  --color-card-bg: #fafafa;
  --color-card-red: #c0352c;
  --color-card-black: #111111;
  --color-chip-gold: #d4a14a;
  --color-chip-red: #c0352c;

  --font-sans: "system-ui", sans-serif;
}

/* Subtle felt texture */
.bg-felt {
  background:
    radial-gradient(ellipse at center, var(--color-felt) 0%, var(--color-felt-dark) 100%);
}
```

**Step 4:** Import in `main.tsx`.

```ts
import "./index.css";
// (existing imports)
```

**Step 5:** Verify dev server starts without errors.

```bash
make dev  # manual smoke, Ctrl-C when /api/health passes in browser
```

**Step 6:** Commit.

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.ts frontend/src/index.css frontend/src/main.tsx
git commit -m "chore(frontend): add tailwind 4 with poker theme tokens"
```

---

### Task 2: PlayingCard SVG component

**Files:**
- Create: `frontend/src/components/PlayingCard.tsx`
- Create: `frontend/src/components/PlayingCard.test.tsx`
- Modify: `frontend/package.json` — add `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
- Modify: `frontend/vitest.config.ts` — enable jsdom + testing-library setup

**Step 1:** Install test deps.

```bash
cd frontend && npm install --save-dev @testing-library/react @testing-library/jest-dom jsdom
```

**Step 2:** Update `vitest.config.ts`.

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.{ts,tsx}"],
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `frontend/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

**Step 3:** Write the failing test.

```tsx
// src/components/PlayingCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlayingCard } from "./PlayingCard";

describe("PlayingCard", () => {
  it("renders rank and suit from a card code", () => {
    render(<PlayingCard code="As" />);
    // "As" = Ace of spades
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByLabelText(/ace of spades/i)).toBeInTheDocument();
  });

  it("renders red color for hearts", () => {
    const { container } = render(<PlayingCard code="Qh" />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("data-suit", "h");
  });

  it("renders face-down card when code is null", () => {
    const { container } = render(<PlayingCard code={null} />);
    expect(container.querySelector('[data-facedown="true"]')).toBeInTheDocument();
  });
});
```

**Step 4:** Run test to confirm it fails.

```bash
cd frontend && npm test -- PlayingCard
```

Expected: FAIL (component doesn't exist yet).

**Step 5:** Implement.

```tsx
// src/components/PlayingCard.tsx
const SUITS = {
  s: { glyph: "♠", name: "spades", color: "text-card-black" },
  h: { glyph: "♥", name: "hearts", color: "text-card-red" },
  d: { glyph: "♦", name: "diamonds", color: "text-card-red" },
  c: { glyph: "♣", name: "clubs", color: "text-card-black" },
} as const;

const RANK_NAMES: Record<string, string> = {
  A: "ace", K: "king", Q: "queen", J: "jack", T: "ten",
  "9": "nine", "8": "eight", "7": "seven", "6": "six",
  "5": "five", "4": "four", "3": "three", "2": "two",
};

export function PlayingCard({
  code,
  size = "md",
}: {
  code: string | null;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass = {
    sm: "w-10 h-14 text-sm",
    md: "w-14 h-20 text-base",
    lg: "w-20 h-28 text-xl",
  }[size];

  if (!code) {
    return (
      <div
        data-facedown="true"
        className={`${sizeClass} rounded-md border-2 border-white/30 bg-gradient-to-br from-blue-900 to-blue-700 shadow-md`}
      />
    );
  }

  const rank = code[0];
  const suit = SUITS[code[1] as keyof typeof SUITS];
  const label = `${RANK_NAMES[rank] ?? rank} of ${suit.name}`;

  return (
    <svg
      viewBox="0 0 60 84"
      className={`${sizeClass} drop-shadow-md`}
      data-suit={code[1]}
      aria-label={label}
    >
      <rect x="1" y="1" width="58" height="82" rx="6" className="fill-card-bg stroke-black/20" strokeWidth="1" />
      <text x="6" y="18" className={`${suit.color} font-bold`} fontSize="14">{rank}</text>
      <text x="6" y="30" className={`${suit.color}`} fontSize="12">{suit.glyph}</text>
      <text x="30" y="56" textAnchor="middle" className={`${suit.color}`} fontSize="34">{suit.glyph}</text>
      <text x="54" y="78" textAnchor="end" className={`${suit.color} font-bold`} fontSize="14" transform="rotate(180 54 74)">{rank}</text>
    </svg>
  );
}
```

**Step 6:** Run tests; verify they pass.

```bash
npm test -- PlayingCard
```

Expected: all three tests PASS.

**Step 7:** Commit.

```bash
git add frontend/src/components/PlayingCard.tsx frontend/src/components/PlayingCard.test.tsx frontend/src/test/setup.ts frontend/vitest.config.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add PlayingCard SVG component"
```

---

### Task 3: Seat, Board, Pot, PokerTable layout

**Files:**
- Create: `frontend/src/components/Seat.tsx`
- Create: `frontend/src/components/Board.tsx`
- Create: `frontend/src/components/Pot.tsx`
- Create: `frontend/src/components/PokerTable.tsx`

**Design:**
- `PokerTable` is the felt-green container; positions hero at bottom, villain at top, board + pot in the center via flex/grid.
- `Seat` shows: seat label (Hero/Villain), stack in BB, hole cards (faceup for hero always, faceup for villain only on showdown/complete), a glowing ring when `to_act`.
- `Board` renders 5 card slots — empty slots show the felt color / outline; filled slots fade in.
- `Pot` shows pot size in BB with a stack-of-chips icon.

**Step 1:** Write `Seat.tsx`.

```tsx
import { PlayingCard } from "./PlayingCard";
import type { GameState, Seat as SeatId } from "../api/types";

export function Seat({
  id,
  label,
  state,
  showHole,
}: {
  id: SeatId;
  label: string;
  state: GameState;
  showHole: boolean;
}) {
  const stack = state.stacks[id];
  const committed = state.committed[id];
  const isToAct = state.to_act === id;
  const hole = id === "hero" ? state.hero_hole : state.villain_hole;

  return (
    <div
      data-testid={`seat-${id}`}
      className={`flex flex-col items-center gap-2 rounded-2xl px-4 py-3 bg-black/40 ${
        isToAct ? "ring-4 ring-amber-400 shadow-lg shadow-amber-500/40" : "ring-1 ring-white/10"
      } transition-all`}
    >
      <div className="flex items-baseline gap-2 text-white">
        <span className="font-semibold">{label}</span>
        <span className="text-xs opacity-70">{(stack / state.bb).toFixed(1)} bb</span>
      </div>
      <div className="flex gap-1">
        {hole && showHole ? (
          <>
            <PlayingCard code={hole[0]} size="md" />
            <PlayingCard code={hole[1]} size="md" />
          </>
        ) : (
          <>
            <PlayingCard code={null} size="md" />
            <PlayingCard code={null} size="md" />
          </>
        )}
      </div>
      {committed > 0 && (
        <div className="text-xs text-amber-300">
          bet {(committed / state.bb).toFixed(1)} bb
        </div>
      )}
    </div>
  );
}
```

**Step 2:** Write `Board.tsx`.

```tsx
import { PlayingCard } from "./PlayingCard";

export function Board({ cards }: { cards: string[] }) {
  return (
    <div data-testid="board" className="flex gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center">
          {cards[i] ? (
            <PlayingCard code={cards[i]} size="lg" />
          ) : (
            <div className="w-20 h-28 rounded-md border-2 border-dashed border-white/20" />
          )}
        </div>
      ))}
    </div>
  );
}
```

**Step 3:** Write `Pot.tsx`.

```tsx
export function Pot({ potBb, committedBb }: { potBb: number; committedBb: number }) {
  const total = potBb + committedBb;
  return (
    <div data-testid="pot" className="flex items-center gap-2 px-4 py-2 rounded-full bg-black/50 text-white">
      <span className="w-3 h-3 rounded-full bg-chip-gold ring-2 ring-yellow-200/40" />
      <span className="font-semibold">{total.toFixed(1)} bb</span>
      <span className="text-xs opacity-70">pot</span>
    </div>
  );
}
```

**Step 4:** Write `PokerTable.tsx`.

```tsx
import type { GameState } from "../api/types";
import { Board } from "./Board";
import { Pot } from "./Pot";
import { Seat } from "./Seat";

export function PokerTable({ state }: { state: GameState }) {
  const showVillainHole = state.street === "showdown" || state.street === "complete";
  const potBb = state.pot / state.bb;
  const committedBb = (state.committed.hero + state.committed.villain) / state.bb;

  return (
    <div className="bg-felt rounded-[48px] px-8 py-10 shadow-2xl border-8 border-stone-800">
      <div className="flex flex-col items-center gap-8 min-h-[360px]">
        <Seat id="villain" label="Villain" state={state} showHole={showVillainHole} />
        <div className="flex flex-col items-center gap-3">
          <Board cards={state.board} />
          <Pot potBb={potBb} committedBb={committedBb} />
        </div>
        <Seat id="hero" label="Hero" state={state} showHole={true} />
      </div>
    </div>
  );
}
```

**Step 5:** Lint.

```bash
cd frontend && npx tsc -b --noEmit && npm run lint
```

Expected: clean.

**Step 6:** Commit.

```bash
git add frontend/src/components/Seat.tsx frontend/src/components/Board.tsx frontend/src/components/Pot.tsx frontend/src/components/PokerTable.tsx
git commit -m "feat(frontend): add PokerTable, Seat, Board, Pot components"
```

---

### Task 4: useHotkeys hook + ActionBar with street-aware sizing

**Files:**
- Create: `frontend/src/hooks/useHotkeys.ts`
- Create: `frontend/src/components/ActionBar.tsx`

**Hotkey mapping** (from design doc §5):
- `f` fold, `c` call, `k` check, `b` bet, `r` raise, `a` all-in
- `space` — get advice
- `n` — new hand
- `esc` — cancel in-flight

**Size presets:**
- **Preflop:** `1`=min-raise, `2`=2.5x, `3`=3x, `4`=3.5x
- **Postflop:** `1`=33% pot, `2`=50%, `3`=75%, `4`=pot, `5`=150% pot

**Step 1:** Write `useHotkeys.ts`.

```ts
import { useEffect } from "react";

type Binding = { key: string; handler: () => void; disabled?: boolean };

export function useHotkeys(bindings: Binding[]): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      const match = bindings.find(
        (b) => !b.disabled && b.key.toLowerCase() === e.key.toLowerCase(),
      );
      if (match) {
        e.preventDefault();
        match.handler();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bindings]);
}
```

**Step 2:** Write `ActionBar.tsx`.

```tsx
import { useMemo, useState } from "react";
import { useHotkeys } from "../hooks/useHotkeys";
import type { Action, ActionType, GameState, LegalAction, Seat } from "../api/types";

const HOTKEY: Record<ActionType, string> = {
  fold: "f",
  check: "k",
  call: "c",
  bet: "b",
  raise: "r",
  allin: "a",
};

function preflopPresets(state: GameState, la: LegalAction): { label: string; toBb: number }[] {
  if (!la.min_to || !la.max_to) return [];
  const maxBb = la.max_to / state.bb;
  const minBb = la.min_to / state.bb;
  const presets = [
    { label: "min", toBb: minBb },
    { label: "2.5x", toBb: 2.5 },
    { label: "3x", toBb: 3 },
    { label: "3.5x", toBb: 3.5 },
  ];
  return presets.filter((p) => p.toBb >= minBb && p.toBb <= maxBb);
}

function postflopPresets(state: GameState, la: LegalAction): { label: string; toBb: number }[] {
  if (!la.min_to || !la.max_to) return [];
  const potBb =
    (state.pot + state.committed.hero + state.committed.villain) / state.bb;
  const actorCommitted =
    state.to_act === "hero" ? state.committed.hero : state.committed.villain;
  const ratios = [
    { label: "33%", r: 0.33 },
    { label: "50%", r: 0.5 },
    { label: "75%", r: 0.75 },
    { label: "pot", r: 1 },
    { label: "150%", r: 1.5 },
  ];
  const minBb = la.min_to / state.bb;
  const maxBb = la.max_to / state.bb;
  return ratios
    .map((r) => ({
      label: r.label,
      toBb: (actorCommitted / state.bb) + potBb * r.r,
    }))
    .map((p) => ({ label: p.label, toBb: Math.max(minBb, Math.min(maxBb, p.toBb)) }));
}

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
  const [sizeBb, setSizeBb] = useState<string>("");
  const legalByType = useMemo(() => Object.fromEntries(legal.map((l) => [l.type, l])), [legal]);

  const isBetOrRaise = (t: ActionType) => t === "bet" || t === "raise";

  const fire = (type: ActionType) => {
    const la = legalByType[type];
    if (!la) return;
    let to: number | null = null;
    if (isBetOrRaise(type)) {
      const bb = parseFloat(sizeBb);
      if (!Number.isFinite(bb) || bb <= 0) return;
      to = Math.round(bb * state.bb);
    } else if (type === "allin") {
      to = la.max_to ?? null;
    }
    onAction({ actor, type, to_amount: to });
    setSizeBb("");
  };

  const presets = useMemo(() => {
    const sizeableType = legalByType.raise ? "raise" : legalByType.bet ? "bet" : null;
    if (!sizeableType) return [];
    const la = legalByType[sizeableType];
    return state.street === "preflop" ? preflopPresets(state, la) : postflopPresets(state, la);
  }, [legalByType, state]);

  useHotkeys([
    ...(Object.entries(HOTKEY) as [ActionType, string][]).map(([t, k]) => ({
      key: k,
      handler: () => {
        if (legalByType[t]) fire(t);
      },
      disabled: !legalByType[t],
    })),
    { key: " ", handler: () => onRequestAdvice?.(), disabled: !onRequestAdvice || adviceDisabled },
  ]);

  return (
    <div className="flex flex-col gap-3" data-testid="action-bar">
      {presets.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {presets.map((p, i) => (
            <button
              key={p.label}
              data-testid={`preset-${p.label}`}
              onClick={() => setSizeBb(p.toBb.toFixed(2))}
              className="px-3 py-1 rounded border border-white/20 bg-white/10 text-white text-sm hover:bg-white/20"
            >
              <span className="opacity-70 mr-1">{i + 1}</span>
              {p.label} <span className="opacity-70">({p.toBb.toFixed(1)}bb)</span>
            </button>
          ))}
          <input
            data-testid="size-input"
            placeholder="size (bb)"
            value={sizeBb}
            onChange={(e) => setSizeBb(e.target.value)}
            className="w-28 px-2 py-1 rounded border border-white/20 bg-black/30 text-white text-sm"
          />
        </div>
      )}
      <div className="flex gap-2 flex-wrap">
        {legal.map((la) => (
          <button
            key={la.type}
            data-testid={`action-${la.type}`}
            onClick={() => fire(la.type)}
            className={`px-4 py-2 rounded-lg font-semibold text-white shadow ${
              la.type === "fold"
                ? "bg-stone-700 hover:bg-stone-600"
                : la.type === "allin"
                  ? "bg-red-700 hover:bg-red-600"
                  : "bg-emerald-700 hover:bg-emerald-600"
            }`}
          >
            <kbd className="mr-2 opacity-60 text-xs">{HOTKEY[la.type]}</kbd>
            {la.type}
          </button>
        ))}
        {onRequestAdvice && (
          <button
            data-testid="request-advice"
            onClick={onRequestAdvice}
            disabled={adviceDisabled}
            className="px-4 py-2 rounded-lg font-semibold text-white bg-amber-600 hover:bg-amber-500 disabled:opacity-50"
          >
            <kbd className="mr-2 opacity-60 text-xs">space</kbd>
            advise
          </button>
        )}
      </div>
    </div>
  );
}
```

**Step 3:** Lint + typecheck.

```bash
cd frontend && npx tsc -b --noEmit && npm run lint
```

**Step 4:** Commit.

```bash
git add frontend/src/hooks/useHotkeys.ts frontend/src/components/ActionBar.tsx
git commit -m "feat(frontend): add ActionBar with hotkeys and street-aware size presets"
```

---

### Task 5: AdvicePanel refactor

**Files:**
- Create: `frontend/src/components/AdvicePanel.tsx`

**Design:**
- Left column of the main layout. Fixed width (~380px).
- States:
  - idle: hint text ("press space to ask for advice")
  - thinking: spinner + "Thinking…" — stays until first reasoning token
  - streaming: reasoning text in a scrollable pane with monospace font
  - done with advice: advice card with rank/suit accents, confidence badge, cost
  - error: red panel with error message
- Divergence badge shown in header if `diverged === true`.

**Step 1:** Write `AdvicePanel.tsx`.

```tsx
import type { StreamState } from "../api/useAdviceStream";
import type { Advice } from "../api/types";

export function AdvicePanel({
  stream,
  diverged,
  presetLabel,
}: {
  stream: StreamState;
  diverged: boolean;
  presetLabel: string;
}) {
  return (
    <aside
      data-testid="advice-panel"
      className="w-[380px] shrink-0 flex flex-col gap-3 rounded-xl bg-stone-900 p-4 text-stone-100 shadow-xl"
    >
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">Coach</span>
          <span className="text-xs opacity-60">{presetLabel}</span>
        </div>
        {diverged && (
          <span
            data-testid="diverged-badge"
            className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-xs border border-amber-500/40"
          >
            diverged
          </span>
        )}
      </header>

      {stream.status === "idle" && (
        <p className="text-sm opacity-60">Press <kbd>space</kbd> on hero's turn to request advice.</p>
      )}

      {stream.status === "thinking" && (
        <div className="flex items-center gap-2 text-sm opacity-80">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span>Thinking…</span>
        </div>
      )}

      {stream.reasoning && (
        <pre
          data-testid="advice-reasoning"
          className="max-h-[280px] overflow-auto text-xs font-mono whitespace-pre-wrap text-stone-300 bg-black/40 rounded p-2"
        >
          {stream.reasoning}
        </pre>
      )}

      {stream.advice && <AdviceCard advice={stream.advice} />}

      {stream.costUsd != null && (
        <div className="text-[10px] text-stone-500">cost: ${stream.costUsd.toFixed(4)}</div>
      )}

      {stream.errorMessage && (
        <div data-testid="advice-error" className="text-sm text-red-300 bg-red-900/30 rounded p-2">
          {stream.errorMessage}
        </div>
      )}
    </aside>
  );
}

function AdviceCard({ advice }: { advice: Advice }) {
  const confidenceColor = {
    high: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    medium: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    low: "bg-stone-500/20 text-stone-300 border-stone-500/40",
  }[advice.confidence];
  return (
    <div
      data-testid="advice-card"
      className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 animate-in fade-in slide-in-from-bottom-1 duration-300"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-lg font-bold capitalize">
          {advice.action}
          {advice.to_amount_bb != null && (
            <span className="ml-2 text-amber-200">to {advice.to_amount_bb} bb</span>
          )}
        </span>
        <span className={`px-2 py-0.5 rounded text-xs border ${confidenceColor}`}>
          {advice.confidence}
        </span>
      </div>
      <p className="text-sm opacity-90 leading-relaxed">{advice.reasoning}</p>
    </div>
  );
}
```

**Step 2:** Lint + typecheck.

```bash
npx tsc -b --noEmit && npm run lint
```

**Step 3:** Commit.

```bash
git add frontend/src/components/AdvicePanel.tsx
git commit -m "feat(frontend): add AdvicePanel with advice card and divergence badge"
```

---

### Task 6: HandSummary overlay + setup form panel

**Files:**
- Create: `frontend/src/components/HandSummary.tsx`
- Create: `frontend/src/components/SetupPanel.tsx`

**Design:**
- `SetupPanel` replaces the raw input grid at the top. Nicer labels + inline help.
- `HandSummary` is a card that shows when `state.street === "complete"` or `"showdown"`. Shows winner (when available), agreement rate this hand, and a "New hand" button.

**Step 1:** Write `SetupPanel.tsx`.

```tsx
import type { PresetSummary, Seat } from "../api/types";

export function SetupPanel({
  heroHole,
  villainHole,
  effectiveStack,
  button,
  presets,
  presetId,
  onChange,
  onStart,
  disabled,
}: {
  heroHole: string;
  villainHole: string;
  effectiveStack: number;
  button: Seat;
  presets: PresetSummary[];
  presetId: string;
  onChange: (patch: Partial<{
    heroHole: string;
    villainHole: string;
    effectiveStack: number;
    button: Seat;
    presetId: string;
  }>) => void;
  onStart: () => void;
  disabled?: boolean;
}) {
  return (
    <section className="rounded-xl bg-stone-800 p-4 text-stone-100 flex flex-wrap items-end gap-4">
      <Field label="Hero hole">
        <input
          value={heroHole}
          onChange={(e) => onChange({ heroHole: e.target.value })}
          placeholder="AsKd"
          className="w-20 bg-stone-900 rounded px-2 py-1"
        />
      </Field>
      <Field label="Villain hole">
        <input
          value={villainHole}
          onChange={(e) => onChange({ villainHole: e.target.value })}
          placeholder="QcQh"
          className="w-20 bg-stone-900 rounded px-2 py-1"
        />
      </Field>
      <Field label="Effective stack (chips)">
        <input
          type="number"
          value={effectiveStack}
          onChange={(e) => onChange({ effectiveStack: parseInt(e.target.value || "0", 10) })}
          className="w-24 bg-stone-900 rounded px-2 py-1"
        />
      </Field>
      <Field label="Button">
        <select
          value={button}
          onChange={(e) => onChange({ button: e.target.value as Seat })}
          className="bg-stone-900 rounded px-2 py-1"
        >
          <option value="hero">hero</option>
          <option value="villain">villain</option>
        </select>
      </Field>
      <Field label="Model">
        <select
          value={presetId}
          onChange={(e) => onChange({ presetId: e.target.value })}
          className="bg-stone-900 rounded px-2 py-1"
        >
          {presets.map((p) => (
            <option key={p.selector_id} value={p.selector_id}>
              {p.selector_id}
            </option>
          ))}
        </select>
      </Field>
      <button
        data-testid="new-hand"
        onClick={onStart}
        disabled={disabled}
        className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50"
      >
        <kbd className="mr-2 opacity-60 text-xs">n</kbd>
        New hand
      </button>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col text-xs opacity-80 gap-1">
      <span>{label}</span>
      {children}
    </label>
  );
}
```

**Step 2:** Write `HandSummary.tsx`.

```tsx
import type { GameState } from "../api/types";

export function HandSummary({
  state,
  agreement,
  onNewHand,
}: {
  state: GameState;
  agreement: { total: number; diverged: number };
  onNewHand: () => void;
}) {
  const rate =
    agreement.total === 0
      ? null
      : Math.round(((agreement.total - agreement.diverged) / agreement.total) * 100);
  return (
    <div
      data-testid="hand-summary"
      className="rounded-xl bg-stone-900 p-4 text-stone-100 flex items-center justify-between gap-4"
    >
      <div>
        <div className="text-sm opacity-70">Hand {state.hand_id.slice(0, 8)} complete</div>
        {rate != null && (
          <div className="mt-1 text-lg">
            Agreement rate: <span className="font-bold">{rate}%</span>{" "}
            <span className="text-xs opacity-60">
              ({agreement.total - agreement.diverged}/{agreement.total})
            </span>
          </div>
        )}
      </div>
      <button
        onClick={onNewHand}
        className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500"
      >
        <kbd className="mr-2 opacity-60 text-xs">n</kbd>
        New hand
      </button>
    </div>
  );
}
```

**Step 3:** Lint + typecheck.

**Step 4:** Commit.

```bash
git add frontend/src/components/SetupPanel.tsx frontend/src/components/HandSummary.tsx
git commit -m "feat(frontend): add SetupPanel and HandSummary components"
```

---

### Task 7: Refactor `LiveCoach.tsx` to compose new components

**Files:**
- Modify (heavy rewrite): `frontend/src/routes/LiveCoach.tsx`

**Layout:**

```
+------------------------------------------------------------+
|  SetupPanel                                                |
+-------------------------------------+----------------------+
|                                     |                      |
|           PokerTable                |    AdvicePanel       |
|  (villain / board+pot / hero)       |   (streaming +       |
|                                     |    advice card)      |
|                                     |                      |
|  ActionBar (hero or villain turn)   |                      |
+-------------------------------------+----------------------+
|  HandSummary (when hand complete)                          |
+------------------------------------------------------------+
```

**Step 1:** Rewrite LiveCoach to compose components. Keep API logic identical; only the view changes.

Key points:
- `presetLabel` passed to AdvicePanel = current preset display text.
- Track `diverged` per current advice: set true when hero's action type ≠ advice.action or sizing differs by > 0.01 bb.
- On `n` hotkey, trigger `newHand()` if not already in-hand (or restart current).
- On `esc`, cancel stream.

**Skeleton:**

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createDecision, createHand, createSession, engineApply, engineStart,
  listPresets, recordAction,
} from "../api/client";
import type { Action, EngineSnapshot, PresetSummary, Seat } from "../api/types";
import { useAdviceStream } from "../api/useAdviceStream";
import { ActionBar } from "../components/ActionBar";
import { AdvicePanel } from "../components/AdvicePanel";
import { HandSummary } from "../components/HandSummary";
import { PokerTable } from "../components/PokerTable";
import { SetupPanel } from "../components/SetupPanel";
import { useHotkeys } from "../hooks/useHotkeys";

// (state + callbacks nearly identical to current implementation)

export function LiveCoach() {
  // ... state ...
  const handComplete = snapshot?.state.street === "complete" || snapshot?.state.street === "showdown";

  useHotkeys([
    { key: "n", handler: () => void newHand() },
    { key: "Escape", handler: () => resetStream() },
  ]);

  return (
    <div className="flex flex-col gap-4">
      <SetupPanel ... onStart={newHand} />
      {error && <div className="rounded bg-red-900/30 text-red-200 p-2 text-sm">{error}</div>}
      {snapshot && (
        <div className="flex gap-6 items-start">
          <div className="flex-1 flex flex-col gap-4">
            <PokerTable state={snapshot.state} />
            {snapshot.state.to_act && !handComplete && (
              <ActionBar
                state={snapshot.state}
                legal={snapshot.legal_actions}
                actor={snapshot.state.to_act}
                onAction={snapshot.state.to_act === "hero" ? heroAction : villainAction}
                onRequestAdvice={snapshot.state.to_act === "hero" ? requestAdvice : undefined}
                adviceDisabled={streamState.status === "thinking" || streamState.status === "streaming"}
              />
            )}
            {handComplete && (
              <HandSummary state={snapshot.state} agreement={agreement} onNewHand={newHand} />
            )}
          </div>
          <AdvicePanel
            stream={streamState}
            diverged={Boolean(currentDivergence)}
            presetLabel={presetId}
          />
        </div>
      )}
    </div>
  );
}
```

(full file derived mechanically from existing LiveCoach; inline styles removed, imports adjusted)

**Step 2:** Run typecheck + lint.

**Step 3:** Run existing Playwright test to confirm it still passes.

```bash
cd frontend && npx playwright test e2e/live-coach.spec.ts
```

If any testid moved, update the spec:
- `new-hand` → still on SetupPanel
- `size-raise` → replaced by `size-input` in ActionBar; update spec
- `action-raise` → stays
- `game-state` → replaced by `poker-table` container; update spec or add a compat testid

**Step 4:** Update Playwright spec to new testids.

Specifically: the spec fills `size-raise` and clicks `action-raise`. After refactor, it should fill `size-input` and click `action-raise`. Adjust:

```ts
await page.getByTestId("size-input").fill("3");
await page.getByTestId("action-raise").click();
await expect(page.getByTestId("seat-villain")).toBeVisible();
// Check the villain seat is highlighted (has a ring)
await expect(page.getByTestId("seat-villain")).toHaveClass(/ring-amber/);
```

**Step 5:** Run Playwright.

```bash
npx playwright test
```

Expected: both e2e tests pass.

**Step 6:** Commit.

```bash
git add frontend/src/routes/LiveCoach.tsx frontend/e2e/live-coach.spec.ts
git commit -m "feat(frontend): wire LiveCoach with new table, action bar, and advice panel"
```

---

### Task 8: App shell polish + session summary sweep

**Files:**
- Modify: `frontend/src/App.tsx` — nav styled with Tailwind, dark background
- Verify: session summary shows correctly when `state.street === "complete"`

**Step 1:** Replace inline styles in App.tsx with Tailwind utilities.

```tsx
import { useState } from "react";
import { LiveCoach } from "./routes/LiveCoach";
import { SpotAnalysis } from "./routes/SpotAnalysis";

type Route = "live" | "spot";

export function App() {
  const [route, setRoute] = useState<Route>("live");
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 font-sans">
      <nav className="flex gap-2 px-6 py-3 border-b border-stone-800">
        <NavLink current={route} value="live" label="Live Coach" onSelect={setRoute} />
        <NavLink current={route} value="spot" label="Spot Analysis" onSelect={setRoute} />
      </nav>
      <main className="px-6 py-6">
        {route === "live" ? <LiveCoach /> : <SpotAnalysis />}
      </main>
    </div>
  );
}

function NavLink({
  current, value, label, onSelect,
}: {
  current: Route; value: Route; label: string; onSelect: (r: Route) => void;
}) {
  const on = current === value;
  return (
    <button
      data-testid={`nav-${value}`}
      onClick={() => onSelect(value)}
      className={`px-3 py-1.5 rounded-md text-sm font-medium ${
        on ? "bg-stone-800 text-white" : "text-stone-400 hover:text-stone-200"
      }`}
    >
      {label}
    </button>
  );
}
```

**Step 2:** Manual QA pass via `make dev`:
- New hand → table renders felt, cards legible, hero glowing ring
- Take a legal action via hotkey (`r`, then `3` preset, `enter` to confirm — or click)
- Press `space` to request advice (if Claude key set)
- Verify reasoning streams into the advice panel, advice card animates in
- Override with a different action → diverged badge appears
- Ride a hand to showdown → HandSummary replaces ActionBar

**Step 3:** Commit.

```bash
git add frontend/src/App.tsx
git commit -m "style(frontend): dark app shell with Tailwind utilities"
```

---

### Task 9: Final sweep — lint, type, test, remove dead styles

**Step 1:** `make lint` and `make test` — all green.

**Step 2:** `npx playwright test` — both e2e pass.

**Step 3:** Commit any stragglers.

```bash
git commit -am "chore(frontend): final polish after UI upgrade"  # if anything
```

---

## What is intentionally NOT in this plan (deferred)

- Full spot analysis UI upgrade (same treatment, different shape — lands in a follow-up)
- Framer Motion / richer animations
- Mobile/responsive breakpoints — desktop-first for MVP
- Theme toggle (dark-only for now)
- Prompt editor UI (Phase 6)
- History viewer (Phase 6)
- Showdown villain-card modal (Phase 6)

## Risk + rollback

- Tailwind 4 is recent; if `@tailwindcss/vite` misbehaves, fall back to `tailwindcss@^3` + PostCSS config (well-trodden path).
- If Playwright testids drift during refactor, the e2e gate catches it. If needed, add `data-testid` compatibility aliases until tests are updated.
- All commits are incremental — any task can be reverted without affecting the others.
