import type { StrategyEntry } from "../api/types";
import { useLocale } from "../i18n";
import type { DictKey } from "../i18n";

const ACTION_LABEL_KEY: Record<StrategyEntry["action"], DictKey> = {
  fold: "advice.action.fold",
  check: "advice.action.check",
  call: "advice.action.call",
  bet: "advice.action.bet",
  raise: "advice.action.raise",
  allin: "advice.action.allin",
};

const ACTION_COLOR: Record<StrategyEntry["action"], string> = {
  fold: "var(--color-parchment)",
  check: "var(--color-jade)",
  call: "var(--color-jade)",
  bet: "var(--color-gold-bright)",
  raise: "var(--color-gold-bright)",
  allin: "var(--color-coral)",
};

export function StrategyBars({ strategy }: { strategy: StrategyEntry[] }) {
  const { t } = useLocale();
  if (strategy.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5" data-testid="strategy-bars">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
          {t("advice.strategy.header")}
        </span>
        <span className="font-mono text-[8px] text-[color:var(--color-parchment-dim)] opacity-70">
          {t("advice.strategy.argmaxHint")}
        </span>
      </div>
      {strategy.map((entry, i) => {
        const isArgmax = i === 0;
        const color = ACTION_COLOR[entry.action];
        const label = `${t(ACTION_LABEL_KEY[entry.action])}${
          entry.to_amount_bb != null ? ` ${entry.to_amount_bb}bb` : ""
        }`;
        const pct = `${Math.round(entry.frequency * 100)}%`;
        return (
          <div
            key={`${entry.action}-${entry.to_amount_bb ?? "na"}-${i}`}
            data-testid={`strategy-row-${i}`}
            data-argmax={isArgmax ? "true" : "false"}
            className="relative flex items-center gap-2 text-[11px] font-mono tabular-nums"
            style={{
              padding: "2px 6px",
              borderRadius: 3,
              border: isArgmax ? `1px solid ${color}` : "1px solid rgba(201,162,94,0.12)",
              boxShadow: isArgmax ? `0 0 8px -2px ${color}` : "none",
            }}
          >
            <span
              data-testid="strategy-label"
              className="relative z-10 min-w-[70px]"
              style={{ color }}
            >
              {label}
            </span>
            <div className="relative flex-1 h-2 rounded-sm overflow-hidden bg-[rgba(10,7,6,0.5)]">
              <div
                data-testid="strategy-bar-fill"
                className="h-full"
                style={{
                  width: pct,
                  background: color,
                  opacity: isArgmax ? 0.9 : 0.45,
                }}
              />
            </div>
            <span className="relative z-10 text-[color:var(--color-parchment)] min-w-[32px] text-right">
              {pct}
            </span>
          </div>
        );
      })}
    </div>
  );
}
