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

  return (
    <footer
      data-testid="cost-footer"
      className="fixed bottom-0 left-0 right-0 border-t border-stone-800 bg-stone-950/95 backdrop-blur text-stone-200 text-xs"
    >
      <div className="px-4 py-1.5 flex items-center gap-4">
        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-2 hover:text-white transition"
          data-testid="cost-footer-toggle"
        >
          <span
            className={`inline-block transition-transform ${expanded ? "rotate-180" : ""}`}
            aria-hidden
          >
            ▴
          </span>
          <span className="opacity-70">session</span>
          <span className="tabular-nums font-semibold">
            ${(cost?.session_usd ?? 0).toFixed(4)}
          </span>
          <span className="opacity-40">·</span>
          <span className="opacity-70">all-time</span>
          <span className="tabular-nums font-semibold">
            ${(cost?.all_time_usd ?? 0).toFixed(4)}
          </span>
          {cost && (
            <span className="opacity-40 ml-2">
              ({cost.by_model.reduce((s, r) => s + r.decision_count, 0)} decisions)
            </span>
          )}
        </button>
      </div>
      {expanded && cost && cost.by_model.length > 0 && (
        <div className="px-4 pb-2 border-t border-stone-800/60 max-h-56 overflow-auto">
          <table className="w-full text-xs tabular-nums">
            <thead className="text-stone-500 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="text-left py-1 pr-4">Model</th>
                <th className="text-left py-1 pr-4">Effort</th>
                <th className="text-right py-1 pr-4">Decisions</th>
                <th className="text-right py-1">Cost</th>
              </tr>
            </thead>
            <tbody>
              {cost.by_model.map((row) => (
                <tr
                  key={`${row.model_id}/${row.reasoning_effort}`}
                  className="border-t border-stone-900"
                >
                  <td className="py-1 pr-4">{row.model_id}</td>
                  <td className="py-1 pr-4 opacity-70">{row.reasoning_effort}</td>
                  <td className="py-1 pr-4 text-right">{row.decision_count}</td>
                  <td className="py-1 text-right font-semibold">
                    ${row.cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </footer>
  );
}
