import { useMemo, useState } from "react";
import { SUITS, type Suit } from "../utils/cards";
import { PlayingCard } from "./PlayingCard";
import { useLocale } from "../i18n";
import type { DictKey } from "../i18n";

const RANKS = ["A","K","Q","J","T","9","8","7","6","5","4","3","2"] as const;
const SUIT_KEYS = ["s","h","d","c"] as const satisfies readonly Suit[];

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

  const { t } = useLocale();
  const headerKey: DictKey = (
    {
      flop: "boardPicker.flop",
      turn: "boardPicker.turn",
      river: "boardPicker.river",
      runout: "boardPicker.runout",
    } as const
  )[street];

  const pickCard = (code: string) => {
    if (used.has(code) && slots[activeIdx] !== code) return;
    const next = [...slots];
    next[activeIdx] = code;
    setSlots(next);
    const nextEmpty = next.findIndex((x) => x == null);
    if (nextEmpty >= 0) setActiveIdx(nextEmpty);
  };

  const dealRandom = () => {
    const pool: string[] = [];
    for (const r of RANKS) for (const s of SUIT_KEYS) pool.push(r + s);
    const available = pool.filter((c) => !used.has(c));
    for (let i = available.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [available[i], available[j]] = [available[j], available[i]];
    }
    const next = [...slots];
    for (let i = 0; i < next.length; i++) {
      if (next[i] == null && available.length > 0) next[i] = available.shift()!;
    }
    setSlots(next);
    const nextEmpty = next.findIndex((x) => x == null);
    setActiveIdx(nextEmpty >= 0 ? nextEmpty : 0);
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
        <h2 className="text-lg font-semibold text-stone-100">{t(headerKey)}</h2>

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
          {SUIT_KEYS.map((suit) => (
            <SuitRow key={suit} suit={suit} used={used} onPick={pickCard} />
          ))}
        </div>

        <div className="flex justify-end gap-2">
          <button
            data-testid="board-picker-random"
            onClick={dealRandom}
            className="px-4 py-2 rounded-md bg-stone-800 hover:bg-stone-700 text-sm text-stone-100 ring-1 ring-white/10 transition"
          >
            {t("boardPicker.random")}
          </button>
          <button
            data-testid="board-picker-confirm"
            onClick={confirm}
            disabled={!allFilled}
            className="px-4 py-2 rounded-md bg-amber-500 text-stone-950 font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-400 transition"
          >
            {t("boardPicker.confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}

function SuitRow({
  suit,
  used,
  onPick,
}: {
  suit: Suit;
  used: Set<string>;
  onPick: (code: string) => void;
}) {
  const { glyph, color } = SUITS[suit];
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
              isUsed
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
