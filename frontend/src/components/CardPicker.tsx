import { useMemo, useState } from "react";
import { SUIT_META, type Suit } from "../utils/cards";
import { PlayingCard } from "./PlayingCard";

const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;
const SUITS: Suit[] = ["s", "h", "d", "c"];

type SlotId = "h1" | "h2" | "v1" | "v2";

const SLOT_ORDER: SlotId[] = ["h1", "h2", "v1", "v2"];

const SLOT_META: Record<SlotId, { owner: "hero" | "villain"; label: string }> = {
  h1: { owner: "hero", label: "Hero 1" },
  h2: { owner: "hero", label: "Hero 2" },
  v1: { owner: "villain", label: "Villain 1" },
  v2: { owner: "villain", label: "Villain 2" },
};

function allSlotsFilled(slots: Record<SlotId, string | null>): boolean {
  return SLOT_ORDER.every((s) => slots[s] != null);
}

export function CardPicker({
  heroHole,
  villainHole,
  onChange,
}: {
  heroHole: [string, string] | null;
  villainHole: [string, string] | null;
  onChange: (value: {
    hero: [string, string] | null;
    villain: [string, string] | null;
  }) => void;
}) {
  // Uncontrolled: we own the per-slot state locally. Parent props seed the
  // initial state only — see commit history on this file for the why.
  const [slots, setSlots] = useState<Record<SlotId, string | null>>(() => ({
    h1: heroHole?.[0] ?? null,
    h2: heroHole?.[1] ?? null,
    v1: villainHole?.[0] ?? null,
    v2: villainHole?.[1] ?? null,
  }));
  const [activeSlot, setActiveSlot] = useState<SlotId>("h1");
  // Collapsed by default when everything is already set on mount; otherwise
  // open so the user can pick.
  const [expanded, setExpanded] = useState<boolean>(() => !allSlotsFilled({
    h1: heroHole?.[0] ?? null,
    h2: heroHole?.[1] ?? null,
    v1: villainHole?.[0] ?? null,
    v2: villainHole?.[1] ?? null,
  }));

  const usedCards = useMemo(
    () => new Set(Object.values(slots).filter((x): x is string => x != null)),
    [slots],
  );

  const commit = (next: Record<SlotId, string | null>) => {
    setSlots(next);
    const hero: [string, string] | null =
      next.h1 && next.h2 ? [next.h1, next.h2] : null;
    const villain: [string, string] | null =
      next.v1 && next.v2 ? [next.v1, next.v2] : null;
    onChange({ hero, villain });
  };

  const firstEmptyAfter = (
    start: SlotId,
    source: Record<SlotId, string | null>,
  ): SlotId => {
    const idx = SLOT_ORDER.indexOf(start);
    for (let i = 1; i <= SLOT_ORDER.length; i++) {
      const next = SLOT_ORDER[(idx + i) % SLOT_ORDER.length];
      if (!source[next]) return next;
    }
    return start;
  };

  const pickCard = (code: string) => {
    if (usedCards.has(code) && slots[activeSlot] !== code) return;
    const next = { ...slots, [activeSlot]: code };
    commit(next);
    setActiveSlot(firstEmptyAfter(activeSlot, next));
  };

  const selectSlot = (slot: SlotId) => {
    setActiveSlot(slot);
    setExpanded(true);
  };

  const clearSlot = (slot: SlotId) => {
    const next = { ...slots, [slot]: null };
    commit(next);
    setActiveSlot(slot);
    setExpanded(true);
  };

  const clearAll = () => {
    commit({ h1: null, h2: null, v1: null, v2: null });
    setActiveSlot("h1");
    setExpanded(true);
  };

  const dealRandom = () => {
    const taken = new Set(usedCards);
    const pool: string[] = [];
    for (const r of RANKS) for (const s of SUITS) pool.push(r + s);
    const available = pool.filter((c) => !taken.has(c));
    for (let i = available.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [available[i], available[j]] = [available[j], available[i]];
    }
    const next = { ...slots };
    for (const slot of SLOT_ORDER) {
      if (!next[slot] && available.length > 0) next[slot] = available.shift()!;
    }
    commit(next);
    // Dealing completes the selection — close the grid so the table is the
    // primary focus.
    if (allSlotsFilled(next)) setExpanded(false);
  };

  return (
    <div className="flex flex-col gap-3" data-testid="card-picker">
      <div className="flex items-center gap-4 flex-wrap">
        <SlotGroup
          title="Hero"
          slots={["h1", "h2"]}
          active={activeSlot}
          values={slots}
          onSlotClick={selectSlot}
          onSlotClear={clearSlot}
        />
        <div className="w-px self-stretch bg-white/10" />
        <SlotGroup
          title="Villain"
          slots={["v1", "v2"]}
          active={activeSlot}
          values={slots}
          onSlotClick={selectSlot}
          onSlotClear={clearSlot}
        />
        <div className="ml-auto flex gap-2 items-center">
          <button
            data-testid="card-deal-random"
            onClick={dealRandom}
            className="px-3 py-1.5 rounded-md bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 ring-1 ring-white/10 transition"
          >
            Deal random
          </button>
          <button
            data-testid="card-clear"
            onClick={clearAll}
            className="px-3 py-1.5 rounded-md bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 ring-1 ring-white/10 transition"
          >
            Clear
          </button>
          <button
            data-testid="card-picker-toggle"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            aria-controls="card-picker-grid"
            title={expanded ? "Hide card grid" : "Show card grid"}
            className="px-2 py-1.5 rounded-md bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 ring-1 ring-white/10 transition flex items-center gap-1"
          >
            <span
              className={`inline-block transition-transform ${expanded ? "rotate-180" : ""}`}
              aria-hidden
            >
              ▾
            </span>
            <span className="text-xs uppercase tracking-wider">
              {expanded ? "Hide" : "Edit"}
            </span>
          </button>
        </div>
      </div>

      {expanded && (
        <div
          id="card-picker-grid"
          className="grid gap-1 bg-stone-950 rounded-lg p-2 ring-1 ring-white/5 anim-fade-up"
          style={{ gridTemplateColumns: `auto repeat(${RANKS.length}, minmax(0, 1fr))` }}
        >
          {SUITS.map((suit) => (
            <SuitRow
              key={suit}
              suit={suit}
              usedCards={usedCards}
              onPick={pickCard}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function SlotGroup({
  title,
  slots,
  active,
  values,
  onSlotClick,
  onSlotClear,
}: {
  title: string;
  slots: SlotId[];
  active: SlotId;
  values: Record<SlotId, string | null>;
  onSlotClick: (s: SlotId) => void;
  onSlotClear: (s: SlotId) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] uppercase tracking-widest opacity-60">{title}</span>
      <div className="flex gap-2">
        {slots.map((s) => (
          <div key={s} className="relative group">
            <button
              data-testid={`slot-${s}`}
              onClick={() => onSlotClick(s)}
              title="click to select, then pick a card from the grid"
              className={`rounded-md p-0.5 transition ${
                active === s
                  ? "ring-2 ring-amber-400 shadow-lg shadow-amber-500/30"
                  : "ring-1 ring-white/10 hover:ring-white/30"
              }`}
            >
              {values[s] ? (
                <PlayingCard code={values[s]} size="sm" />
              ) : (
                <div className="w-10 h-14 rounded-md border-2 border-dashed border-white/20 flex items-center justify-center text-[10px] text-stone-500">
                  {SLOT_META[s].label.split(" ")[1]}
                </div>
              )}
            </button>
            {values[s] && (
              <button
                data-testid={`slot-clear-${s}`}
                onClick={() => onSlotClear(s)}
                title="clear this slot"
                aria-label={`clear ${SLOT_META[s].label}`}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-stone-700 text-stone-100 text-[10px] leading-none flex items-center justify-center opacity-0 group-hover:opacity-100 ring-1 ring-stone-900 transition"
              >
                ×
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SuitRow({
  suit,
  usedCards,
  onPick,
}: {
  suit: Suit;
  usedCards: Set<string>;
  onPick: (code: string) => void;
}) {
  const meta = SUIT_META[suit];
  return (
    <>
      <div
        className={`flex items-center justify-center text-lg pr-1 ${meta.colorClass}`}
        aria-hidden
      >
        {meta.glyph}
      </div>
      {RANKS.map((rank) => {
        const code = rank + suit;
        const used = usedCards.has(code);
        return (
          <button
            key={code}
            data-testid={`grid-${code}`}
            data-used={used ? "true" : undefined}
            onClick={() => onPick(code)}
            disabled={used}
            className={`aspect-[5/7] rounded ${
              used
                ? "opacity-30 cursor-not-allowed"
                : "hover:scale-110 hover:z-10 transition-transform"
            }`}
          >
            <PlayingCard code={code} size="sm" />
          </button>
        );
      })}
    </>
  );
}
