import { useCallback, useEffect, useState } from "react";
import { getDecisionDetail, listDecisions } from "../api/client";
import type { DecisionDetail, DecisionListRow } from "../api/types";
import { useLocale } from "../i18n";

export function History() {
  const { t } = useLocale();
  const [rows, setRows] = useState<DecisionListRow[]>([]);
  const [filters, setFilters] = useState<{
    model_id: string;
    status: string;
    prompt_version: string;
  }>({ model_id: "", status: "", prompt_version: "" });
  const [selected, setSelected] = useState<DecisionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDecisions({
        limit: 100,
        model_id: filters.model_id || null,
        status: filters.status || null,
        prompt_version: filters.prompt_version || null,
      });
      setRows(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    reload();
  }, [reload]);

  const openDetail = async (id: string) => {
    setError(null);
    try {
      const detail = await getDecisionDetail(id);
      setSelected(detail);
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="flex gap-4 max-w-[1400px] mx-auto">
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        <h1 className="text-xl font-semibold">{t("routes.history.title")}</h1>
        <div className="flex gap-2 items-center flex-wrap">
          <Filter
            label={t("routes.history.filterModel")}
            value={filters.model_id}
            onChange={(v) => setFilters((f) => ({ ...f, model_id: v }))}
            placeholder="claude-opus-4-7"
          />
          <Filter
            label={t("routes.history.filterStatus")}
            value={filters.status}
            onChange={(v) => setFilters((f) => ({ ...f, status: v }))}
            placeholder={t("routes.history.filterStatusPlaceholder")}
          />
          <Filter
            label={t("routes.history.filterPromptVersion")}
            value={filters.prompt_version}
            onChange={(v) => setFilters((f) => ({ ...f, prompt_version: v }))}
            placeholder="v1"
          />
          <button
            onClick={reload}
            className="ml-auto px-3 py-1.5 rounded-md bg-stone-800 hover:bg-stone-700 text-sm ring-1 ring-white/10"
          >
            {t("routes.history.refresh")}
          </button>
        </div>
        {error && (
          <div className="rounded bg-red-900/30 text-red-200 p-2 text-sm ring-1 ring-red-500/30">
            {error}
          </div>
        )}
        <div className="rounded-lg ring-1 ring-white/5 overflow-hidden">
          <table className="w-full text-xs tabular-nums">
            <thead className="bg-stone-900 text-stone-400 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="text-left px-3 py-2">{t("routes.history.columnWhen")}</th>
                <th className="text-left px-3 py-2">{t("routes.history.columnModel")}</th>
                <th className="text-left px-3 py-2">{t("routes.history.columnPrompt")}</th>
                <th className="text-left px-3 py-2">{t("routes.history.columnStatus")}</th>
                <th className="text-left px-3 py-2">{t("routes.history.columnAdvice")}</th>
                <th className="text-right px-3 py-2">{t("routes.history.columnCost")}</th>
                <th className="text-right px-3 py-2">{t("routes.history.columnLatency")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="p-4 text-center text-stone-500">
                    {t("routes.history.empty")}
                  </td>
                </tr>
              )}
              {rows.map((r) => (
                <tr
                  key={r.decision_id}
                  data-testid={`history-row-${r.decision_id}`}
                  onClick={() => openDetail(r.decision_id)}
                  className={`border-t border-stone-900 cursor-pointer transition ${
                    selected?.decision_id === r.decision_id
                      ? "bg-stone-800/70"
                      : "hover:bg-stone-900/60"
                  }`}
                >
                  <td className="px-3 py-1.5 text-stone-400">
                    {r.created_at.slice(0, 19).replace("T", " ")}
                  </td>
                  <td className="px-3 py-1.5">{r.model_id}</td>
                  <td className="px-3 py-1.5 opacity-70">
                    {r.prompt_name}/{r.prompt_version}
                  </td>
                  <td className="px-3 py-1.5">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-3 py-1.5">
                    {r.parsed_advice ? (
                      <>
                        <span className="capitalize">{r.parsed_advice.action}</span>
                        {r.parsed_advice.to_amount_bb != null && (
                          <span className="opacity-70"> {r.parsed_advice.to_amount_bb}bb</span>
                        )}
                      </>
                    ) : (
                      <span className="opacity-40">—</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-right opacity-80">
                    {r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right opacity-70">
                    {r.latency_ms != null ? `${r.latency_ms}ms` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <aside className="w-[460px] shrink-0 rounded-lg bg-stone-900 p-4 ring-1 ring-white/5 text-sm max-h-[80vh] overflow-auto">
          <header className="flex justify-between items-baseline mb-3">
            <div>
              <div className="text-[10px] uppercase tracking-widest opacity-60">{t("routes.history.detailDecision")}</div>
              <div className="font-mono text-xs">{selected.decision_id.slice(0, 16)}…</div>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-stone-500 hover:text-stone-200"
            >
              ×
            </button>
          </header>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs mb-3">
            <dt className="opacity-60">{t("routes.history.detailModel")}</dt>
            <dd>{selected.model_id}</dd>
            <dt className="opacity-60">{t("routes.history.detailEffort")}</dt>
            <dd>{selected.reasoning_effort ?? selected.thinking_budget ?? "—"}</dd>
            <dt className="opacity-60">{t("routes.history.detailPrompt")}</dt>
            <dd>
              {selected.prompt_name}/{selected.prompt_version}
            </dd>
            <dt className="opacity-60">{t("routes.history.detailStatus")}</dt>
            <dd>
              <StatusBadge status={selected.status} />
            </dd>
            <dt className="opacity-60">{t("routes.history.detailTokens")}</dt>
            <dd>
              {selected.input_tokens ?? "—"} / {selected.output_tokens ?? "—"} /{" "}
              {selected.reasoning_tokens ?? "—"}
            </dd>
            <dt className="opacity-60">{t("routes.history.detailCost")}</dt>
            <dd>
              {selected.cost_usd != null ? `$${selected.cost_usd.toFixed(4)}` : "—"}
            </dd>
            <dt className="opacity-60">{t("routes.history.detailLatency")}</dt>
            <dd>{selected.latency_ms != null ? `${selected.latency_ms}ms` : "—"}</dd>
          </dl>

          {selected.parsed_advice && (
            <Collapsible title={t("routes.history.sectionAdvice")} defaultOpen>
              <div className="rounded bg-amber-500/10 border border-amber-500/40 p-2">
                <div className="font-semibold capitalize">
                  {selected.parsed_advice.action}
                  {selected.parsed_advice.to_amount_bb != null && (
                    <span className="ml-1 text-amber-200">
                      {t("routes.history.toPrefix")} {selected.parsed_advice.to_amount_bb} {t("routes.history.bbUnit")}
                    </span>
                  )}{" "}
                  ({selected.parsed_advice.confidence})
                </div>
                <p className="mt-1 text-[11px] opacity-90">
                  {selected.parsed_advice.reasoning}
                </p>
              </div>
            </Collapsible>
          )}
          {selected.reasoning_text && (
            <Collapsible title={t("routes.history.sectionReasoning")}>
              <pre className="text-[11px] font-mono whitespace-pre-wrap bg-black/40 p-2 rounded max-h-56 overflow-auto">
                {selected.reasoning_text}
              </pre>
            </Collapsible>
          )}
          <Collapsible title={t("routes.history.sectionPrompt")}>
            <pre className="text-[11px] font-mono whitespace-pre-wrap bg-black/40 p-2 rounded max-h-56 overflow-auto">
              {selected.rendered_prompt}
            </pre>
          </Collapsible>
          <Collapsible title={t("routes.history.sectionGameState")}>
            <pre className="text-[11px] font-mono whitespace-pre-wrap bg-black/40 p-2 rounded max-h-56 overflow-auto">
              {JSON.stringify(selected.game_state, null, 2)}
            </pre>
          </Collapsible>
          {selected.error_message && (
            <Collapsible title={t("routes.history.sectionError")} defaultOpen>
              <pre className="text-[11px] font-mono whitespace-pre-wrap bg-red-900/30 text-red-200 p-2 rounded ring-1 ring-red-500/30">
                {selected.error_message}
              </pre>
            </Collapsible>
          )}
        </aside>
      )}
    </div>
  );
}

function Filter({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col text-[10px] uppercase tracking-wider opacity-70 gap-0.5">
      <span>{label}</span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="normal-case text-sm bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none w-52"
      />
    </label>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "ok"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
      : status === "in_flight"
        ? "bg-blue-500/20 text-blue-300 border-blue-500/40"
        : status === "cancelled" || status === "abandoned"
          ? "bg-stone-500/20 text-stone-300 border-stone-500/40"
          : "bg-red-500/20 text-red-300 border-red-500/40";
  return (
    <span className={`px-1.5 py-0.5 rounded text-[10px] border uppercase tracking-wider ${color}`}>
      {status}
    </span>
  );
}

function Collapsible({
  title,
  children,
  defaultOpen,
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(Boolean(defaultOpen));
  return (
    <div className="mb-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between py-1 text-[11px] uppercase tracking-wider opacity-70 hover:opacity-100"
      >
        <span>{title}</span>
        <span
          className={`transition-transform ${open ? "rotate-180" : ""}`}
          aria-hidden
        >
          ▾
        </span>
      </button>
      {open && <div className="mt-1">{children}</div>}
    </div>
  );
}
