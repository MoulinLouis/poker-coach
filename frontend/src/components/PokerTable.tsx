import type { GameState, Seat as SeatId, Street } from "../api/types";
import { useLocale } from "../i18n";
import type { DictKey } from "../i18n";
import { Board } from "./Board";
import { Pot } from "./Pot";
import { Seat } from "./Seat";

const STREET_KEYS: Record<Street, DictKey> = {
  preflop: "pokerTable.street.preflop",
  flop: "pokerTable.street.flop",
  turn: "pokerTable.street.turn",
  river: "pokerTable.street.river",
  showdown: "pokerTable.street.showdown",
  complete: "pokerTable.street.complete",
};

function BetChips({ bb, seat }: { bb: number; seat: SeatId }) {
  const { t } = useLocale();
  if (bb <= 0) return null;
  return (
    <div
      data-testid={`bet-${seat}`}
      className="relative flex items-center gap-2 pl-1.5 pr-3 py-1 rounded-full"
      style={{
        background:
          "linear-gradient(180deg, rgba(10,7,6,0.85), rgba(10,7,6,0.65))",
        border: "1px solid rgba(201,162,94,0.4)",
        boxShadow:
          "inset 0 1px 0 rgba(201,162,94,0.3), 0 4px 10px -4px rgba(0,0,0,0.7)",
      }}
    >
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
        <defs>
          <linearGradient id={`chip-${seat}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-gold-bright)" />
            <stop offset="100%" stopColor="var(--color-gold-deep)" />
          </linearGradient>
        </defs>
        <circle cx="9" cy="9" r="7.5" fill={`url(#chip-${seat})`} />
        <circle
          cx="9"
          cy="9"
          r="5"
          fill="none"
          stroke="var(--color-gold-shadow)"
          strokeWidth="0.7"
          strokeDasharray="2 1.5"
        />
        <circle cx="9" cy="9" r="2" fill="var(--color-oxblood-deep)" />
      </svg>
      <span className="font-mono text-[11px] tabular-nums text-[color:var(--color-bone)]">
        {bb.toFixed(1)}
        <span className="opacity-50 ml-0.5">{t("pokerTable.bbUnit")}</span>
      </span>
    </div>
  );
}

function Fleuron({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 60 60"
      className={className}
      aria-hidden
      fill="none"
      stroke="currentColor"
      strokeWidth="0.8"
    >
      <path d="M30 8 L34 22 L48 26 L34 30 L30 44 L26 30 L12 26 L26 22 Z" />
      <circle cx="30" cy="26" r="3" />
      <path d="M14 44 Q22 38 30 44 Q38 50 46 44" />
      <circle cx="30" cy="48" r="1.4" fill="currentColor" />
    </svg>
  );
}

export function PokerTable({ state }: { state: GameState }) {
  const { t } = useLocale();
  const showVillainHole =
    state.pending_reveal === null &&
    (state.street === "showdown" || state.street === "complete");
  const potBb = state.pot / state.bb;
  const heroBetBb = state.committed.hero / state.bb;
  const villainBetBb = state.committed.villain / state.bb;
  const streetLabel = t(STREET_KEYS[state.street]);

  return (
    <div
      data-testid="poker-table"
      className="relative rounded-[32px] sm:rounded-[52px] p-[6px] sm:p-[10px]"
      style={{
        background:
          "linear-gradient(140deg, #1a0d0f 0%, #2a1012 40%, #130708 100%)",
        boxShadow:
          "0 30px 80px -30px rgba(0,0,0,0.9), 0 0 0 1px rgba(201,162,94,0.12)",
      }}
    >
      {/* gold inlay ring */}
      <div
        aria-hidden
        className="absolute inset-[3px] sm:inset-[5px] rounded-[28px] sm:rounded-[48px] pointer-events-none"
        style={{
          border: "1px solid rgba(201,162,94,0.4)",
          boxShadow:
            "inset 0 0 0 2px rgba(10,7,6,0.8), inset 0 0 0 3px rgba(201,162,94,0.18)",
        }}
      />

      <div className="relative bg-felt rounded-[26px] sm:rounded-[44px] px-3 sm:px-8 lg:px-10 py-5 sm:py-8 lg:py-10 overflow-hidden">
        {/* deco corner fleurons — desktop only (too busy on phone) */}
        <Fleuron className="hidden sm:block absolute top-3 left-3 w-10 h-10 text-[color:var(--color-gold)]/50" />
        <Fleuron className="hidden sm:block absolute top-3 right-3 w-10 h-10 text-[color:var(--color-gold)]/50 -scale-x-100" />
        <Fleuron className="hidden sm:block absolute bottom-3 left-3 w-10 h-10 text-[color:var(--color-gold)]/50 -scale-y-100" />
        <Fleuron className="hidden sm:block absolute bottom-3 right-3 w-10 h-10 text-[color:var(--color-gold)]/50 -scale-100" />

        {/* Inner field — oval highlight */}
        <div
          aria-hidden
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[85%] h-[75%] rounded-[50%] pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse at center, rgba(26,111,83,0.4) 0%, transparent 70%)",
          }}
        />

        <div className="relative flex flex-col items-center gap-3 sm:gap-5 min-h-[380px] sm:min-h-[460px]">
          <Seat id="villain" label={t("pokerTable.villain")} state={state} showHole={showVillainHole} />
          <BetChips bb={villainBetBb} seat="villain" />

          <div className="flex flex-col items-center gap-3 sm:gap-4 my-1 sm:my-2">
            {/* Street marker — deco banderole */}
            <div className="flex items-center gap-2 sm:gap-3">
              <span className="block w-6 sm:w-10 h-px bg-[color:var(--color-gold)]/50" />
              <span className="font-mono text-[10px] sm:text-[11px] tracking-[0.3em] sm:tracking-[0.4em] uppercase text-[color:var(--color-gold-pale)]">
                {streetLabel}
              </span>
              <span className="block w-6 sm:w-10 h-px bg-[color:var(--color-gold)]/50" />
            </div>

            <Board cards={state.board} />
            <Pot potBb={potBb} />
          </div>

          <BetChips bb={heroBetBb} seat="hero" />
          <Seat id="hero" label={t("pokerTable.hero")} state={state} showHole={true} />
        </div>
      </div>
    </div>
  );
}
