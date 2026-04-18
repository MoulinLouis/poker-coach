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
      className="rounded-xl bg-stone-900 p-4 text-stone-100 flex items-center justify-between gap-4 ring-1 ring-white/5 anim-fade-up"
    >
      <div>
        <div className="text-xs uppercase tracking-widest opacity-60">
          Hand {state.hand_id.slice(0, 8)} complete
        </div>
        {rate != null ? (
          <div className="mt-1 text-lg">
            Agreement rate: <span className="font-bold tabular-nums">{rate}%</span>
            <span className="ml-2 text-xs opacity-60 tabular-nums">
              ({agreement.total - agreement.diverged}/{agreement.total})
            </span>
          </div>
        ) : (
          <div className="mt-1 text-sm opacity-70">No advice requested this hand.</div>
        )}
      </div>
      <button
        onClick={onNewHand}
        className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 transition"
      >
        <kbd className="mr-2 opacity-60 text-[10px] font-mono">n</kbd>
        New hand
      </button>
    </div>
  );
}
