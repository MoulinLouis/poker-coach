import { useState } from "react";
import { LiveCoach } from "./routes/LiveCoach";
import { SpotAnalysis } from "./routes/SpotAnalysis";

type Route = "live" | "spot";

export function App() {
  const [route, setRoute] = useState<Route>("live");
  return (
    <div style={{ fontFamily: "system-ui, sans-serif" }}>
      <nav
        style={{
          display: "flex",
          gap: 12,
          padding: "8px 16px",
          borderBottom: "1px solid #ddd",
        }}
      >
        <NavLink current={route} value="live" label="Live Coach" onSelect={setRoute} />
        <NavLink current={route} value="spot" label="Spot Analysis" onSelect={setRoute} />
      </nav>
      <div style={{ padding: 16 }}>
        {route === "live" ? <LiveCoach /> : <SpotAnalysis />}
      </div>
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
      style={{
        padding: "4px 8px",
        border: on ? "1px solid #333" : "1px solid transparent",
        background: on ? "#f0f0f0" : "transparent",
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}
