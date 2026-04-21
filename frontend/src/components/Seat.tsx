import type { GameState, Seat as SeatId } from "../api/types";
import { PlayingCard } from "./PlayingCard";

function DealerButton() {
  return (
    <span
      aria-label="dealer button"
      className="inline-flex items-center justify-center w-6 h-6 rounded-full shrink-0 select-none"
      style={{
        background:
          "radial-gradient(circle at 35% 30%, #f8f1dc 0%, #ede3cc 55%, #c9b388 100%)",
        boxShadow:
          "0 2px 4px rgba(0,0,0,0.6), inset 0 0 0 1px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.7)",
      }}
    >
      <span
        className="font-bold text-[10px] leading-none"
        style={{
          color: "var(--color-ink)",
          letterSpacing: "0.02em",
        }}
      >
        D
      </span>
    </span>
  );
}

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
      className={`relative flex flex-col items-center gap-3 rounded-2xl px-5 py-4 transition-all ${
        isToAct ? "anim-halo" : ""
      }`}
      style={{
        background:
          "linear-gradient(180deg, rgba(10,7,6,0.7), rgba(10,7,6,0.45))",
        border: isToAct
          ? "1px solid rgba(201,162,94,0.8)"
          : "1px solid rgba(201,162,94,0.15)",
        boxShadow: isToAct
          ? undefined
          : "inset 0 1px 0 rgba(255,255,255,0.03), 0 8px 18px -10px rgba(0,0,0,0.8)",
        backdropFilter: "blur(6px)",
      }}
    >
      <div
        data-testid={`seat-${id}-position`}
        data-position={isButton ? "BTN" : "BB"}
        className="flex items-center gap-2.5 text-[color:var(--color-bone)]"
      >
        {isButton && <DealerButton />}
        <span className="text-[15px] font-semibold tracking-tight">{label}</span>
        <span className="font-mono text-[11px] tabular-nums text-[color:var(--color-gold-pale)]">
          {stackBb.toFixed(1)}
          <span className="opacity-60 ml-0.5">bb</span>
        </span>
      </div>

      <div className="flex gap-1.5">
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

      {/* Stack depth — thin gold meter with ticks */}
      <div className="w-full flex flex-col gap-0.5">
        <div
          data-testid={`seat-${id}-depth`}
          className="relative h-[3px] w-full rounded-full overflow-hidden"
          style={{
            background: "rgba(255,255,255,0.06)",
            boxShadow: "inset 0 1px 0 rgba(0,0,0,0.4)",
          }}
        >
          <div
            className="h-full transition-[width] duration-500"
            style={{
              width: `${depthPct}%`,
              background:
                "linear-gradient(90deg, var(--color-gold-deep), var(--color-gold-bright))",
              boxShadow: "0 0 6px rgba(240,211,138,0.5)",
            }}
          />
          {/* tick marks at 25/50/75 */}
          {[25, 50, 75].map((t) => (
            <span
              key={t}
              className="absolute top-0 w-px h-full bg-black/40"
              style={{ left: `${t}%` }}
            />
          ))}
        </div>
        <div className="flex items-center justify-between text-[8px] uppercase font-mono tracking-[0.25em] text-[color:var(--color-parchment-dim)]">
          <span>depth</span>
          <span className="tabular-nums">{depthPct.toFixed(0)}%</span>
        </div>
      </div>
    </div>
  );
}
