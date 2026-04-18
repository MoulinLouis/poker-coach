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
  const committed = state.committed[id];
  const isToAct = state.to_act === id;
  const isButton = state.button === id;
  const hole = id === "hero" ? state.hero_hole : state.villain_hole;

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
        {isButton && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/80 text-amber-950 font-bold">
            BTN
          </span>
        )}
        <span className="text-xs opacity-70 tabular-nums">
          {(stack / state.bb).toFixed(1)} bb
        </span>
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
      <div className="h-4 text-xs text-amber-300 tabular-nums">
        {committed > 0 ? `bet ${(committed / state.bb).toFixed(1)} bb` : ""}
      </div>
    </div>
  );
}
