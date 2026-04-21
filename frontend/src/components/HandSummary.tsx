import type { GameState } from "../api/types";
import { useLocale } from "../i18n";

export function HandSummary({
  state,
  agreement,
  onNewHand,
}: {
  state: GameState;
  agreement: { total: number; diverged: number };
  onNewHand: () => void;
}) {
  const { t } = useLocale();
  const rate =
    agreement.total === 0
      ? null
      : Math.round(((agreement.total - agreement.diverged) / agreement.total) * 100);

  const rateColor =
    rate == null
      ? "var(--color-parchment)"
      : rate >= 80
        ? "var(--color-jade)"
        : rate >= 50
          ? "var(--color-gold-bright)"
          : "var(--color-coral)";

  return (
    <div
      data-testid="hand-summary"
      className="anim-fade-up relative rounded-2xl p-6 flex items-center justify-between gap-4 overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, rgba(29,23,24,0.9), rgba(14,10,11,0.95))",
        border: "1px solid rgba(201,162,94,0.35)",
        boxShadow:
          "0 20px 60px -30px rgba(0,0,0,0.9), inset 0 1px 0 rgba(201,162,94,0.18)",
      }}
    >
      <div className="flex flex-col gap-2">
        <span className="font-mono text-[9px] tracking-[0.4em] uppercase text-[color:var(--color-parchment-dim)]">
          {t("handSummary.handLabel")} · {state.hand_id.slice(0, 8)} · {t("handSummary.closed")}
        </span>
        {rate != null ? (
          <div className="flex items-baseline gap-3">
            <span className="text-sm text-[color:var(--color-parchment)]">
              {t("handSummary.agreement")}
            </span>
            <span
              className="text-[2rem] font-bold tabular-nums tracking-tight"
              style={{ color: rateColor }}
            >
              {rate}%
            </span>
            <span className="font-mono text-[10px] tabular-nums text-[color:var(--color-parchment-dim)]">
              ({agreement.total - agreement.diverged}/{agreement.total})
            </span>
          </div>
        ) : (
          <span className="text-sm text-[color:var(--color-parchment)]">
            {t("handSummary.noAdvice")}
          </span>
        )}
      </div>
      <button
        onClick={onNewHand}
        className="chip-button h-12 px-5 flex items-center gap-3"
        style={
          {
            "--chip-core":
              "linear-gradient(180deg, #e6c584 0%, #a07a2e 100%)",
            color: "var(--color-ink)",
          } as React.CSSProperties
        }
      >
        <kbd className="font-mono text-[9px] tracking-widest px-1.5 py-0.5 rounded border border-[color:var(--color-ink)]/30 bg-black/15">
          N
        </kbd>
        <span className="font-semibold text-sm tracking-tight">
          {t("handSummary.nextHand")}
        </span>
      </button>
    </div>
  );
}
