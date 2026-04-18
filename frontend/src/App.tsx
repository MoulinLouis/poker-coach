import { useState } from "react";
import { CostFooter } from "./components/CostFooter";
import { History } from "./routes/History";
import { LiveCoach } from "./routes/LiveCoach";
import { Prompts } from "./routes/Prompts";
import { SpotAnalysis } from "./routes/SpotAnalysis";

type Route = "live" | "spot" | "history" | "prompts";

const ROUTES: { value: Route; label: string }[] = [
  { value: "live", label: "Live Coach" },
  { value: "spot", label: "Spot Analysis" },
  { value: "history", label: "History" },
  { value: "prompts", label: "Prompts" },
];

export function App() {
  const [route, setRoute] = useState<Route>("live");
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 font-sans pb-10">
      <nav className="flex items-center gap-2 px-6 py-3 border-b border-stone-800 bg-stone-900/60 backdrop-blur sticky top-0 z-10">
        <span className="font-semibold tracking-tight mr-3">Poker HU Coach</span>
        {ROUTES.map((r) => (
          <NavLink
            key={r.value}
            current={route}
            value={r.value}
            label={r.label}
            onSelect={setRoute}
          />
        ))}
      </nav>
      <main className="px-6 py-6">
        {route === "live" && <LiveCoach />}
        {route === "spot" && <SpotAnalysis />}
        {route === "history" && <History />}
        {route === "prompts" && <Prompts />}
      </main>
      <CostFooter sessionId={null} />
    </div>
  );
}

function NavLink({
  current,
  value,
  label,
  onSelect,
}: {
  current: Route;
  value: Route;
  label: string;
  onSelect: (r: Route) => void;
}) {
  const on = current === value;
  return (
    <button
      data-testid={`nav-${value}`}
      onClick={() => onSelect(value)}
      className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
        on ? "bg-stone-800 text-white" : "text-stone-400 hover:text-stone-200"
      }`}
    >
      {label}
    </button>
  );
}
