import { useEffect, useRef, useState } from "react";
import type { Advice } from "../api/types";
import type { StreamState } from "../api/useAdviceStream";
import { type TranslationState, useTranslation } from "../api/useTranslation";

export function AdvicePanel({
  stream,
  diverged,
  presetLabel,
  onFollow,
}: {
  stream: StreamState;
  diverged: boolean;
  presetLabel: string;
  onFollow?: () => void;
}) {
  const reasoningTranslation = useTranslation(stream.reasoning ?? "");
  const adviceTranslation = useTranslation(stream.advice?.reasoning ?? "");

  const displayedReasoning =
    reasoningTranslation.lang === "fr" && reasoningTranslation.frText !== null
      ? reasoningTranslation.frText
      : stream.reasoning ?? "";

  const displayedAdviceReasoning =
    adviceTranslation.lang === "fr" && adviceTranslation.frText !== null
      ? adviceTranslation.frText
      : stream.advice?.reasoning ?? "";

  return (
    <aside
      data-testid="advice-panel"
      className="relative w-full lg:w-[400px] lg:shrink-0 flex flex-col gap-4 p-4 sm:p-5 rounded-2xl bg-lacquer"
      style={{
        border: "1px solid rgba(201,162,94,0.25)",
        boxShadow:
          "0 30px 80px -40px rgba(0,0,0,0.9), inset 0 1px 0 rgba(201,162,94,0.15)",
      }}
    >
      {/* deco corner accents */}
      <CornerAccent className="absolute top-2 left-2" />
      <CornerAccent className="absolute top-2 right-2" flipX />
      <CornerAccent className="absolute bottom-2 left-2" flipY />
      <CornerAccent className="absolute bottom-2 right-2" flipX flipY />

      <header className="flex items-center justify-between gap-2">
        <div className="flex flex-col -space-y-0.5">
          <span className="text-[9px] uppercase tracking-[0.4em] text-[color:var(--color-parchment-dim)]">
            Coach
          </span>
          <span className="text-lg font-semibold tracking-tight text-[color:var(--color-bone)]">
            Advisor
          </span>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="font-mono text-[9px] uppercase tracking-[0.22em] text-[color:var(--color-parchment)] bg-[color:var(--color-lacquer-raised)] px-2 py-0.5 rounded-sm border border-[color:var(--color-gold-shadow)]/50">
            {presetLabel || "—"}
          </span>
          {diverged && (
            <span
              data-testid="diverged-badge"
              className="font-mono px-2 py-0.5 text-[9px] tracking-[0.3em] uppercase"
              style={{
                color: "var(--color-coral)",
                background: "rgba(232,93,76,0.1)",
                border: "1px solid rgba(232,93,76,0.4)",
                borderRadius: "2px",
              }}
            >
              Diverged
            </span>
          )}
        </div>
      </header>

      <div className="deco-rule" />

      {stream.status === "idle" && (
        <EmptyState />
      )}

      {stream.status === "thinking" && <ThinkingIndicator />}

      {stream.reasoning && (
        <ThinkingBlock
          stream={stream}
          displayedReasoning={displayedReasoning}
          translation={reasoningTranslation}
        />
      )}

      {stream.advice && (
        <AdviceCard
          advice={stream.advice}
          displayedReasoning={displayedAdviceReasoning}
          translation={adviceTranslation}
          onFollow={onFollow}
        />
      )}

      {stream.costUsd != null && (
        <div className="flex items-center gap-2 text-[10px] font-mono text-[color:var(--color-parchment-dim)]">
          <span className="w-1 h-1 rounded-full bg-[color:var(--color-gold)]" />
          <span className="tabular-nums">
            ${stream.costUsd.toFixed(4)} · reasoning tariff
          </span>
        </div>
      )}

      {stream.errorMessage && (
        <div
          data-testid="advice-error"
          className="text-sm p-3 rounded"
          style={{
            background: "rgba(232,93,76,0.08)",
            border: "1px solid rgba(232,93,76,0.35)",
            color: "var(--color-coral)",
          }}
        >
          {stream.errorMessage}
        </div>
      )}
    </aside>
  );
}

function CornerAccent({
  className = "",
  flipX = false,
  flipY = false,
}: {
  className?: string;
  flipX?: boolean;
  flipY?: boolean;
}) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={`w-5 h-5 text-[color:var(--color-gold)]/40 pointer-events-none ${className}`}
      style={{
        transform: `scale(${flipX ? -1 : 1}, ${flipY ? -1 : 1})`,
      }}
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
      aria-hidden
    >
      <path d="M2 12 L2 2 L12 2" />
      <path d="M6 6 L10 6 L10 10" />
      <circle cx="4" cy="4" r="0.8" fill="currentColor" />
    </svg>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-6">
      <svg viewBox="0 0 40 40" className="w-8 h-8 text-[color:var(--color-gold)]/40" fill="none" stroke="currentColor" strokeWidth="1">
        <circle cx="20" cy="20" r="14" />
        <circle cx="20" cy="20" r="9" strokeDasharray="2 2" />
        <circle cx="20" cy="20" r="3" fill="currentColor" opacity="0.4" />
      </svg>
      <p className="text-[13px] text-[color:var(--color-parchment)] leading-snug max-w-[240px]">
        Click{" "}
        <span className="font-semibold text-[color:var(--color-gold-pale)]">
          advise
        </span>{" "}
        on hero's turn to get a read.
      </p>
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <div className="flex items-center gap-3 text-sm py-2">
      <span className="relative flex h-2 w-2">
        <span
          className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
          style={{ background: "var(--color-gold)" }}
        />
        <span
          className="relative inline-flex rounded-full h-2 w-2"
          style={{ background: "var(--color-gold-bright)" }}
        />
      </span>
      <span className="font-mono text-[11px] tracking-[0.25em] uppercase text-[color:var(--color-gold-pale)]">
        Thinking
      </span>
    </div>
  );
}

function ThinkingBlock({
  stream,
  displayedReasoning,
  translation,
}: {
  stream: StreamState;
  displayedReasoning: string;
  translation: TranslationState;
}) {
  const [userOverride, setUserOverride] = useState<boolean | null>(null);
  const prevStatusRef = useRef(stream.status);

  useEffect(() => {
    if (prevStatusRef.current !== stream.status && stream.status === "idle") {
      setUserOverride(null);
    }
    prevStatusRef.current = stream.status;
  }, [stream.status]);

  const isTerminal = stream.status === "done" || stream.status === "error";
  const collapsed = userOverride !== null ? userOverride : isTerminal;
  const live = stream.status === "streaming" || stream.status === "thinking";

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          data-testid="thinking-toggle"
          onClick={() => setUserOverride(!collapsed)}
          className="flex items-center gap-2 text-[9px] uppercase tracking-[0.3em] font-mono text-[color:var(--color-parchment)] hover:text-[color:var(--color-bone)] transition"
        >
          <span>{collapsed ? "▸" : "▾"}</span>
          <span>Reasoning</span>
          {live && (
            <span
              className="w-1.5 h-1.5 rounded-full animate-pulse"
              style={{ background: "var(--color-gold)" }}
            />
          )}
          <span className="tabular-nums opacity-60 normal-case tracking-normal">
            · {stream.reasoning!.length} chars
          </span>
        </button>
        <LangToggle state={translation} disabled={!isTerminal} />
      </div>
      {!collapsed && (
        <pre
          data-testid="advice-reasoning"
          className="max-h-[260px] overflow-auto text-[11px] leading-[1.7] font-mono whitespace-pre-wrap p-3 rounded"
          style={{
            color: "var(--color-parchment)",
            background:
              "linear-gradient(180deg, rgba(10,7,6,0.6), rgba(10,7,6,0.9))",
            border: "1px solid rgba(201,162,94,0.12)",
            boxShadow: "inset 0 1px 0 rgba(0,0,0,0.4)",
          }}
        >
          {displayedReasoning}
        </pre>
      )}
    </div>
  );
}

function LangToggle({
  state,
  disabled = false,
}: {
  state: TranslationState;
  disabled?: boolean;
}) {
  const { lang, loading, error, toggle } = state;
  const label = loading ? "…" : error ? "!" : lang === "fr" ? "FR" : "EN";
  return (
    <button
      type="button"
      data-testid="lang-toggle"
      disabled={disabled || loading}
      onClick={toggle}
      className="font-mono text-[9px] uppercase tracking-[0.25em] px-2 py-0.5 rounded-sm transition disabled:opacity-40 disabled:cursor-not-allowed"
      style={{
        color: "var(--color-gold-pale)",
        background: "var(--color-lacquer-raised)",
        border: "1px solid rgba(201,162,94,0.3)",
      }}
      title={error ? `translation error: ${error}` : undefined}
    >
      {label}
    </button>
  );
}

function AdviceCard({
  advice,
  displayedReasoning,
  translation,
  onFollow,
}: {
  advice: Advice;
  displayedReasoning: string;
  translation: TranslationState;
  onFollow?: () => void;
}) {
  const confidence = advice.confidence;

  const actionTheme: Record<
    string,
    { glow: string; accent: string; label: string }
  > = {
    fold: { glow: "rgba(137,127,101,0.3)", accent: "var(--color-parchment)", label: "Fold" },
    check: { glow: "rgba(45,146,116,0.35)", accent: "var(--color-jade)", label: "Check" },
    call: { glow: "rgba(45,146,116,0.35)", accent: "var(--color-jade)", label: "Call" },
    bet: { glow: "rgba(201,162,94,0.45)", accent: "var(--color-gold-bright)", label: "Bet" },
    raise: { glow: "rgba(201,162,94,0.45)", accent: "var(--color-gold-bright)", label: "Raise" },
    allin: { glow: "rgba(232,93,76,0.45)", accent: "var(--color-coral)", label: "All-in" },
  };
  const theme = actionTheme[advice.action] ?? actionTheme.fold;

  return (
    <div
      data-testid="advice-card"
      className="relative anim-fade-up rounded-xl overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, rgba(38,10,14,0.85) 0%, rgba(22,6,8,0.85) 100%)",
        border: "1px solid rgba(201,162,94,0.45)",
        boxShadow: `0 10px 40px -10px ${theme.glow}, inset 0 1px 0 rgba(201,162,94,0.2)`,
      }}
    >
      {/* placard header */}
      <div className="px-4 pt-3 pb-2 flex items-center justify-between border-b border-[color:var(--color-gold-shadow)]/40">
        <span className="font-mono text-[9px] uppercase tracking-[0.4em] text-[color:var(--color-gold-pale)]">
          Verdict
        </span>
        <div className="flex items-center gap-2">
          <ConfidenceDial level={confidence} />
          <LangToggle state={translation} />
        </div>
      </div>

      <div className="px-4 py-4">
        <div className="flex items-baseline gap-3 mb-3">
          <span
            className="foil font-display text-[34px] leading-none font-bold tracking-tight"
          >
            {theme.label}
          </span>
          {advice.to_amount_bb != null && (
            <span className="font-mono text-base tabular-nums text-[color:var(--color-gold-pale)]">
              <span className="opacity-50">to </span>
              {advice.to_amount_bb}
              <span className="opacity-50 ml-0.5">bb</span>
            </span>
          )}
        </div>

        <p className="text-[13px] leading-[1.6] text-[color:var(--color-bone-soft)]">
          {displayedReasoning}
        </p>

        {onFollow && (
          <button
            type="button"
            data-testid="follow-advice"
            onClick={onFollow}
            className="chip-button mt-5 w-full h-12 flex items-center justify-center gap-2 font-semibold tracking-tight"
            style={
              {
                "--chip-core":
                  "linear-gradient(180deg, #d8b876 0%, #b98a3c 100%)",
                color: "var(--color-ink)",
              } as React.CSSProperties
            }
          >
            <span className="text-[15px]">Follow</span>
            <span className="font-mono text-[11px] opacity-80 capitalize tabular-nums">
              {advice.action}
              {advice.to_amount_bb != null ? ` · ${advice.to_amount_bb}bb` : ""}
            </span>
          </button>
        )}
      </div>
    </div>
  );
}

function ConfidenceDial({ level }: { level: "high" | "medium" | "low" }) {
  const pct = level === "high" ? 100 : level === "medium" ? 66 : 33;
  const color =
    level === "high"
      ? "var(--color-jade)"
      : level === "medium"
        ? "var(--color-gold)"
        : "var(--color-parchment-dim)";
  return (
    <div className="flex items-center gap-1.5">
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
        <circle
          cx="9"
          cy="9"
          r="6.5"
          fill="none"
          stroke="rgba(237,227,204,0.12)"
          strokeWidth="2"
        />
        <circle
          cx="9"
          cy="9"
          r="6.5"
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeDasharray={`${(pct / 100) * 40.8} 40.8`}
          strokeLinecap="round"
          transform="rotate(-90 9 9)"
        />
      </svg>
      <span
        className="font-mono text-[9px] uppercase tracking-[0.2em]"
        style={{ color }}
      >
        {level}
      </span>
    </div>
  );
}
