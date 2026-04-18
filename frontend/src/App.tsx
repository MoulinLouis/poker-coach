import { useQuery } from "@tanstack/react-query";

type Health = { status: string };

async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(`health check failed: ${res.status}`);
  return (await res.json()) as Health;
}

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: fetchHealth });

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: 24 }}>
      <h1>Poker HU LLM Coach</h1>
      <p>Phase 0 scaffold. Nav shell placeholder.</p>
      <nav style={{ display: "flex", gap: 12 }}>
        <span>Live Coach</span>
        <span>Spot Analysis</span>
        <span>History</span>
        <span>Prompts</span>
        <span>Settings</span>
      </nav>
      <section style={{ marginTop: 24 }}>
        <h2>Backend health</h2>
        {health.isPending && <p>checking…</p>}
        {health.isError && <p>error: {String(health.error)}</p>}
        {health.data && <p>status: {health.data.status}</p>}
      </section>
    </main>
  );
}
