import { useLocale } from "../i18n";
import type { DictKey } from "../i18n";
import { PlayingCard } from "./PlayingCard";

const SLOT_LABEL_KEYS: readonly DictKey[] = [
  "board.slotFlop",
  "board.slotFlop",
  "board.slotFlop",
  "board.slotTurn",
  "board.slotRiver",
];

export function Board({ cards }: { cards: string[] }) {
  const { t } = useLocale();
  return (
    <div
      data-testid="board"
      className="relative flex items-center gap-1.5 sm:gap-3 px-2 sm:px-4 py-3 rounded-xl"
    >
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex flex-col items-center gap-1.5">
          {cards[i] ? (
            <div className="anim-zoom-in" style={{ animationDelay: `${i * 70}ms` }}>
              <PlayingCard code={cards[i]} size="board" />
            </div>
          ) : (
            <div
              className="w-[3.25rem] sm:w-[4rem] lg:w-[5.2rem] h-[4.6rem] sm:h-[5.7rem] lg:h-[7.4rem] rounded-[8px] flex items-center justify-center"
              style={{
                border: "1px dashed rgba(237, 227, 204, 0.18)",
                background:
                  "repeating-linear-gradient(135deg, rgba(255,255,255,0.015) 0px, rgba(255,255,255,0.015) 2px, transparent 2px, transparent 8px)",
              }}
            >
              <span className="text-[8px] sm:text-[9px] uppercase tracking-[0.25em] sm:tracking-[0.3em] text-[color:var(--color-parchment-dim)] opacity-50">
                {t(SLOT_LABEL_KEYS[i])}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
