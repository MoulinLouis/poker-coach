import type { Advice } from "../api/types";
import type { StreamState } from "../api/useAdviceStream";

export function AdvicePanel({
  stream,
  diverged,
  presetLabel,
}: {
  stream: StreamState;
  diverged: boolean;
  presetLabel: string;
}) {
  return (
    <aside
      data-testid="advice-panel"
      className="w-[380px] shrink-0 flex flex-col gap-3 rounded-xl bg-stone-900 p-4 text-stone-100 shadow-xl ring-1 ring-white/5"
    >
      <header className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-sm font-semibold">Coach</span>
          <span className="text-[11px] opacity-60">{presetLabel}</span>
        </div>
        {diverged && (
          <span
            data-testid="diverged-badge"
            className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 text-[10px] tracking-wider uppercase border border-amber-500/40"
          >
            diverged
          </span>
        )}
      </header>

      {stream.status === "idle" && (
        <p className="text-sm opacity-60">
          Click <span className="font-semibold text-amber-300">advise</span> on hero's turn
          to ask the coach.
        </p>
      )}

      {stream.status === "thinking" && (
        <div className="flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          <span className="opacity-80">Thinking…</span>
        </div>
      )}

      {stream.reasoning && (
        <pre
          data-testid="advice-reasoning"
          className="max-h-[300px] overflow-auto text-[11px] leading-relaxed font-mono whitespace-pre-wrap text-stone-300 bg-black/40 rounded p-2 ring-1 ring-white/5"
        >
          {stream.reasoning}
        </pre>
      )}

      {stream.advice && <AdviceCard advice={stream.advice} />}

      {stream.costUsd != null && (
        <div className="text-[10px] text-stone-500 tabular-nums">
          cost: ${stream.costUsd.toFixed(4)}
        </div>
      )}

      {stream.errorMessage && (
        <div
          data-testid="advice-error"
          className="text-sm text-red-300 bg-red-900/30 rounded p-2 ring-1 ring-red-500/30"
        >
          {stream.errorMessage}
        </div>
      )}
    </aside>
  );
}

function AdviceCard({ advice }: { advice: Advice }) {
  const confidenceStyle = {
    high: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
    medium: "bg-amber-500/20 text-amber-300 border-amber-500/40",
    low: "bg-stone-500/20 text-stone-300 border-stone-500/40",
  }[advice.confidence];

  return (
    <div
      data-testid="advice-card"
      className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 anim-fade-up"
    >
      <div className="flex items-center justify-between mb-2 gap-2">
        <span className="text-lg font-bold capitalize">
          {advice.action}
          {advice.to_amount_bb != null && (
            <span className="ml-2 text-amber-200 tabular-nums">
              to {advice.to_amount_bb} bb
            </span>
          )}
        </span>
        <span
          className={`px-2 py-0.5 rounded text-[10px] border uppercase tracking-wider ${confidenceStyle}`}
        >
          {advice.confidence}
        </span>
      </div>
      <p className="text-sm opacity-90 leading-relaxed">{advice.reasoning}</p>
    </div>
  );
}
