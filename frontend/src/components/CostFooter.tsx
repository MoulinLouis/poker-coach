import { useEffect, useState } from "react";
import { fetchCost } from "../api/client";
import type { CostResponse } from "../api/types";

const POLL_MS = 5000;

export function CostFooter({ sessionId }: { sessionId: string | null }) {
  const [cost, setCost] = useState<CostResponse | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await fetchCost(sessionId);
        if (!cancelled) setCost(data);
      } catch {
        /* swallow transient polling failures */
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [sessionId]);

  const decisionCount = cost?.by_model.reduce((s, r) => s + r.decision_count, 0) ?? 0;

  return (
    <footer
      data-testid="cost-footer"
      className="fixed bottom-0 left-0 right-0 z-10 backdrop-blur-xl text-[color:var(--color-bone)] text-xs"
      style={{
        background:
          "linear-gradient(180deg, rgba(10,7,6,0.5) 0%, rgba(10,7,6,0.95) 100%)",
        borderTop: "1px solid rgba(201,162,94,0.3)",
      }}
    >
      <div className="max-w-[1320px] mx-auto">
        <div className="px-3 sm:px-6 py-2 flex items-center gap-4">
          <button
            onClick={() => setExpanded((e) => !e)}
            className="flex items-center gap-2.5 sm:gap-4 hover:text-[color:var(--color-gold-bright)] transition group"
            data-testid="cost-footer-toggle"
          >
            <span
              className={`inline-block transition-transform text-[color:var(--color-gold)] ${expanded ? "rotate-180" : ""}`}
              aria-hidden
            >
              ▴
            </span>
            <Stat label="Session" value={`$${(cost?.session_usd ?? 0).toFixed(4)}`} accent />
            <span className="hidden sm:inline-flex items-center gap-4">
              <Divider />
              <Stat label="All-time" value={`$${(cost?.all_time_usd ?? 0).toFixed(4)}`} />
            </span>
            <Divider />
            <Stat
              label="Dec."
              value={decisionCount.toString()}
              mono
            />
            <span className="hidden sm:inline ml-2 text-[11px] text-[color:var(--color-parchment-dim)] group-hover:text-[color:var(--color-parchment)]">
              {expanded ? "hide ledger" : "view ledger"}
            </span>
          </button>

          {/* decorative ticker ornament */}
          <div className="ml-auto hidden md:flex items-center gap-2 font-mono text-[9px] tracking-[0.3em] uppercase text-[color:var(--color-gold-deep)]">
            <span className="w-1 h-1 rounded-full bg-[color:var(--color-jade)] animate-pulse" />
            Live · Polling
          </div>
        </div>

        {expanded && cost && cost.by_model.length > 0 && (
          <div
            className="px-6 pb-3 max-h-56 overflow-auto"
            style={{
              borderTop: "1px solid rgba(201,162,94,0.15)",
              background: "rgba(10,7,6,0.5)",
            }}
          >
            <table className="w-full text-xs tabular-nums font-mono mt-2">
              <thead className="text-[color:var(--color-parchment-dim)] uppercase tracking-[0.25em] text-[9px]">
                <tr>
                  <th className="text-left py-1.5 pr-4 font-normal">Model</th>
                  <th className="text-left py-1.5 pr-4 font-normal">Effort</th>
                  <th className="text-right py-1.5 pr-4 font-normal">Decisions</th>
                  <th className="text-right py-1.5 font-normal">Cost</th>
                </tr>
              </thead>
              <tbody>
                {cost.by_model.map((row) => (
                  <tr
                    key={`${row.model_id}/${row.reasoning_effort}`}
                    className="border-t border-[color:var(--color-gold-deep)]/20"
                  >
                    <td className="py-1.5 pr-4">{row.model_id}</td>
                    <td className="py-1.5 pr-4 text-[color:var(--color-parchment)]">
                      {row.reasoning_effort}
                    </td>
                    <td className="py-1.5 pr-4 text-right">{row.decision_count}</td>
                    <td className="py-1.5 text-right font-semibold text-[color:var(--color-gold-pale)]">
                      ${row.cost_usd.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </footer>
  );
}

function Stat({
  label,
  value,
  accent = false,
  mono = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
  mono?: boolean;
}) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
        {label}
      </span>
      <span
        className={`tabular-nums font-semibold ${mono ? "font-mono" : ""}`}
        style={{
          color: accent ? "var(--color-gold-bright)" : "var(--color-bone)",
        }}
      >
        {value}
      </span>
    </span>
  );
}

function Divider() {
  return (
    <span className="inline-block w-1 h-1 rotate-45 bg-[color:var(--color-gold-deep)]" />
  );
}
