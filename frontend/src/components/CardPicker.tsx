import { useMemo, useState } from "react";
import { PlayingCard } from "./PlayingCard";

const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;
const SUITS = ["s", "h", "d", "c"] as const;
const SUIT_LABEL: Record<(typeof SUITS)[number], { glyph: string; color: string }> = {
  s: { glyph: "♠", color: "text-stone-200" },
  h: { glyph: "♥", color: "text-red-400" },
  d: { glyph: "♦", color: "text-red-400" },
  c: { glyph: "♣", color: "text-stone-200" },
};

type SlotId = "h1" | "h2" | "v1" | "v2";

const SLOT_ORDER: SlotId[] = ["h1", "h2", "v1", "v2"];

const SLOT_META: Record<SlotId, { owner: "hero" | "villain"; label: string }> = {
  h1: { owner: "hero", label: "Hero 1" },
  h2: { owner: "hero", label: "Hero 2" },
  v1: { owner: "villain", label: "Villain 1" },
  v2: { owner: "villain", label: "Villain 2" },
};

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
  const [activeSlot, setActiveSlot] = useState<SlotId>("h1");

  const slots: Record<SlotId, string | null> = useMemo(
    () => ({
      h1: heroHole?.[0] ?? null,
      h2: heroHole?.[1] ?? null,
      v1: villainHole?.[0] ?? null,
      v2: villainHole?.[1] ?? null,
    }),
    [heroHole, villainHole],
  );

  const usedCards = useMemo(
    () => new Set(Object.values(slots).filter((x): x is string => x != null)),
    [slots],
  );

  const commit = (next: Record<SlotId, string | null>) => {
    const hero: [string, string] | null =
      next.h1 && next.h2 ? [next.h1, next.h2] : null;
    const villain: [string, string] | null =
      next.v1 && next.v2 ? [next.v1, next.v2] : null;
    onChange({ hero, villain });
  };

  const firstEmptyAfter = (start: SlotId): SlotId => {
    const idx = SLOT_ORDER.indexOf(start);
    for (let i = 1; i <= SLOT_ORDER.length; i++) {
      const next = SLOT_ORDER[(idx + i) % SLOT_ORDER.length];
      if (!slots[next]) return next;
    }
    return start;
  };

  const pickCard = (code: string) => {
    if (usedCards.has(code)) return;
    const next = { ...slots, [activeSlot]: code };
    commit(next);
    const advance = firstEmptyAfter(activeSlot);
    setActiveSlot(advance);
  };

  const clearSlot = (slot: SlotId) => {
    const next = { ...slots, [slot]: null };
    commit(next);
    setActiveSlot(slot);
  };

  const clearAll = () => {
    commit({ h1: null, h2: null, v1: null, v2: null });
    setActiveSlot("h1");
  };

  const dealRandom = () => {
    const taken = new Set(usedCards);
    const pool: string[] = [];
    for (const r of RANKS) for (const s of SUITS) pool.push(r + s);
    const available = pool.filter((c) => !taken.has(c));
    // shuffle
    for (let i = available.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [available[i], available[j]] = [available[j], available[i]];
    }
    const next = { ...slots };
    for (const slot of SLOT_ORDER) {
      if (!next[slot] && available.length > 0) next[slot] = available.shift()!;
    }
    commit(next);
  };

  return (
    <div className="flex flex-col gap-3" data-testid="card-picker">
      <div className="flex items-center gap-4">
        <SlotGroup
          title="Hero"
          slots={["h1", "h2"]}
          active={activeSlot}
          values={slots}
          onSlotClick={(s) => setActiveSlot(s)}
          onSlotClear={clearSlot}
        />
        <div className="w-px self-stretch bg-white/10" />
        <SlotGroup
          title="Villain"
          slots={["v1", "v2"]}
          active={activeSlot}
          values={slots}
          onSlotClick={(s) => setActiveSlot(s)}
          onSlotClear={clearSlot}
        />
        <div className="ml-auto flex gap-2">
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
        </div>
      </div>

      <div
        className="grid gap-1 bg-stone-950 rounded-lg p-2 ring-1 ring-white/5"
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
          <button
            key={s}
            data-testid={`slot-${s}`}
            onClick={() => (values[s] ? onSlotClear(s) : onSlotClick(s))}
            onDoubleClick={() => onSlotClear(s)}
            title={values[s] ? "click to clear" : "click to select this slot"}
            className={`rounded-md p-0.5 transition ${
              active === s && !values[s]
                ? "ring-2 ring-amber-400 shadow-lg shadow-amber-500/30"
                : "ring-1 ring-white/10"
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
  suit: (typeof SUITS)[number];
  usedCards: Set<string>;
  onPick: (code: string) => void;
}) {
  const meta = SUIT_LABEL[suit];
  return (
    <>
      <div
        className={`flex items-center justify-center text-lg pr-1 ${meta.color}`}
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
