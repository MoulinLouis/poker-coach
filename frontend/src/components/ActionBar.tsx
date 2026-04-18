import { useMemo, useState } from "react";
import { useHotkeys } from "../hooks/useHotkeys";
import type { Action, ActionType, GameState, LegalAction, Seat } from "../api/types";

const HOTKEY: Partial<Record<ActionType, string>> = {
  fold: "f",
  check: "k",
  call: "c",
  bet: "b",
  raise: "r",
  allin: "a",
};

type Preset = { label: string; toBb: number };

function preflopPresets(state: GameState, la: LegalAction): Preset[] {
  if (la.min_to == null || la.max_to == null) return [];
  const minBb = la.min_to / state.bb;
  const maxBb = la.max_to / state.bb;
  return [
    { label: "min", toBb: minBb },
    { label: "2.5x", toBb: 2.5 },
    { label: "3x", toBb: 3 },
    { label: "3.5x", toBb: 3.5 },
  ].filter((p) => p.toBb >= minBb && p.toBb <= maxBb);
}

function postflopPresets(state: GameState, la: LegalAction): Preset[] {
  if (la.min_to == null || la.max_to == null) return [];
  const potBb = (state.pot + state.committed.hero + state.committed.villain) / state.bb;
  const actorCommittedBb =
    (state.to_act === "hero" ? state.committed.hero : state.committed.villain) / state.bb;
  const minBb = la.min_to / state.bb;
  const maxBb = la.max_to / state.bb;
  const ratios: { label: string; r: number }[] = [
    { label: "33%", r: 0.33 },
    { label: "50%", r: 0.5 },
    { label: "75%", r: 0.75 },
    { label: "pot", r: 1.0 },
    { label: "150%", r: 1.5 },
  ];
  return ratios.map((r) => {
    const raw = actorCommittedBb + potBb * r.r;
    return { label: r.label, toBb: Math.max(minBb, Math.min(maxBb, raw)) };
  });
}

export function ActionBar({
  state,
  legal,
  actor,
  onAction,
  onRequestAdvice,
  adviceDisabled,
}: {
  state: GameState;
  legal: LegalAction[];
  actor: Seat;
  onAction: (a: Action) => void;
  onRequestAdvice?: () => void;
  adviceDisabled?: boolean;
}) {
  const [sizeBb, setSizeBb] = useState<string>("");
  const legalByType = useMemo(
    () => Object.fromEntries(legal.map((l) => [l.type, l])) as Record<string, LegalAction>,
    [legal],
  );
  const sizeableType = legalByType.raise ? "raise" : legalByType.bet ? "bet" : null;

  const presets = useMemo<Preset[]>(() => {
    if (!sizeableType) return [];
    const la = legalByType[sizeableType];
    return state.street === "preflop"
      ? preflopPresets(state, la)
      : postflopPresets(state, la);
  }, [legalByType, sizeableType, state]);

  const fire = (type: ActionType) => {
    const la = legalByType[type];
    if (!la) return;
    let to: number | null = null;
    if (type === "bet" || type === "raise") {
      const bb = parseFloat(sizeBb);
      if (!Number.isFinite(bb) || bb <= 0) return;
      to = Math.round(bb * state.bb);
    } else if (type === "allin") {
      to = la.max_to ?? null;
    }
    onAction({ actor, type, to_amount: to });
    setSizeBb("");
  };

  useHotkeys([
    ...(Object.entries(HOTKEY) as [ActionType, string][]).map(([t, k]) => ({
      key: k,
      handler: () => {
        if (legalByType[t]) fire(t);
      },
      disabled: !legalByType[t],
    })),
    ...(presets.map((p, i) => ({
      key: String(i + 1),
      handler: () => setSizeBb(p.toBb.toFixed(2)),
    })) as HotkeyWithoutDisabled[]),
    {
      key: " ",
      handler: () => onRequestAdvice?.(),
      disabled: !onRequestAdvice || Boolean(adviceDisabled),
    },
  ]);

  const actorLabel = actor === "hero" ? "Your turn" : "Villain to act";

  return (
    <div
      className="rounded-xl bg-stone-900/90 p-4 flex flex-col gap-3 ring-1 ring-white/10"
      data-testid="action-bar"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-stone-100">{actorLabel}</span>
        {actor === "villain" && (
          <span className="text-xs text-stone-400">
            Click what villain just did
          </span>
        )}
      </div>

      {presets.length > 0 && (
        <div className="flex gap-2 flex-wrap items-center">
          {presets.map((p, i) => (
            <button
              key={p.label}
              data-testid={`preset-${p.label}`}
              onClick={() => setSizeBb(p.toBb.toFixed(2))}
              className="px-2.5 py-1 rounded border border-white/20 bg-white/5 text-stone-100 text-sm hover:bg-white/15 transition"
            >
              <kbd className="opacity-50 mr-1 text-[10px]">{i + 1}</kbd>
              {p.label}{" "}
              <span className="opacity-60 tabular-nums">({p.toBb.toFixed(1)}bb)</span>
            </button>
          ))}
          <input
            data-testid="size-input"
            placeholder="size (bb)"
            value={sizeBb}
            onChange={(e) => setSizeBb(e.target.value)}
            className="w-24 px-2 py-1 rounded border border-white/20 bg-black/30 text-stone-100 text-sm"
          />
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {legal.map((la) => (
          <button
            key={la.type}
            data-testid={`action-${la.type}`}
            onClick={() => fire(la.type)}
            className={`px-4 py-2 rounded-lg font-semibold text-white shadow transition capitalize ${
              la.type === "fold"
                ? "bg-stone-700 hover:bg-stone-600"
                : la.type === "allin"
                  ? "bg-red-700 hover:bg-red-600"
                  : "bg-emerald-700 hover:bg-emerald-600"
            }`}
          >
            {HOTKEY[la.type] && (
              <kbd className="mr-2 opacity-60 text-[10px] font-mono">{HOTKEY[la.type]}</kbd>
            )}
            {la.type}
          </button>
        ))}
        {onRequestAdvice && (
          <button
            data-testid="request-advice"
            onClick={onRequestAdvice}
            disabled={adviceDisabled}
            className="ml-auto px-4 py-2 rounded-lg font-semibold text-white bg-amber-600 hover:bg-amber-500 disabled:opacity-50 transition"
          >
            <kbd className="mr-2 opacity-60 text-[10px] font-mono">space</kbd>
            advise
          </button>
        )}
      </div>
    </div>
  );
}

type HotkeyWithoutDisabled = {
  key: string;
  handler: () => void;
  disabled?: boolean;
};
