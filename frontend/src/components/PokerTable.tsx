import type { GameState } from "../api/types";
import { Board } from "./Board";
import { Pot } from "./Pot";
import { Seat } from "./Seat";

export function PokerTable({ state }: { state: GameState }) {
  const showVillainHole =
    state.pending_reveal === null &&
    (state.street === "showdown" || state.street === "complete");
  const potBb = state.pot / state.bb;
  const committedBb = (state.committed.hero + state.committed.villain) / state.bb;
  const streetLabel = state.street.charAt(0).toUpperCase() + state.street.slice(1);

  return (
    <div
      data-testid="poker-table"
      className="bg-felt rounded-[48px] px-10 py-8 shadow-2xl border-8 border-stone-900"
    >
      <div className="flex flex-col items-center gap-6 min-h-[420px]">
        <Seat id="villain" label="Villain" state={state} showHole={showVillainHole} />

        <div className="flex flex-col items-center gap-3">
          <div className="text-[10px] uppercase tracking-[0.3em] text-white/60">
            {streetLabel}
          </div>
          <Board cards={state.board} />
          <Pot potBb={potBb} committedBb={committedBb} />
        </div>

        <Seat id="hero" label="Hero" state={state} showHole={true} />
      </div>
    </div>
  );
}
