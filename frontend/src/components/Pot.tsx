import { useLocale } from "../i18n";

export function Pot({ potBb }: { potBb: number }) {
  const { t } = useLocale();
  return (
    <div
      data-testid="pot"
      className="relative flex items-center gap-3 pl-2 pr-5 py-1.5 rounded-full"
      style={{
        background:
          "linear-gradient(180deg, rgba(10,7,6,0.85), rgba(10,7,6,0.65))",
        boxShadow:
          "inset 0 1px 0 rgba(201,162,94,0.3), 0 6px 18px -8px rgba(0,0,0,0.9)",
        border: "1px solid rgba(201,162,94,0.35)",
      }}
    >
      <ChipStack />
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl tabular-nums font-bold text-[color:var(--color-bone)] tracking-tight">
          {potBb.toFixed(1)}
        </span>
        <span className="font-mono text-[10px] tracking-widest uppercase text-[color:var(--color-parchment-dim)]">
          {t("pot.bbUnit")}
        </span>
      </div>
      <span className="pl-2 border-l border-[color:var(--color-gold-shadow)]/60 text-[9px] uppercase tracking-[0.4em] text-[color:var(--color-parchment-dim)]">
        {t("pot.label")}
      </span>
    </div>
  );
}

function ChipStack() {
  return (
    <svg width="30" height="30" viewBox="0 0 30 30" aria-hidden className="shrink-0">
      <defs>
        <linearGradient id="chip-gold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--color-gold-bright)" />
          <stop offset="50%" stopColor="var(--color-gold)" />
          <stop offset="100%" stopColor="var(--color-gold-deep)" />
        </linearGradient>
      </defs>
      {/* 3 stacked chips */}
      <ellipse cx="15" cy="22" rx="11" ry="3" fill="url(#chip-gold)" />
      <rect x="4" y="18" width="22" height="4" fill="var(--color-gold-deep)" />
      <ellipse cx="15" cy="18" rx="11" ry="3" fill="url(#chip-gold)" />
      <rect x="4" y="14" width="22" height="4" fill="var(--color-gold-deep)" />
      <ellipse cx="15" cy="14" rx="11" ry="3" fill="url(#chip-gold)" />
      {/* top face detail */}
      <circle cx="15" cy="14" r="6" fill="none" stroke="var(--color-gold-shadow)" strokeWidth="0.8" />
      <circle cx="15" cy="14" r="2.2" fill="var(--color-oxblood-deep)" />
    </svg>
  );
}
