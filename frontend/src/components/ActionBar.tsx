import { useMemo, useState } from "react";
import type { Action, GameState, LegalAction, Seat } from "../api/types";
import {
  clampChips,
  getPresets,
  legalByType,
  type Preset,
  resolveFireType,
  sizeableType,
  sizingPotPct,
} from "./actionBar/sizing";

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
  const lbt = useMemo(() => legalByType(legal), [legal]);
  const sized = sizeableType(lbt);
  const sizingLegal = sized ? lbt[sized]! : null;
  const presets = useMemo<Preset[]>(
    () => (sizingLegal ? getPresets(state, sizingLegal) : []),
    [state, sizingLegal],
  );

  const initialChips = sizingLegal?.min_to ?? 0;
  const [sizeChips, setSizeChips] = useState<number>(initialChips);

  const nudge = (deltaChips: number) => {
    if (!sizingLegal) return;
    setSizeChips((prev) => clampChips(prev + deltaChips, sizingLegal));
  };

  const fireSizing = () => {
    const resolved = resolveFireType(sizeChips, lbt);
    if (!resolved) return;
    onAction({ actor, type: resolved.type, to_amount: resolved.to });
  };

  const fireFixed = (type: "fold" | "check" | "call") => {
    const la = lbt[type];
    if (!la) return;
    // call/check/fold carry no amount on the LegalAction; the backend derives
    // the call amount from state.committed (see engine/models.py).
    onAction({ actor, type, to_amount: null });
  };

  // Delta the actor must put in to call, derived from state (not legal).
  const callDeltaChips = (() => {
    const other = actor === "hero" ? "villain" : "hero";
    return Math.max(0, state.committed[other] - state.committed[actor]);
  })();

  const fireAllIn = () => {
    if (!lbt.allin?.max_to) return;
    onAction({ actor, type: "allin", to_amount: lbt.allin.max_to });
  };

  const bb = state.bb;
  // Clamp for display so a stale sizeChips (e.g. across a spot transition
  // where the parent didn't remount) can never render an out-of-range
  // readout or a slider thumb that disagrees with the native range input.
  const effectiveSizeChips = sizingLegal ? clampChips(sizeChips, sizingLegal) : sizeChips;
  const sizeBb = effectiveSizeChips / bb;
  const potPct = sizingLegal ? sizingPotPct(effectiveSizeChips, state) : null;
  const atMax =
    sizingLegal?.max_to != null && effectiveSizeChips >= sizingLegal.max_to;
  const actorLabel = actor === "hero" ? "Your turn" : "Villain to act";

  return (
    <div
      className={`rounded-xl p-4 flex flex-col gap-3 ring-1 ${
        actor === "hero"
          ? "bg-stone-900/90 ring-white/10"
          : "bg-stone-900/70 ring-white/5"
      }`}
      data-testid="action-bar"
      data-actor={actor}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-stone-100">{actorLabel}</span>
        <div className="flex items-center gap-3">
          {actor === "villain" && (
            <span className="text-xs text-stone-400">Click what villain just did</span>
          )}
          {onRequestAdvice && (
            <button
              data-testid="request-advice"
              onClick={onRequestAdvice}
              disabled={adviceDisabled}
              className="text-xs font-semibold text-amber-400 hover:text-amber-300 disabled:opacity-40 transition"
            >
              advise
            </button>
          )}
        </div>
      </div>

      {sizingLegal && sizingLegal.min_to != null && sizingLegal.max_to != null && (
        <SizingPanel
          state={state}
          la={sizingLegal}
          presets={presets}
          sizeChips={effectiveSizeChips}
          onSetChips={(c) => setSizeChips(clampChips(c, sizingLegal))}
          onNudge={nudge}
          sizeBb={sizeBb}
          potPct={potPct}
        />
      )}

      <div className="grid grid-cols-3 gap-2">
        <ActionSlot
          testId="action-fold"
          visible={Boolean(lbt.fold)}
          onClick={() => fireFixed("fold")}
          tone="neutral"
          label="Fold"
        />
        <ActionSlot
          testId={lbt.check ? "action-check" : "action-call"}
          visible={Boolean(lbt.check || lbt.call)}
          onClick={() => fireFixed(lbt.check ? "check" : "call")}
          tone="info"
          label={
            lbt.check
              ? "Check"
              : `Call ${(callDeltaChips / bb).toFixed(1)}bb`
          }
        />
        {sizingLegal ? (
          <button
            data-testid="action-raise"
            onClick={atMax && lbt.allin ? fireAllIn : fireSizing}
            className={`h-14 rounded-xl font-semibold text-white shadow transition active:scale-[0.98] flex flex-col items-center justify-center leading-tight ${
              atMax && lbt.allin
                ? "bg-gradient-to-b from-red-500 to-red-700 hover:from-red-400 hover:to-red-600"
                : "bg-gradient-to-b from-emerald-500 to-emerald-700 hover:from-emerald-400 hover:to-emerald-600"
            }`}
          >
            {atMax && lbt.allin ? (
              <>
                <span className="text-xs opacity-80">All-in</span>
                <span className="text-base tabular-nums">{sizeBb.toFixed(1)}bb</span>
              </>
            ) : (
              <>
                <span className="text-xs opacity-80">
                  {sized === "raise" ? "Raise to" : "Bet"}
                </span>
                <span className="text-base tabular-nums">{sizeBb.toFixed(1)}bb</span>
              </>
            )}
          </button>
        ) : lbt.allin ? (
          <ActionSlot
            testId="action-allin"
            visible
            onClick={fireAllIn}
            tone="allin"
            label={`All-in ${((lbt.allin.max_to ?? 0) / bb).toFixed(1)}bb`}
          />
        ) : (
          <div />
        )}
      </div>
    </div>
  );
}

function SizingPanel({
  state,
  la,
  presets,
  sizeChips,
  onSetChips,
  onNudge,
  sizeBb,
  potPct,
}: {
  state: GameState;
  la: LegalAction;
  presets: Preset[];
  sizeChips: number;
  onSetChips: (c: number) => void;
  onNudge: (deltaChips: number) => void;
  sizeBb: number;
  potPct: number | null;
}) {
  const min = la.min_to!;
  const max = la.max_to!;
  const activeLabel = presets.find((p) => p.toChips === sizeChips)?.label;
  const [editing, setEditing] = useState(false);
  const [rawInput, setRawInput] = useState("");

  const commitEdit = () => {
    const parsed = parseFloat(rawInput);
    if (Number.isFinite(parsed) && parsed > 0) {
      onSetChips(Math.round(parsed * state.bb));
    }
    setEditing(false);
  };

  return (
    <div className="rounded-lg bg-black/30 ring-1 ring-white/5 p-3 flex flex-col gap-3">
      <div className="flex gap-1.5 flex-wrap">
        {presets.map((p) => {
          const isMax = p.kind === "max";
          const active = activeLabel === p.label;
          return (
            <button
              key={p.label}
              data-testid={`preset-${p.label}`}
              onClick={() => onSetChips(p.toChips)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                active
                  ? isMax
                    ? "bg-red-500/20 ring-1 ring-red-400 text-red-100"
                    : "bg-emerald-500/20 ring-1 ring-emerald-400 text-emerald-100"
                  : isMax
                    ? "bg-red-500/10 text-red-200 hover:bg-red-500/20"
                    : "bg-white/5 text-stone-200 hover:bg-white/15"
              }`}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <button
          data-testid="size-minus"
          onClick={() => onNudge(-state.bb)}
          className="h-9 w-9 rounded-lg bg-white/5 hover:bg-white/15 text-stone-100 text-lg font-bold transition disabled:opacity-40"
          disabled={sizeChips <= min}
          aria-label="Decrease size by 1bb"
        >
          −
        </button>
        <div className="relative flex-1 h-9 flex items-center">
          <div className="absolute inset-x-0 h-2 rounded-full bg-stone-700 pointer-events-none" />
          <div
            className="absolute h-2 rounded-full bg-emerald-500 pointer-events-none"
            style={{ width: `${pct(sizeChips, min, max)}%` }}
          />
          {presets.map((p) => (
            <span
              key={p.label}
              className={`absolute w-0.5 h-3 rounded-full pointer-events-none ${
                p.kind === "max" ? "bg-red-400" : "bg-white/60"
              }`}
              style={{ left: `calc(${pct(p.toChips, min, max)}% - 1px)` }}
            />
          ))}
          <input
            type="range"
            min={min}
            max={max}
            step={1}
            value={sizeChips}
            onChange={(e) => onSetChips(Number(e.target.value))}
            data-testid="size-slider"
            aria-label="Bet size in chips"
            className="relative w-full appearance-none bg-transparent cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:ring-2 [&::-webkit-slider-thumb]:ring-emerald-400 [&::-webkit-slider-thumb]:shadow [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:bg-white [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-emerald-400"
          />
        </div>
        <button
          data-testid="size-plus"
          onClick={() => onNudge(state.bb)}
          className="h-9 w-9 rounded-lg bg-white/5 hover:bg-white/15 text-stone-100 text-lg font-bold transition disabled:opacity-40"
          disabled={sizeChips >= max}
          aria-label="Increase size by 1bb"
        >
          +
        </button>
      </div>

      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          {editing ? (
            <input
              type="text"
              value={rawInput}
              onChange={(e) => setRawInput(e.target.value)}
              onBlur={commitEdit}
              onKeyDown={(e) => {
                if (e.key === "Enter") { e.currentTarget.blur(); }
                if (e.key === "Escape") { setEditing(false); }
              }}
              autoFocus
              aria-label="Bet size in bb"
              className="text-3xl font-bold tabular-nums text-stone-50 bg-transparent border-b-2 border-emerald-400 outline-none w-20 transition-colors"
            />
          ) : (
            <span
              data-testid="size-readout-bb"
              onClick={() => { setEditing(true); setRawInput(sizeBb.toFixed(1)); }}
              className="text-3xl font-bold tabular-nums text-stone-50 cursor-text hover:text-emerald-300 transition-colors select-none"
              title="Click to type a size"
            >
              {sizeBb.toFixed(1)}
            </span>
          )}
          <span className="text-xs text-stone-400">bb</span>
        </div>
        <span className="text-xs text-stone-400 tabular-nums">
          = {sizeChips} chips
          {potPct != null ? ` · ${Math.round(potPct)}% pot` : ""}
        </span>
      </div>
    </div>
  );
}

function pct(value: number, min: number, max: number): number {
  if (max === min) return 0;
  return ((value - min) / (max - min)) * 100;
}

function ActionSlot({
  testId,
  visible,
  onClick,
  tone,
  label,
}: {
  testId: string;
  visible: boolean;
  onClick: () => void;
  tone: "neutral" | "info" | "allin";
  label: string;
}) {
  if (!visible) return <div />;
  const toneClass =
    tone === "neutral"
      ? "bg-stone-700 hover:bg-stone-600 text-stone-100"
      : tone === "info"
        ? "bg-sky-700 hover:bg-sky-600 text-white"
        : "bg-gradient-to-b from-red-500 to-red-700 hover:from-red-400 hover:to-red-600 text-white";
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className={`h-14 rounded-xl font-semibold shadow transition active:scale-[0.98] ${toneClass}`}
    >
      {label}
    </button>
  );
}
