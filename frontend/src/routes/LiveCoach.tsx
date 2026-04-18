import { useCallback, useEffect, useState } from "react";
import {
  createDecision,
  createHand,
  createSession,
  engineApply,
  engineStart,
  listPresets,
  recordAction,
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
import { useAdviceStream } from "../api/useAdviceStream";

interface SessionState {
  sessionId: string;
  handId: string | null;
}

type ActionFormState = Record<string, string>;

function formatCard(card: string): string {
  return card;
}

function bb(state: GameState, chips: number): string {
  return (chips / state.bb).toFixed(1);
}

export function LiveCoach() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [presetId, setPresetId] = useState<string>("");
  const [snapshot, setSnapshot] = useState<EngineSnapshot | null>(null);
  const [heroHole, setHeroHole] = useState<string>("AsKd");
  const [villainHole, setVillainHole] = useState<string>("QcQh");
  const [effectiveStack, setEffectiveStack] = useState<number>(10000);
  const [button, setButton] = useState<Seat>("hero");
  const [decisionId, setDecisionId] = useState<string | null>(null);
  const [actionForm, setActionForm] = useState<ActionFormState>({});
  const [error, setError] = useState<string | null>(null);
  const [agreement, setAgreement] = useState<{ total: number; diverged: number }>({
    total: 0,
    diverged: 0,
  });
  const { state: streamState, start: startStream, reset: resetStream } = useAdviceStream();

  useEffect(() => {
    listPresets()
      .then((resp) => {
        setPresets(resp.presets);
        setPresetId(resp.default);
      })
      .catch((err: unknown) => setError(String(err)));
  }, []);

  const startSessionIfNeeded = useCallback(async (): Promise<SessionState> => {
    if (session) return session;
    const { session_id } = await createSession("live");
    const next: SessionState = { sessionId: session_id, handId: null };
    setSession(next);
    return next;
  }, [session]);

  const parseHole = (raw: string): [string, string] | null => {
    if (raw.length !== 4) return null;
    return [raw.slice(0, 2), raw.slice(2, 4)];
  };

  const newHand = useCallback(async () => {
    setError(null);
    resetStream();
    setDecisionId(null);
    const hero = parseHole(heroHole);
    const villain = parseHole(villainHole);
    if (!hero || !villain) {
      setError("hole cards must be 4 chars, e.g. AsKd");
      return;
    }
    try {
      const s = await startSessionIfNeeded();
      const hand = await createHand({
        session_id: s.sessionId,
        bb: 100,
        effective_stack_start: effectiveStack,
      });
      const snap = await engineStart({
        effective_stack: effectiveStack,
        bb: 100,
        button,
        hero_hole: hero,
        villain_hole: villain,
      });
      setSession({ ...s, handId: hand.hand_id });
      setSnapshot(snap);
      setAgreement({ total: 0, diverged: 0 });
    } catch (err) {
      setError(String(err));
    }
  }, [button, effectiveStack, heroHole, resetStream, startSessionIfNeeded, villainHole]);

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

  const requestAdvice = useCallback(async () => {
    if (!snapshot || !session || !presetId) return;
    if (snapshot.state.to_act !== "hero") {
      setError("advice is only requested on hero's turn");
      return;
    }
    setError(null);
    resetStream();
    try {
      const { decision_id } = await createDecision({
        session_id: session.sessionId,
        hand_id: session.handId,
        model_preset: presetId,
        prompt_name: "coach",
        prompt_version: "v1",
        game_state: snapshot.state,
      });
      setDecisionId(decision_id);
      startStream(decision_id);
    } catch (err) {
      setError(String(err));
    }
  }, [presetId, resetStream, session, snapshot, startStream]);

  const heroAction = useCallback(
    async (type: ActionType, toAmount?: number | null) => {
      if (!snapshot) return;
      const action: Action = { actor: "hero", type, to_amount: toAmount ?? null };
      // Override detection: if advice exists and we're hero, record divergence
      if (decisionId && streamState.advice) {
        const divergent =
          streamState.advice.action !== type ||
          (streamState.advice.to_amount_bb != null &&
            toAmount != null &&
            Math.abs(streamState.advice.to_amount_bb - toAmount / snapshot.state.bb) > 0.01);
        await recordAction({ decision_id: decisionId, action }).catch(() => undefined);
        setAgreement((a) => ({
          total: a.total + 1,
          diverged: a.diverged + (divergent ? 1 : 0),
        }));
      }
      await applyAction(action);
      setDecisionId(null);
      resetStream();
    },
    [applyAction, decisionId, resetStream, snapshot, streamState.advice],
  );

  const villainAction = useCallback(
    async (type: ActionType, toAmount?: number | null) => {
      if (!snapshot) return;
      await applyAction({ actor: "villain", type, to_amount: toAmount ?? null });
    },
    [applyAction, snapshot],
  );

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 16, maxWidth: 960 }}>
      <header style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
        <h1 style={{ margin: 0 }}>Live Coach</h1>
        {session && (
          <span style={{ color: "#888", fontSize: 12 }}>session {session.sessionId.slice(0, 8)}</span>
        )}
        {agreement.total > 0 && (
          <span data-testid="agreement-rate" style={{ color: "#444", fontSize: 13 }}>
            agreement {Math.round(((agreement.total - agreement.diverged) / agreement.total) * 100)}%
            ({agreement.total - agreement.diverged}/{agreement.total})
          </span>
        )}
      </header>

      <section style={{ marginTop: 12, padding: 12, border: "1px solid #ddd" }}>
        <strong>Start a new hand</strong>
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          <label>
            Hero hole <input value={heroHole} onChange={(e) => setHeroHole(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            Villain hole <input value={villainHole} onChange={(e) => setVillainHole(e.target.value)} style={{ width: 70 }} />
          </label>
          <label>
            Effective stack (chips){" "}
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
          <label>
            Model{" "}
            <select value={presetId} onChange={(e) => setPresetId(e.target.value)}>
              {presets.map((p) => (
                <option key={p.selector_id} value={p.selector_id}>
                  {p.selector_id}
                </option>
              ))}
            </select>
          </label>
          <button onClick={newHand} data-testid="new-hand">New hand</button>
        </div>
      </section>

      {error && <p style={{ color: "crimson" }}>{error}</p>}

      {snapshot && <GameStateView snapshot={snapshot} />}

      {snapshot && snapshot.state.to_act === "hero" && (
        <section style={{ marginTop: 12, padding: 12, border: "1px solid #ddd" }}>
          <strong>Your turn</strong>
          <ActionButtons
            legal={snapshot.legal_actions}
            actionForm={actionForm}
            setActionForm={setActionForm}
            bb={snapshot.state.bb}
            onAction={heroAction}
          />
          <button
            data-testid="request-advice"
            onClick={requestAdvice}
            disabled={streamState.status === "thinking" || streamState.status === "streaming"}
            style={{ marginTop: 8 }}
          >
            Get advice
          </button>
        </section>
      )}

      {snapshot && snapshot.state.to_act === "villain" && (
        <section style={{ marginTop: 12, padding: 12, border: "1px solid #ddd" }}>
          <strong>Villain to act — what did villain do?</strong>
          <ActionButtons
            legal={snapshot.legal_actions}
            actionForm={actionForm}
            setActionForm={setActionForm}
            bb={snapshot.state.bb}
            onAction={villainAction}
          />
        </section>
      )}

      {streamState.status !== "idle" && (
        <section
          data-testid="advice-panel"
          style={{ marginTop: 12, padding: 12, border: "1px solid #ddd", minHeight: 80 }}
        >
          {streamState.status === "thinking" && <em>Thinking…</em>}
          {streamState.reasoning && (
            <pre
              data-testid="advice-reasoning"
              style={{ whiteSpace: "pre-wrap", margin: 0, color: "#444" }}
            >
              {streamState.reasoning}
            </pre>
          )}
          {streamState.advice && (
            <div data-testid="advice-card" style={{ marginTop: 8, padding: 8, background: "#f6f6f6" }}>
              <div>
                <strong>Advice:</strong> {streamState.advice.action}
                {streamState.advice.to_amount_bb != null
                  ? ` to ${streamState.advice.to_amount_bb} bb`
                  : ""}{" "}
                (confidence: {streamState.advice.confidence})
              </div>
              <div style={{ fontSize: 13, color: "#333", marginTop: 4 }}>
                {streamState.advice.reasoning}
              </div>
            </div>
          )}
          {streamState.costUsd != null && (
            <div data-testid="advice-cost" style={{ fontSize: 12, color: "#666", marginTop: 4 }}>
              cost: ${streamState.costUsd.toFixed(4)}
            </div>
          )}
          {streamState.errorMessage && (
            <div style={{ color: "crimson", marginTop: 4 }}>error: {streamState.errorMessage}</div>
          )}
        </section>
      )}
    </main>
  );

  function GameStateView({ snapshot: s }: { snapshot: EngineSnapshot }) {
    const state = s.state;
    return (
      <section
        data-testid="game-state"
        style={{ marginTop: 12, padding: 12, border: "1px solid #ddd", lineHeight: 1.4 }}
      >
        <div>
          <strong>Street:</strong> {state.street} · <strong>Button:</strong> {state.button} ·{" "}
          <strong>Pot:</strong> {bb(state, state.pot)} bb · <strong>To act:</strong>{" "}
          {state.to_act ?? "(none)"}
        </div>
        <div>
          <strong>Hero:</strong> {state.hero_hole.map(formatCard).join(" ")} · stack {bb(state, state.stacks.hero)}bb
          · committed {bb(state, state.committed.hero)}bb
        </div>
        <div>
          <strong>Villain:</strong> stack {bb(state, state.stacks.villain)}bb · committed{" "}
          {bb(state, state.committed.villain)}bb
          {state.villain_hole && state.street === "showdown"
            ? ` · ${state.villain_hole.join(" ")}`
            : ""}
        </div>
        <div>
          <strong>Board:</strong> {state.board.length ? state.board.join(" ") : "(none)"}
        </div>
        {state.history.length > 0 && (
          <div style={{ marginTop: 4 }}>
            <strong>History:</strong>{" "}
            {state.history
              .map((a) =>
                a.to_amount != null
                  ? `${a.actor} ${a.type} to ${bb(state, a.to_amount)}bb`
                  : `${a.actor} ${a.type}`,
              )
              .join(" · ")}
          </div>
        )}
      </section>
    );
  }
}

function ActionButtons({
  legal,
  actionForm,
  setActionForm,
  bb: bbValue,
  onAction,
}: {
  legal: LegalAction[];
  actionForm: ActionFormState;
  setActionForm: (v: ActionFormState) => void;
  bb: number;
  onAction: (type: ActionType, toAmount?: number | null) => void | Promise<void>;
}) {
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
      {legal.map((la) => {
        const needsSize = la.type === "bet" || la.type === "raise";
        const input = actionForm[la.type] ?? "";
        return (
          <span key={la.type} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            {needsSize && (
              <input
                placeholder={`${la.min_to != null ? (la.min_to / bbValue).toFixed(1) : ""}–${
                  la.max_to != null ? (la.max_to / bbValue).toFixed(1) : ""
                } bb`}
                value={input}
                onChange={(e) => setActionForm({ ...actionForm, [la.type]: e.target.value })}
                style={{ width: 100 }}
                data-testid={`size-${la.type}`}
              />
            )}
            <button
              data-testid={`action-${la.type}`}
              onClick={() => {
                if (needsSize) {
                  const bbAmount = parseFloat(input || "0");
                  if (!Number.isFinite(bbAmount) || bbAmount <= 0) return;
                  onAction(la.type, Math.round(bbAmount * bbValue));
                } else if (la.type === "allin") {
                  onAction(la.type, la.max_to);
                } else {
                  onAction(la.type);
                }
              }}
            >
              {la.type}
            </button>
          </span>
        );
      })}
    </div>
  );
}
