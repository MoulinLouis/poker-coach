import { useState } from "react";
import { CostFooter } from "./components/CostFooter";
import { History } from "./routes/History";
import { LiveCoach } from "./routes/LiveCoach";
import { Prompts } from "./routes/Prompts";
import { SpotAnalysis } from "./routes/SpotAnalysis";

type Route = "live" | "spot" | "history" | "prompts";

const ROUTES: { value: Route; label: string; no: string }[] = [
  { value: "live", label: "Live Coach", no: "I" },
  { value: "spot", label: "Spot Analysis", no: "II" },
  { value: "history", label: "History", no: "III" },
  { value: "prompts", label: "Prompts", no: "IV" },
];

export function App() {
  const [route, setRoute] = useState<Route>("live");
  return (
    <div className="min-h-screen pb-20 text-[color:var(--color-bone)] overflow-x-hidden">
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-[color:var(--color-ink)]/70 border-b border-[color:var(--color-gold-shadow)]/60">
        <div className="max-w-[1320px] mx-auto px-3 sm:px-6 pt-3 sm:pt-4 pb-2 sm:pb-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          <Brand />
          <nav className="order-3 sm:order-none w-full sm:w-auto flex items-end gap-0 sm:gap-1 overflow-x-auto">
            {ROUTES.map((r) => (
              <NavLink
                key={r.value}
                current={route}
                value={r.value}
                label={r.label}
                no={r.no}
                onSelect={setRoute}
              />
            ))}
          </nav>
          <div className="ml-auto hidden md:flex items-center gap-3 text-[10px] uppercase tracking-[0.28em] text-[color:var(--color-parchment-dim)]">
            <span>Heads-Up · No Limit</span>
            <span className="w-px h-3 bg-[color:var(--color-gold-shadow)]" />
            <span className="font-mono tabular-nums">v.0427</span>
          </div>
        </div>
        <div className="relative h-px">
          <div className="deco-rule absolute inset-x-3 sm:inset-x-6 top-0" />
        </div>
      </header>

      <main className="max-w-[1320px] mx-auto px-3 sm:px-6 py-4 sm:py-8">
        {route === "live" && <LiveCoach />}
        {route === "spot" && <SpotAnalysis />}
        {route === "history" && <History />}
        {route === "prompts" && <Prompts />}
      </main>
      <CostFooter sessionId={null} />
    </div>
  );
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
      <SpadeMark />
      <div className="flex flex-col -space-y-0.5 leading-none">
        <span className="text-[8px] sm:text-[9px] uppercase tracking-[0.3em] sm:tracking-[0.4em] text-[color:var(--color-parchment-dim)]">
          Maison du Coup
        </span>
        <span className="foil font-display text-xl sm:text-2xl font-semibold tracking-tight">
          Poker Coach
        </span>
      </div>
    </div>
  );
}

function SpadeMark() {
  return (
    <div className="relative h-10 w-10 shrink-0 rounded-full flex items-center justify-center foil-border bg-[color:var(--color-lacquer-raised)]">
      <svg
        viewBox="0 0 24 24"
        className="h-5 w-5"
        aria-hidden
        fill="url(#spade-foil)"
      >
        <defs>
          <linearGradient id="spade-foil" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--color-gold-bright)" />
            <stop offset="50%" stopColor="var(--color-gold)" />
            <stop offset="100%" stopColor="var(--color-gold-deep)" />
          </linearGradient>
        </defs>
        <path d="M12 2 C 12 2, 4 9, 4 14 C 4 17.3, 6.5 19, 9 19 C 10.4 19, 11.3 18.3, 11.6 17.7 C 11.4 19.3, 10.6 20.6, 9 21.5 L 15 21.5 C 13.4 20.6, 12.6 19.3, 12.4 17.7 C 12.7 18.3, 13.6 19, 15 19 C 17.5 19, 20 17.3, 20 14 C 20 9, 12 2, 12 2 Z" />
      </svg>
    </div>
  );
}

function NavLink({
  current,
  value,
  label,
  no,
  onSelect,
}: {
  current: Route;
  value: Route;
  label: string;
  no: string;
  onSelect: (r: Route) => void;
}) {
  const on = current === value;
  return (
    <button
      data-testid={`nav-${value}`}
      onClick={() => onSelect(value)}
      className={`group relative px-2.5 sm:px-3 pt-2 pb-2 flex items-baseline gap-1.5 shrink-0 transition ${
        on
          ? "text-[color:var(--color-bone)]"
          : "text-[color:var(--color-parchment-dim)] hover:text-[color:var(--color-bone-soft)]"
      }`}
    >
      <span className="hidden sm:inline font-mono text-[10px] tracking-widest opacity-60">
        {no}
      </span>
      <span className="font-display text-[13px] sm:text-[15px] tracking-tight whitespace-nowrap">
        {label}
      </span>
      <span
        className={`pointer-events-none absolute left-2 right-2 -bottom-[1px] h-[2px] origin-center transition-all duration-300 ${
          on
            ? "bg-gradient-to-r from-transparent via-[color:var(--color-gold)] to-transparent opacity-100 scale-x-100"
            : "bg-[color:var(--color-gold)] opacity-0 scale-x-0 group-hover:opacity-40 group-hover:scale-x-75"
        }`}
      />
    </button>
  );
}
