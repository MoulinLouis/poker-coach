import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createDecision,
  createHand,
  createSession,
  engineApply,
  engineReveal,
  engineStart,
  listPresets,
  recordAction,
} from "../api/client";
import type { Action, EngineSnapshot, PresetSummary } from "../api/types";
import { useAdviceStream } from "../api/useAdviceStream";
import { ActionBar } from "../components/ActionBar";
import { AdvicePanel } from "../components/AdvicePanel";
import { BoardPicker } from "../components/BoardPicker";
import { HandSummary } from "../components/HandSummary";
import { PokerTable } from "../components/PokerTable";
import { SetupPanel, type SetupValues } from "../components/SetupPanel";
import { useHotkeys } from "../hooks/useHotkeys";

interface SessionState {
  sessionId: string;
  handId: string | null;
}

function parseHole(raw: string): [string, string] | null {
  if (raw.length !== 4) return null;
  return [raw.slice(0, 2), raw.slice(2, 4)];
}

function divergesFromAdvice(
  adviceAction: string,
  adviceToAmountBb: number | null | undefined,
  action: Action,
  bb: number,
): boolean {
  if (action.type !== adviceAction) return true;
  if (adviceToAmountBb == null || action.to_amount == null) return false;
  return Math.abs(adviceToAmountBb - action.to_amount / bb) > 0.01;
}

export function LiveCoach() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  const [setup, setSetup] = useState<SetupValues>({
    heroHole: "AsKd",
    villainHole: "QcQh",
    effectiveStack: 10_000,
    button: "hero",
    presetId: "",
  });
  const [snapshot, setSnapshot] = useState<EngineSnapshot | null>(null);
  const [decisionId, setDecisionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [agreement, setAgreement] = useState<{ total: number; diverged: number }>({
    total: 0,
    diverged: 0,
  });
  const [currentDiverged, setCurrentDiverged] = useState<boolean>(false);

  const { state: streamState, start: startStream, reset: resetStream } = useAdviceStream();

  useEffect(() => {
    listPresets()
      .then((resp) => {
        setPresets(resp.presets);
        setSetup((s) => ({ ...s, presetId: s.presetId || resp.default }));
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

  const newHand = useCallback(async () => {
    setError(null);
    resetStream();
    setDecisionId(null);
    setCurrentDiverged(false);
    const hero = parseHole(setup.heroHole);
    const villain = parseHole(setup.villainHole);
    if (!hero || !villain) {
      setError("hole cards must be 4 characters, e.g. AsKd");
      return;
    }
    try {
      const s = await startSessionIfNeeded();
      const hand = await createHand({
        session_id: s.sessionId,
        bb: 100,
        effective_stack_start: setup.effectiveStack,
      });
      const snap = await engineStart({
        effective_stack: setup.effectiveStack,
        bb: 100,
        button: setup.button,
        hero_hole: hero,
        villain_hole: villain,
      });
      setSession({ ...s, handId: hand.hand_id });
      setSnapshot(snap);
      setAgreement({ total: 0, diverged: 0 });
    } catch (err) {
      setError(String(err));
    }
  }, [resetStream, setup, startSessionIfNeeded]);

  const applyAction = useCallback(
    async (action: Action) => {
      if (!snapshot) return;
      try {
        const next = await engineApply(snapshot.state, action);
        setSnapshot(next);
      } catch (err) {
        setError(String(err));
      }
    },
    [snapshot],
  );

  const applyReveal = useCallback(
    async (cards: string[]) => {
      if (!snapshot) return;
      try {
        const next = await engineReveal(snapshot.state, cards);
        setSnapshot(next);
      } catch (err) {
        setError(String(err));
      }
    },
    [snapshot],
  );

  const requestAdvice = useCallback(async () => {
    if (!snapshot || !session || !setup.presetId) return;
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
        model_preset: setup.presetId,
        prompt_name: "coach",
        prompt_version: "v1",
        game_state: snapshot.state,
      });
      setDecisionId(decision_id);
      setCurrentDiverged(false);
      startStream(decision_id);
    } catch (err) {
      setError(String(err));
    }
  }, [resetStream, session, setup.presetId, snapshot, startStream]);

  const heroAction = useCallback(
    async (action: Action) => {
      if (!snapshot) return;
      if (decisionId && streamState.advice) {
        const diverged = divergesFromAdvice(
          streamState.advice.action,
          streamState.advice.to_amount_bb,
          action,
          snapshot.state.bb,
        );
        recordAction({ decision_id: decisionId, action }).catch(() => undefined);
        setAgreement((a) => ({
          total: a.total + 1,
          diverged: a.diverged + (diverged ? 1 : 0),
        }));
        setCurrentDiverged(diverged);
      }
      await applyAction(action);
      setDecisionId(null);
      resetStream();
    },
    [applyAction, decisionId, resetStream, snapshot, streamState.advice],
  );

  const handComplete = useMemo(() => {
    if (!snapshot) return false;
    if (snapshot.state.pending_reveal !== null) return false;
    return snapshot.state.street === "complete" || snapshot.state.street === "showdown";
  }, [snapshot]);

  useHotkeys([
    { key: "n", handler: () => void newHand() },
    { key: "Escape", handler: () => resetStream() },
  ]);

  return (
    <div className="flex flex-col gap-4 max-w-[1280px] mx-auto">
      <SetupPanel
        values={setup}
        presets={presets}
        onChange={(patch) => setSetup((s) => ({ ...s, ...patch }))}
        onStart={newHand}
      />

      {error && (
        <div className="rounded bg-red-900/30 text-red-200 p-2 text-sm ring-1 ring-red-500/30">
          {error}
        </div>
      )}

      {session && (
        <div className="text-xs text-stone-400 tabular-nums">
          session {session.sessionId.slice(0, 8)}
          {agreement.total > 0 && (
            <span className="ml-3" data-testid="agreement-rate">
              agreement{" "}
              <span className="text-stone-200 font-semibold">
                {Math.round(
                  ((agreement.total - agreement.diverged) / agreement.total) * 100,
                )}
                %
              </span>{" "}
              ({agreement.total - agreement.diverged}/{agreement.total})
            </span>
          )}
        </div>
      )}

      {snapshot && (
        <div className="flex gap-6 items-start">
          {snapshot.state.pending_reveal !== null && (
            <BoardPicker
              street={snapshot.state.pending_reveal}
              existingBoard={snapshot.state.board}
              excludedCards={[
                ...snapshot.state.hero_hole,
                ...(snapshot.state.villain_hole ?? []),
                ...snapshot.state.board,
              ]}
              onConfirm={applyReveal}
            />
          )}
          <div className="flex-1 flex flex-col gap-4 min-w-0">
            <PokerTable state={snapshot.state} />
            {!handComplete && snapshot.state.to_act && (
              <ActionBar
                key={`${snapshot.state.hand_id}:${snapshot.state.history.length}:${snapshot.state.to_act}`}
                state={snapshot.state}
                legal={snapshot.legal_actions}
                actor={snapshot.state.to_act}
                onAction={
                  snapshot.state.to_act === "hero" ? heroAction : applyAction
                }
                onRequestAdvice={
                  snapshot.state.to_act === "hero" ? requestAdvice : undefined
                }
                adviceDisabled={
                  streamState.status === "thinking" ||
                  streamState.status === "streaming"
                }
              />
            )}
            {handComplete && (
              <HandSummary
                state={snapshot.state}
                agreement={agreement}
                onNewHand={newHand}
              />
            )}
          </div>
          <AdvicePanel
            stream={streamState}
            diverged={currentDiverged}
            presetLabel={setup.presetId}
          />
        </div>
      )}
    </div>
  );
}
