import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createDecision,
  createSession,
  engineApply,
  engineStart,
  listPresets,
} from "../api/client";
import type {
  Action,
  ActionType,
  EngineSnapshot,
  GameState,
  LegalAction,
  PresetSummary,
  Seat,
  VillainProfile,
} from "../api/types";
import { useAdviceStream, type StreamState } from "../api/useAdviceStream";
import { formatUsd, useLocale } from "../i18n";
import { parseHole } from "../utils/cards";

interface ColumnState {
  presetId: string;
  stream: StreamState;
  start: (id: string) => void;
  cancel: () => void;
  reset: () => void;
  decisionId: string | null;
}

function useColumn(presetId: string): ColumnState {
  const { state, start, cancel, reset } = useAdviceStream();
  const [decisionId, setDecisionId] = useState<string | null>(null);
  return useMemo(
    () => ({
      presetId,
      stream: state,
      start: (id: string) => {
        setDecisionId(id);
        start(id);
      },
      cancel,
      reset: () => {
        setDecisionId(null);
        reset();
      },
      decisionId,
    }),
    [cancel, decisionId, presetId, reset, start, state],
  );
}

function bb(state: GameState, chips: number): string {
  return (chips / state.bb).toFixed(1);
}

export function SpotAnalysis() {
  const { t, lang } = useLocale();
  const [session, setSession] = useState<string | null>(null);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [snapshot, setSnapshot] = useState<EngineSnapshot | null>(null);
  const [heroHole, setHeroHole] = useState<string>("AsKd");
  const [villainHole, setVillainHole] = useState<string>("QcQh");
  const [effectiveStack, setEffectiveStack] = useState<number>(10000);
  const [button, setButton] = useState<Seat>("hero");
  const [villainProfile, setVillainProfile] = useState<VillainProfile>("unknown");
  const [actionForm, setActionForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  // We support up to 3 comparison columns; the hook layout is fixed so the
  // column hooks are stable across renders.
  const col1 = useColumn(selected[0] ?? "");
  const col2 = useColumn(selected[1] ?? "");
  const col3 = useColumn(selected[2] ?? "");
  const columns = [col1, col2, col3].slice(0, selected.length);

  useEffect(() => {
    listPresets()
      .then((resp) => {
        setPresets(resp.presets);
        setSelected([resp.default]);
      })
      .catch((err: unknown) => setError(String(err)));
  }, []);

  const initSession = useCallback(async (): Promise<string> => {
    if (session) return session;
    const { session_id } = await createSession({ mode: "spot" });
    setSession(session_id);
    return session_id;
  }, [session]);

  const start = useCallback(async () => {
    setError(null);
    columns.forEach((c) => c.reset());
    const hero = parseHole(heroHole);
    const villain = parseHole(villainHole);
    if (!hero || !villain) {
      setError(t("routes.spotAnalysis.errorHoleCards"));
      return;
    }
    try {
      const snap = await engineStart({
        effective_stack: effectiveStack,
        bb: 100,
        button,
        hero_hole: hero,
        villain_hole: villain,
      });
      setSnapshot(snap);
    } catch (err) {
      setError(String(err));
    }
  }, [button, columns, effectiveStack, heroHole, villainHole]);

  const applyAction = useCallback(
    async (action: Action) => {
      if (!snapshot) return;
      try {
        const next = await engineApply(snapshot.state, action);
        setSnapshot(next);
        setActionForm({});
      } catch (err) {
        setError(String(err));
      }
    },
    [snapshot],
  );

  const compare = useCallback(async () => {
    if (!snapshot || snapshot.state.to_act !== "hero") {
      setError(t("routes.spotAnalysis.errorCompareOnHeroTurn"));
      return;
    }
    if (selected.length === 0) {
      setError(t("routes.spotAnalysis.errorSelectModel"));
      return;
    }
    setError(null);
    try {
      const sessionId = await initSession();
      // Reset and fire in parallel
      columns.forEach((c) => c.reset());
      const decisions = await Promise.all(
        columns.map((c) =>
          createDecision({
            session_id: sessionId,
            model_preset: c.presetId,
            prompt_name: "coach",
            prompt_version: "v2",
            game_state: snapshot.state,
            villain_profile: villainProfile,
          }),
        ),
      );
      decisions.forEach((d, i) => columns[i].start(d.decision_id));
    } catch (err) {
      setError(String(err));
    }
  }, [columns, initSession, selected.length, snapshot, villainProfile]);

  const toggleSelected = (id: string) => {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((x) => x !== id);
      if (current.length >= 3) return current;
      return [...current, id];
    });
  };

  return (
    <div className="max-w-[1200px]">
      <h1 className="mb-3 text-2xl font-semibold text-stone-100">{t("routes.spotAnalysis.title")}</h1>

      <section className="p-3 rounded-lg ring-1 ring-white/5 bg-stone-900">
        <strong className="text-sm font-semibold text-stone-200">{t("routes.spotAnalysis.spotHeader")}</strong>
        <div className="flex gap-2 mt-2 flex-wrap items-center">
          <label className="flex items-center gap-1 text-sm text-stone-300">
            {t("routes.spotAnalysis.heroHoleLabel")}{" "}
            <input
              value={heroHole}
              onChange={(e) => setHeroHole(e.target.value)}
              className="w-[70px] bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-sm"
            />
          </label>
          <label className="flex items-center gap-1 text-sm text-stone-300">
            {t("routes.spotAnalysis.villainHoleLabel")}{" "}
            <input
              value={villainHole}
              onChange={(e) => setVillainHole(e.target.value)}
              className="w-[70px] bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-sm"
            />
          </label>
          <label className="flex items-center gap-1 text-sm text-stone-300">
            {t("routes.spotAnalysis.effectiveStackLabel")}{" "}
            <input
              type="number"
              value={effectiveStack}
              onChange={(e) => setEffectiveStack(parseInt(e.target.value || "0", 10))}
              className="w-[100px] bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-sm"
            />
          </label>
          <label className="flex items-center gap-1 text-sm text-stone-300">
            {t("routes.spotAnalysis.buttonLabel")}{" "}
            <select
              value={button}
              onChange={(e) => setButton(e.target.value as Seat)}
              className="bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-sm"
            >
              <option value="hero">{t("routes.spotAnalysis.optionHero")}</option>
              <option value="villain">{t("routes.spotAnalysis.optionVillain")}</option>
            </select>
          </label>
          <label className="flex items-center gap-1 text-sm text-stone-300">
            {t("routes.spotAnalysis.villainProfileLabel")}{" "}
            <select
              value={villainProfile}
              onChange={(e) => setVillainProfile(e.target.value as VillainProfile)}
              className="bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-sm"
            >
              <option value="unknown">{t("routes.spotAnalysis.optionUnknown")}</option>
              <option value="reg">{t("routes.spotAnalysis.optionReg")}</option>
            </select>
          </label>
          <button
            onClick={start}
            data-testid="spot-start"
            className="px-3 py-1 rounded bg-amber-500 text-stone-950 font-semibold text-sm hover:bg-amber-400 transition"
          >
            {t("routes.spotAnalysis.start")}
          </button>
        </div>
      </section>

      <section className="mt-3 p-3 rounded-lg ring-1 ring-white/5 bg-stone-900">
        <strong className="text-sm font-semibold text-stone-200">{t("routes.spotAnalysis.modelsHeader")}</strong>
        <div className="mt-2 flex gap-2 flex-wrap">
          {presets.map((p) => {
            const on = selected.includes(p.selector_id);
            return (
              <button
                key={p.selector_id}
                onClick={() => toggleSelected(p.selector_id)}
                className={`px-2 py-1 rounded text-xs ring-1 transition cursor-pointer ${
                  on
                    ? "bg-stone-700 text-stone-100 ring-stone-500"
                    : "bg-stone-800 text-stone-400 ring-white/10 hover:text-stone-200"
                }`}
              >
                {p.selector_id}
              </button>
            );
          })}
        </div>
      </section>

      {error && <p className="mt-2 text-red-400 text-sm">{error}</p>}

      {snapshot && (
        <section
          data-testid="spot-state"
          className="mt-3 p-3 rounded-lg ring-1 ring-white/5 bg-stone-900 leading-relaxed text-sm text-stone-300"
        >
          <div>
            <strong className="text-stone-200">{t("routes.spotAnalysis.streetLabel")}</strong> {snapshot.state.street} ·{" "}
            <strong className="text-stone-200">{t("routes.spotAnalysis.toActLabel")}</strong>{" "}
            {snapshot.state.to_act ?? t("routes.spotAnalysis.toActNone")} ·{" "}
            <strong className="text-stone-200">{t("routes.spotAnalysis.potLabel")}</strong>{" "}
            {bb(snapshot.state, snapshot.state.pot)}
            {t("routes.spotAnalysis.bbUnit")}
          </div>
          <div>
            <strong className="text-stone-200">{t("routes.spotAnalysis.heroLabel")}</strong>{" "}
            {snapshot.state.hero_hole.join(" ")} · {t("routes.spotAnalysis.stackWord")}{" "}
            {bb(snapshot.state, snapshot.state.stacks.hero)}
            {t("routes.spotAnalysis.bbUnit")}
          </div>
          <div>
            <strong className="text-stone-200">{t("routes.spotAnalysis.villainLabel")}</strong> {t("routes.spotAnalysis.stackWord")}{" "}
            {bb(snapshot.state, snapshot.state.stacks.villain)}
            {t("routes.spotAnalysis.bbUnit")}
          </div>
          <div>
            <strong className="text-stone-200">{t("routes.spotAnalysis.boardLabel")}</strong>{" "}
            {snapshot.state.board.length ? snapshot.state.board.join(" ") : t("routes.spotAnalysis.boardNone")}
          </div>
          {snapshot.state.to_act && (
            <ActionRow
              legal={snapshot.legal_actions}
              form={actionForm}
              setForm={setActionForm}
              bb={snapshot.state.bb}
              actor={snapshot.state.to_act}
              onAction={applyAction}
            />
          )}
          {snapshot.state.to_act === "hero" && (
            <button
              onClick={compare}
              data-testid="spot-compare"
              className="mt-2 px-3 py-1 rounded bg-amber-500 text-stone-950 font-semibold text-sm hover:bg-amber-400 transition disabled:opacity-40 disabled:cursor-not-allowed"
              disabled={columns.some(
                (c) => c.stream.status === "streaming" || c.stream.status === "thinking",
              )}
            >
              {t("routes.spotAnalysis.compare")} ({selected.length})
            </button>
          )}
        </section>
      )}

      {columns.some((c) => c.stream.status !== "idle") && (
        <section
          data-testid="spot-columns"
          className="mt-3 grid gap-2"
          style={{ gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))` }}
        >
          {columns.map((c) => (
            <div
              key={c.presetId}
              className="p-3 rounded-lg ring-1 ring-white/5 bg-stone-900"
            >
              <strong className="text-sm font-semibold text-stone-200">{c.presetId}</strong>
              {c.stream.status === "thinking" && (
                <p className="text-sm text-stone-400 italic mt-1">{t("routes.spotAnalysis.thinking")}</p>
              )}
              {c.stream.reasoning && (
                <pre className="whitespace-pre-wrap text-[13px] text-stone-500 mt-1 overflow-auto max-h-40">
                  {c.stream.reasoning}
                </pre>
              )}
              {c.stream.advice && (
                <div className="mt-2 p-2 bg-stone-800 rounded">
                  <div className="text-sm text-stone-200">
                    <strong>{c.stream.advice.action}</strong>
                    {c.stream.advice.to_amount_bb != null
                      ? ` ${c.stream.advice.to_amount_bb}${t("routes.spotAnalysis.bbUnit")}`
                      : ""}{" "}
                    · {t("routes.spotAnalysis.confShort")} {c.stream.advice.confidence}
                  </div>
                  <div className="text-xs text-stone-400 mt-1">
                    {c.stream.advice.reasoning}
                  </div>
                </div>
              )}
              {c.stream.costUsd != null && (
                <div className="text-[11px] text-stone-500 mt-1 tabular-nums">
                  {formatUsd(lang, c.stream.costUsd)}
                </div>
              )}
              {c.stream.errorMessage && (
                <div className="text-red-400 text-xs mt-1">{c.stream.errorMessage}</div>
              )}
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

function ActionRow({
  legal,
  form,
  setForm,
  bb: bbValue,
  actor,
  onAction,
}: {
  legal: LegalAction[];
  form: Record<string, string>;
  setForm: (v: Record<string, string>) => void;
  bb: number;
  actor: Seat;
  onAction: (action: Action) => void | Promise<void>;
}) {
  const { t } = useLocale();
  const actorLabel = actor === "hero" ? t("routes.spotAnalysis.optionHero") : t("routes.spotAnalysis.optionVillain");
  return (
    <div className="mt-2 flex gap-1.5 flex-wrap">
      {legal.map((la) => {
        const needsSize = la.type === "bet" || la.type === "raise";
        const value = form[la.type] ?? "";
        return (
          <span key={la.type} className="inline-flex items-center gap-1">
            {needsSize && (
              <input
                placeholder={`${la.min_to != null ? (la.min_to / bbValue).toFixed(1) : ""}–${
                  la.max_to != null ? (la.max_to / bbValue).toFixed(1) : ""
                } ${t("routes.spotAnalysis.sizePlaceholderUnit")}`}
                value={value}
                onChange={(e) => setForm({ ...form, [la.type]: e.target.value })}
                className="w-20 bg-stone-800 text-stone-100 rounded px-1.5 py-0.5 ring-1 ring-white/10 text-xs"
              />
            )}
            <button
              onClick={() => {
                let amt: number | null = null;
                if (needsSize) {
                  const parsed = Math.round(parseFloat(value || "0") * bbValue);
                  if (!Number.isFinite(parsed) || parsed <= 0) return;
                  amt = parsed;
                } else if (la.type === "allin") {
                  amt = la.max_to ?? null;
                }
                onAction({ actor, type: la.type as ActionType, to_amount: amt });
              }}
              className="px-2 py-0.5 rounded bg-stone-700 text-stone-200 text-xs ring-1 ring-white/10 hover:bg-stone-600 transition"
            >
              {actorLabel} {la.type}
            </button>
          </span>
        );
      })}
    </div>
  );
}
