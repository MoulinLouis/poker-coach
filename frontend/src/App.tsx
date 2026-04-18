import { useState } from "react";
import { LiveCoach } from "./routes/LiveCoach";
import { SpotAnalysis } from "./routes/SpotAnalysis";

type Route = "live" | "spot";

export function App() {
  const [route, setRoute] = useState<Route>("live");
  return (
    <div className="min-h-screen bg-stone-950 text-stone-100 font-sans">
      <nav className="flex items-center gap-2 px-6 py-3 border-b border-stone-800 bg-stone-900/60 backdrop-blur">
        <span className="font-semibold tracking-tight mr-3">Poker HU Coach</span>
        <NavLink current={route} value="live" label="Live Coach" onSelect={setRoute} />
        <NavLink current={route} value="spot" label="Spot Analysis" onSelect={setRoute} />
      </nav>
      <main className="px-6 py-6">
        {route === "live" ? <LiveCoach /> : <SpotAnalysis />}
      </main>
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
