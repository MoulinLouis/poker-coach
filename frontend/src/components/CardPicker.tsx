import { useMemo, useState } from "react";
import { SUITS, type Suit } from "../utils/cards";
import { PlayingCard } from "./PlayingCard";
import { useLocale } from "../i18n";

const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;
const SUIT_KEYS = ["s", "h", "d", "c"] as const satisfies readonly Suit[];

type SlotId = "h1" | "h2" | "v1" | "v2";

const SLOT_ORDER: SlotId[] = ["h1", "h2", "v1", "v2"];

const SLOT_META: Record<SlotId, { owner: "hero" | "villain"; slotNumber: "1" | "2" }> = {
  h1: { owner: "hero", slotNumber: "1" },
  h2: { owner: "hero", slotNumber: "2" },
  v1: { owner: "villain", slotNumber: "1" },
  v2: { owner: "villain", slotNumber: "2" },
};

function slotLabel(t: (k: "cardPicker.hero" | "cardPicker.villain") => string, id: SlotId) {
  const meta = SLOT_META[id];
  const owner = meta.owner === "hero" ? t("cardPicker.hero") : t("cardPicker.villain");
  return `${owner} ${meta.slotNumber}`;
}

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
  const { t } = useLocale();
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
    for (const r of RANKS) for (const s of SUIT_KEYS) pool.push(r + s);
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
          title={t("cardPicker.hero")}
          slots={["h1", "h2"]}
          active={activeSlot}
          values={slots}
          onSlotClick={selectSlot}
          onSlotClear={clearSlot}
        />
        <div
          className="w-px self-stretch"
          style={{ background: "rgba(201,162,94,0.2)" }}
        />
        <SlotGroup
          title={t("cardPicker.villain")}
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
            className="px-3 py-1.5 rounded-md font-mono text-[10px] uppercase tracking-[0.25em] transition"
            style={{
              color: "var(--color-bone)",
              background: "rgba(10,7,6,0.5)",
              border: "1px solid rgba(201,162,94,0.25)",
            }}
          >
            {t("cardPicker.deal")}
          </button>
          <button
            data-testid="card-clear"
            onClick={clearAll}
            className="px-3 py-1.5 rounded-md font-mono text-[10px] uppercase tracking-[0.25em] transition"
            style={{
              color: "var(--color-parchment)",
              background: "rgba(10,7,6,0.5)",
              border: "1px solid rgba(201,162,94,0.15)",
            }}
          >
            {t("cardPicker.clear")}
          </button>
          <button
            data-testid="card-picker-toggle"
            onClick={() => setExpanded((e) => !e)}
            aria-expanded={expanded}
            aria-controls="card-picker-grid"
            title={expanded ? t("cardPicker.tipHideGrid") : t("cardPicker.tipShowGrid")}
            className="px-2 py-1.5 rounded-md font-mono text-[10px] uppercase tracking-[0.25em] transition flex items-center gap-1.5"
            style={{
              color: "var(--color-gold-pale)",
              background: "rgba(201,162,94,0.08)",
              border: "1px solid rgba(201,162,94,0.35)",
            }}
          >
            <span
              className={`inline-block transition-transform ${expanded ? "rotate-180" : ""}`}
              aria-hidden
            >
              ▾
            </span>
            <span>{expanded ? t("cardPicker.hide") : t("cardPicker.edit")}</span>
          </button>
        </div>
      </div>

      {expanded && (
        <div
          id="card-picker-grid"
          className="grid gap-1 rounded-lg p-3 anim-fade-up overflow-x-auto"
          style={{
            gridTemplateColumns: `auto repeat(${RANKS.length}, minmax(28px, 1fr))`,
            minWidth: "min-content",
            background:
              "linear-gradient(180deg, rgba(10,7,6,0.7), rgba(10,7,6,0.5))",
            border: "1px solid rgba(201,162,94,0.15)",
          }}
        >
          {SUIT_KEYS.map((suit) => (
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
  const { t } = useLocale();
  return (
    <div className="flex flex-col gap-1.5">
      <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
        {title}
      </span>
      <div className="flex gap-2">
        {slots.map((s) => (
          <div key={s} className="relative group">
            <button
              data-testid={`slot-${s}`}
              onClick={() => onSlotClick(s)}
              title={t("cardPicker.tipSlotSelect")}
              className="rounded-md p-0.5 transition"
              style={{
                boxShadow:
                  active === s
                    ? "0 0 0 2px var(--color-gold), 0 4px 16px -4px rgba(240,211,138,0.5)"
                    : "0 0 0 1px rgba(201,162,94,0.15)",
              }}
            >
              {values[s] ? (
                <PlayingCard code={values[s]} size="sm" />
              ) : (
                <div
                  className="w-10 h-14 rounded-md flex items-center justify-center font-mono text-[9px] uppercase tracking-widest"
                  style={{
                    color: "var(--color-parchment-dim)",
                    border: "1px dashed rgba(201,162,94,0.3)",
                    background:
                      "repeating-linear-gradient(135deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 2px, transparent 2px, transparent 6px)",
                  }}
                >
                  {SLOT_META[s].slotNumber}
                </div>
              )}
            </button>
            {values[s] && (
              <button
                data-testid={`slot-clear-${s}`}
                onClick={() => onSlotClear(s)}
                title={t("cardPicker.tipSlotClear")}
                aria-label={`${t("cardPicker.ariaClearPrefix")} ${slotLabel(t, s)}`}
                className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full text-[10px] leading-none flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                style={{
                  background: "var(--color-ink)",
                  color: "var(--color-gold-pale)",
                  border: "1px solid var(--color-gold-deep)",
                }}
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
  const meta = SUITS[suit];
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
