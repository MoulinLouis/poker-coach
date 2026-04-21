import { useMemo, useState } from "react";
import type { Action, GameState, LegalAction, Seat } from "../api/types";
import { useLocale } from "../i18n";
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
  const { t } = useLocale();
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
    onAction({ actor, type, to_amount: null });
  };

  const callDeltaChips = (() => {
    const other = actor === "hero" ? "villain" : "hero";
    return Math.max(0, state.committed[other] - state.committed[actor]);
  })();

  const fireAllIn = () => {
    if (!lbt.allin?.max_to) return;
    onAction({ actor, type: "allin", to_amount: lbt.allin.max_to });
  };

  const bb = state.bb;
  const effectiveSizeChips = sizingLegal ? clampChips(sizeChips, sizingLegal) : sizeChips;
  const sizeBb = effectiveSizeChips / bb;
  const potPct = sizingLegal ? sizingPotPct(effectiveSizeChips, state) : null;
  const atMax =
    sizingLegal?.max_to != null && effectiveSizeChips >= sizingLegal.max_to;
  const isHero = actor === "hero";

  return (
    <div
      className="relative rounded-2xl p-3 sm:p-5 flex flex-col gap-3 sm:gap-4"
      data-testid="action-bar"
      data-actor={actor}
      style={{
        background:
          "linear-gradient(180deg, rgba(29,23,24,0.88), rgba(20,16,18,0.92))",
        border: isHero
          ? "1px solid rgba(201,162,94,0.4)"
          : "1px solid rgba(201,162,94,0.12)",
        boxShadow:
          "0 20px 60px -30px rgba(0,0,0,0.9), inset 0 1px 0 rgba(201,162,94,0.12)",
      }}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className={`w-2 h-2 rounded-full ${isHero ? "animate-pulse" : ""}`}
            style={{
              background: isHero ? "var(--color-gold)" : "var(--color-parchment-dim)",
              boxShadow: isHero ? "0 0 12px var(--color-gold)" : undefined,
            }}
          />
          <div className="flex flex-col -space-y-0.5">
            <span className="text-[9px] uppercase tracking-[0.35em] font-mono text-[color:var(--color-parchment-dim)]">
              {isHero ? t("actionBar.actKicker") : t("actionBar.observeKicker")}
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-[color:var(--color-bone)]">
              {isHero ? t("actionBar.yourTurn") : t("actionBar.villainToAct")}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {actor === "villain" && (
            <span className="text-[11px] text-[color:var(--color-parchment)]">
              {t("actionBar.villainHint")}
            </span>
          )}
          {onRequestAdvice && (
            <button
              data-testid="request-advice"
              onClick={onRequestAdvice}
              disabled={adviceDisabled}
              className="relative group font-mono text-[11px] uppercase tracking-[0.2em] px-3 py-1.5 rounded-md transition disabled:opacity-40"
              style={{
                color: "var(--color-gold-bright)",
                background: "rgba(201,162,94,0.08)",
                border: "1px solid rgba(201,162,94,0.45)",
              }}
            >
              {t("actionBar.advise")}
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

      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        <ActionSlot
          testId="action-fold"
          visible={Boolean(lbt.fold)}
          onClick={() => fireFixed("fold")}
          tone="fold"
          label={t("actionBar.fold")}
        />
        <ActionSlot
          testId={lbt.check ? "action-check" : "action-call"}
          visible={Boolean(lbt.check || lbt.call)}
          onClick={() => fireFixed(lbt.check ? "check" : "call")}
          tone="passive"
          label={lbt.check ? t("actionBar.check") : t("actionBar.call")}
          sub={
            !lbt.check
              ? `${(callDeltaChips / bb).toFixed(1)} ${t("actionBar.bbUnit")}`
              : undefined
          }
        />
        {sizingLegal ? (
          <ChipAction
            testId="action-raise"
            onClick={atMax && lbt.allin ? fireAllIn : fireSizing}
            tone={atMax && lbt.allin ? "allin" : "aggressive"}
            label={
              atMax && lbt.allin
                ? t("actionBar.allIn")
                : sized === "raise"
                  ? t("actionBar.raiseTo")
                  : t("actionBar.bet")
            }
            sub={`${sizeBb.toFixed(1)} ${t("actionBar.bbUnit")}`}
          />
        ) : lbt.allin ? (
          <ChipAction
            testId="action-allin"
            onClick={fireAllIn}
            tone="allin"
            label={t("actionBar.allIn")}
            sub={`${((lbt.allin.max_to ?? 0) / bb).toFixed(1)} ${t("actionBar.bbUnit")}`}
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
  const { t } = useLocale();
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
    <div
      className="relative rounded-xl p-3 sm:p-4 flex flex-col gap-3 sm:gap-3.5"
      style={{
        background:
          "linear-gradient(180deg, rgba(10,7,6,0.65), rgba(10,7,6,0.4))",
        border: "1px solid rgba(201,162,94,0.15)",
        boxShadow: "inset 0 1px 0 rgba(0,0,0,0.4)",
      }}
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] tracking-[0.3em] uppercase text-[color:var(--color-parchment-dim)]">
          {t("actionBar.sizingHeader")}
        </span>
        <span className="font-mono text-[10px] tabular-nums text-[color:var(--color-parchment)]">
          {min / state.bb}–{(max / state.bb).toFixed(0)} {t("actionBar.bbUnit")}
        </span>
      </div>

      <div className="flex gap-1.5 flex-wrap">
        {presets.map((p) => {
          const isMax = p.kind === "max";
          const active = activeLabel === p.label;
          return (
            <button
              key={p.label}
              data-testid={`preset-${p.label}`}
              onClick={() => onSetChips(p.toChips)}
              className="relative px-3 py-1 rounded-full font-mono text-[10px] tracking-widest uppercase transition"
              style={{
                color: active
                  ? isMax
                    ? "var(--color-coral)"
                    : "var(--color-gold-bright)"
                  : isMax
                    ? "var(--color-coral-soft)"
                    : "var(--color-parchment)",
                background: active
                  ? isMax
                    ? "rgba(232,93,76,0.12)"
                    : "rgba(201,162,94,0.12)"
                  : "transparent",
                border: active
                  ? isMax
                    ? "1px solid rgba(232,93,76,0.6)"
                    : "1px solid rgba(201,162,94,0.6)"
                  : "1px solid rgba(201,162,94,0.18)",
              }}
            >
              {p.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <button
          data-testid="size-minus"
          onClick={() => onNudge(-state.bb)}
          disabled={sizeChips <= min}
          aria-label={t("actionBar.decreaseAria")}
          className="h-9 w-9 rounded-full font-display text-xl leading-none transition disabled:opacity-30"
          style={{
            color: "var(--color-bone)",
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(201,162,94,0.25)",
          }}
        >
          −
        </button>
        <div className="relative flex-1 h-9 flex items-center">
          <div
            className="absolute inset-x-0 h-[3px] rounded-full pointer-events-none"
            style={{
              background: "rgba(255,255,255,0.06)",
              boxShadow: "inset 0 1px 0 rgba(0,0,0,0.5)",
            }}
          />
          <div
            className="absolute h-[3px] rounded-full pointer-events-none"
            style={{
              width: `${pct(sizeChips, min, max)}%`,
              background:
                "linear-gradient(90deg, var(--color-gold-deep), var(--color-gold-bright))",
              boxShadow: "0 0 8px rgba(240,211,138,0.5)",
            }}
          />
          {presets.map((p) => (
            <span
              key={p.label}
              className="absolute w-px h-3 pointer-events-none"
              style={{
                left: `calc(${pct(p.toChips, min, max)}% - 0.5px)`,
                background:
                  p.kind === "max"
                    ? "var(--color-coral)"
                    : "rgba(237,227,204,0.5)",
              }}
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
            aria-label={t("actionBar.sliderAria")}
            className="relative w-full appearance-none bg-transparent cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none
              [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5
              [&::-webkit-slider-thumb]:rounded-full
              [&::-webkit-slider-thumb]:bg-[color:var(--color-gold-bright)]
              [&::-webkit-slider-thumb]:ring-2 [&::-webkit-slider-thumb]:ring-[color:var(--color-gold-deep)]
              [&::-webkit-slider-thumb]:shadow-[0_0_0_2px_rgba(10,7,6,0.8),0_4px_10px_-2px_rgba(240,211,138,0.5)]
              [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5
              [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:bg-[color:var(--color-gold-bright)]
              [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-[color:var(--color-gold-deep)]"
          />
        </div>
        <button
          data-testid="size-plus"
          onClick={() => onNudge(state.bb)}
          disabled={sizeChips >= max}
          aria-label={t("actionBar.increaseAria")}
          className="h-9 w-9 rounded-full font-display text-xl leading-none transition disabled:opacity-30"
          style={{
            color: "var(--color-bone)",
            background: "rgba(255,255,255,0.04)",
            border: "1px solid rgba(201,162,94,0.25)",
          }}
        >
          +
        </button>
      </div>

      <div className="flex items-end justify-between">
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
              aria-label={t("actionBar.readoutAria")}
              className="text-[2rem] font-bold tabular-nums bg-transparent border-b-2 outline-none w-24 transition-colors tracking-tight"
              style={{
                color: "var(--color-gold-bright)",
                borderColor: "var(--color-gold)",
              }}
            />
          ) : (
            <span
              data-testid="size-readout-bb"
              onClick={() => { setEditing(true); setRawInput(sizeBb.toFixed(1)); }}
              className="text-[2rem] font-bold tabular-nums cursor-text select-none transition-colors leading-none tracking-tight"
              style={{ color: "var(--color-bone)" }}
              title={t("actionBar.readoutTitle")}
            >
              {sizeBb.toFixed(1)}
            </span>
          )}
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
            {t("actionBar.bbUnit")}
          </span>
        </div>
        <div className="flex items-baseline gap-3 font-mono text-[10px] tabular-nums">
          <span className="text-[color:var(--color-parchment-dim)]">
            {sizeChips} {t("actionBar.chipsSuffix")}
          </span>
          {potPct != null && (
            <>
              <span className="text-[color:var(--color-gold-shadow)]">·</span>
              <span className="text-[color:var(--color-gold-pale)]">
                {Math.round(potPct)}% {t("actionBar.potSuffix")}
              </span>
            </>
          )}
        </div>
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
  sub,
}: {
  testId: string;
  visible: boolean;
  onClick: () => void;
  tone: "fold" | "passive";
  label: string;
  sub?: string;
}) {
  if (!visible) return <div />;
  const chipCore =
    tone === "fold"
      ? "linear-gradient(180deg, #3b2e2e 0%, #1f1718 100%)"
      : "linear-gradient(180deg, #23504a 0%, #0f2b26 100%)";
  const textColor =
    tone === "fold" ? "var(--color-parchment)" : "var(--color-bone)";

  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className="chip-button h-14 flex flex-col items-center justify-center leading-tight"
      style={
        {
          "--chip-core": chipCore,
          color: textColor,
        } as React.CSSProperties
      }
    >
      <span className="font-semibold text-[15px] tracking-tight">
        {label}
      </span>
      {sub && (
        <span className="font-mono text-[10px] opacity-70 tabular-nums">
          {sub}
        </span>
      )}
    </button>
  );
}

function ChipAction({
  testId,
  onClick,
  tone,
  label,
  sub,
}: {
  testId: string;
  onClick: () => void;
  tone: "aggressive" | "allin";
  label: string;
  sub?: string;
}) {
  const chipCore =
    tone === "aggressive"
      ? "linear-gradient(180deg, #d8b876 0%, #a07a2e 100%)"
      : "linear-gradient(180deg, #e85d4c 0%, #8a1e16 100%)";
  const textColor =
    tone === "aggressive" ? "var(--color-ink)" : "var(--color-bone)";
  return (
    <button
      data-testid={testId}
      onClick={onClick}
      className="chip-button h-14 flex flex-col items-center justify-center leading-tight"
      style={
        {
          "--chip-core": chipCore,
          color: textColor,
        } as React.CSSProperties
      }
    >
      <span className="font-bold text-[15px] tracking-tight">
        {label}
      </span>
      {sub && (
        <span className="font-mono text-[11px] tabular-nums opacity-80">
          {sub}
        </span>
      )}
    </button>
  );
}
