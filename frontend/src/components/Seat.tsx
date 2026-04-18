import type { GameState, Seat as SeatId } from "../api/types";
import { PlayingCard } from "./PlayingCard";

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
  const isToAct = state.to_act === id;
  const isButton = state.button === id;
  const hole = id === "hero" ? state.hero_hole : state.villain_hole;
  const stackBb = stack / state.bb;
  const effectiveBb = state.effective_stack / state.bb;
  const depthPct =
    effectiveBb > 0 ? Math.max(0, Math.min(100, (stackBb / effectiveBb) * 100)) : 0;

  return (
    <div
      data-testid={`seat-${id}`}
      data-to-act={isToAct ? "true" : undefined}
      className={`flex flex-col items-center gap-2 rounded-2xl px-5 py-3 bg-black/40 backdrop-blur-sm transition-all ${
        isToAct
          ? "ring-4 ring-amber-400 shadow-xl shadow-amber-500/40"
          : "ring-1 ring-white/10"
      }`}
    >
      <div className="flex items-baseline gap-2 text-white">
        <span className="font-semibold tracking-wide">{label}</span>
        <span
          data-testid={`seat-${id}-position`}
          className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
            isButton
              ? "bg-amber-500/80 text-amber-950"
              : "bg-white/15 text-white/80"
          }`}
        >
          {isButton ? "BTN" : "BB"}
        </span>
        <span className="text-xs opacity-70 tabular-nums">{stackBb.toFixed(1)} bb</span>
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
      <div
        data-testid={`seat-${id}-depth`}
        className="h-1 w-full rounded-full bg-white/10 overflow-hidden"
      >
        <div
          className="h-full bg-emerald-400/80 transition-[width] duration-300"
          style={{ width: `${depthPct}%` }}
        />
      </div>
    </div>
  );
}
