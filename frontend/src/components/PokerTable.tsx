import type { GameState, Seat as SeatId } from "../api/types";
import { Board } from "./Board";
import { Pot } from "./Pot";
import { Seat } from "./Seat";

function BetChips({ bb, seat }: { bb: number; seat: SeatId }) {
  if (bb <= 0) return null;
  return (
    <div
      data-testid={`bet-${seat}`}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/50 text-white text-xs font-medium tabular-nums ring-1 ring-white/10 backdrop-blur-sm"
    >
      <span className="w-2 h-2 rounded-full bg-[color:var(--color-chip-gold)] ring-1 ring-yellow-200/40" />
      {bb.toFixed(1)} bb
    </div>
  );
}

export function PokerTable({ state }: { state: GameState }) {
  const showVillainHole =
    state.pending_reveal === null &&
    (state.street === "showdown" || state.street === "complete");
  const potBb = state.pot / state.bb;
  const heroBetBb = state.committed.hero / state.bb;
  const villainBetBb = state.committed.villain / state.bb;
  const streetLabel = state.street.charAt(0).toUpperCase() + state.street.slice(1);

  return (
    <div
      data-testid="poker-table"
      className="bg-felt rounded-[48px] px-10 py-8 shadow-2xl border-8 border-stone-900"
    >
      <div className="flex flex-col items-center gap-4 min-h-[420px]">
        <Seat id="villain" label="Villain" state={state} showHole={showVillainHole} />
        <BetChips bb={villainBetBb} seat="villain" />

        <div className="flex flex-col items-center gap-3">
          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">
            {streetLabel}
          </div>
          <Board cards={state.board} />
          <Pot potBb={potBb} />
        </div>

        <BetChips bb={heroBetBb} seat="hero" />
        <Seat id="hero" label="Hero" state={state} showHole={true} />
      </div>
    </div>
  );
}
