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
} from "../api/types";
import { useAdviceStream, type StreamState } from "../api/useAdviceStream";

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
  const [session, setSession] = useState<string | null>(null);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [snapshot, setSnapshot] = useState<EngineSnapshot | null>(null);
  const [heroHole, setHeroHole] = useState<string>("AsKd");
  const [villainHole, setVillainHole] = useState<string>("QcQh");
  const [effectiveStack, setEffectiveStack] = useState<number>(10000);
  const [button, setButton] = useState<Seat>("hero");
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
    const { session_id } = await createSession("spot");
    setSession(session_id);
    return session_id;
  }, [session]);

  const start = useCallback(async () => {
    setError(null);
    columns.forEach((c) => c.reset());
    const hero = heroHole.length === 4 ? ([heroHole.slice(0, 2), heroHole.slice(2, 4)] as [string, string]) : null;
    const villain =
      villainHole.length === 4
        ? ([villainHole.slice(0, 2), villainHole.slice(2, 4)] as [string, string])
        : null;
    if (!hero || !villain) {
      setError("hole cards must be 4 chars, e.g. AsKd");
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
      setError("Compare runs on hero's turn");
      return;
    }
    if (selected.length === 0) {
      setError("Select at least one model");
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
            prompt_version: "v1",
            game_state: snapshot.state,
          }),
        ),
      );
      decisions.forEach((d, i) => columns[i].start(d.decision_id));
    } catch (err) {
      setError(String(err));
    }
  }, [columns, initSession, selected.length, snapshot]);

  const toggleSelected = (id: string) => {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((x) => x !== id);
      if (current.length >= 3) return current;
      return [...current, id];
    });
  };

  return (
    <div style={{ maxWidth: 1200 }}>
      <h1 style={{ margin: "0 0 12px" }}>Spot Analysis</h1>

      <section style={{ padding: 12, border: "1px solid #ddd" }}>
        <strong>Spot</strong>
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <label>
            Hero hole <input value={heroHole} onChange={(e) => setHeroHole(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            Villain hole <input value={villainHole} onChange={(e) => setVillainHole(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            Effective stack{" "}
            <input
              type="number"
              value={effectiveStack}
              onChange={(e) => setEffectiveStack(parseInt(e.target.value || "0", 10))}
              style={{ width: 100 }}
            />
          </label>
          <label>
            Button{" "}
            <select value={button} onChange={(e) => setButton(e.target.value as Seat)}>
              <option value="hero">hero</option>
              <option value="villain">villain</option>
            </select>
          </label>
          <button onClick={start} data-testid="spot-start">Start</button>
        </div>
      </section>

      <section style={{ marginTop: 12, padding: 12, border: "1px solid #ddd" }}>
        <strong>Models to compare (up to 3)</strong>
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {presets.map((p) => {
            const on = selected.includes(p.selector_id);
            return (
              <button
                key={p.selector_id}
                onClick={() => toggleSelected(p.selector_id)}
                style={{
                  padding: "4px 8px",
                  background: on ? "#333" : "#fff",
                  color: on ? "#fff" : "#333",
                  border: "1px solid #888",
                  cursor: "pointer",
                }}
              >
                {p.selector_id}
              </button>
            );
          })}
        </div>
      </section>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {snapshot && (
        <section
          data-testid="spot-state"
          style={{ marginTop: 12, padding: 12, border: "1px solid #ddd", lineHeight: 1.4 }}
        >
          <div>
            <strong>Street:</strong> {snapshot.state.street} · <strong>To act:</strong>{" "}
            {snapshot.state.to_act ?? "(none)"} · <strong>Pot:</strong>{" "}
            {bb(snapshot.state, snapshot.state.pot)}bb
          </div>
          <div>
            <strong>Hero:</strong> {snapshot.state.hero_hole.join(" ")} · stack{" "}
            {bb(snapshot.state, snapshot.state.stacks.hero)}bb
          </div>
          <div>
            <strong>Villain:</strong> stack {bb(snapshot.state, snapshot.state.stacks.villain)}bb
          </div>
          <div>
            <strong>Board:</strong>{" "}
            {snapshot.state.board.length ? snapshot.state.board.join(" ") : "(none)"}
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
              style={{ marginTop: 8 }}
              disabled={columns.some(
                (c) => c.stream.status === "streaming" || c.stream.status === "thinking",
              )}
            >
              Compare ({selected.length})
            </button>
          )}
        </section>
      )}

      {columns.some((c) => c.stream.status !== "idle") && (
        <section
          data-testid="spot-columns"
          style={{
            marginTop: 12,
            display: "grid",
            gridTemplateColumns: `repeat(${columns.length}, minmax(0, 1fr))`,
            gap: 8,
          }}
        >
          {columns.map((c) => (
            <div key={c.presetId} style={{ padding: 12, border: "1px solid #ddd" }}>
              <strong>{c.presetId}</strong>
              {c.stream.status === "thinking" && <p><em>Thinking…</em></p>}
              {c.stream.reasoning && (
                <pre style={{ whiteSpace: "pre-wrap", fontSize: 13, color: "#444" }}>
                  {c.stream.reasoning}
                </pre>
              )}
              {c.stream.advice && (
                <div style={{ marginTop: 8, padding: 8, background: "#f6f6f6" }}>
                  <div>
                    <strong>{c.stream.advice.action}</strong>
                    {c.stream.advice.to_amount_bb != null
                      ? ` ${c.stream.advice.to_amount_bb}bb`
                      : ""}{" "}
                    · conf {c.stream.advice.confidence}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    {c.stream.advice.reasoning}
                  </div>
                </div>
              )}
              {c.stream.costUsd != null && (
                <div style={{ fontSize: 11, color: "#666", marginTop: 4 }}>
                  ${c.stream.costUsd.toFixed(4)}
                </div>
              )}
              {c.stream.errorMessage && (
                <div style={{ color: "crimson", fontSize: 12 }}>
                  {c.stream.errorMessage}
                </div>
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
  return (
    <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
      {legal.map((la) => {
        const needsSize = la.type === "bet" || la.type === "raise";
        const value = form[la.type] ?? "";
        return (
          <span key={la.type} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            {needsSize && (
              <input
                placeholder={`${la.min_to != null ? (la.min_to / bbValue).toFixed(1) : ""}–${
                  la.max_to != null ? (la.max_to / bbValue).toFixed(1) : ""
                } bb`}
                value={value}
                onChange={(e) => setForm({ ...form, [la.type]: e.target.value })}
                style={{ width: 80 }}
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
            >
              {actor} {la.type}
            </button>
          </span>
        );
      })}
    </div>
  );
}
