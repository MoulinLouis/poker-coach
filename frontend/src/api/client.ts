import type {
  Action,
  CostResponse,
  DecisionDetail,
  DecisionListRow,
  EngineSnapshot,
  GameState,
  Pack,
  PresetsResponse,
  PromptDetail,
  Seat,
  VillainProfile,
} from "./types";

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`POST ${path} failed (${res.status}): ${detail}`);
  }
  return (await res.json()) as T;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`GET ${path} failed (${res.status})`);
  return (await res.json()) as T;
}

export async function listPresets(): Promise<PresetsResponse> {
  return getJSON<PresetsResponse>("/api/presets");
}

export async function createSession(mode: "live" | "spot"): Promise<{ session_id: string }> {
  return postJSON("/api/sessions", { mode });
}

export async function createHand(input: {
  session_id: string;
  bb: number;
  ante?: number;
  effective_stack_start?: number;
  hero_stack_start?: number;
  villain_stack_start?: number;
  rng_seed?: number | null;
  deck_snapshot?: string[] | null;
}): Promise<{ hand_id: string }> {
  return postJSON("/api/hands", input);
}

export async function engineStart(input: {
  bb: number;
  ante?: number;
  button: Seat;
  effective_stack?: number;
  hero_stack?: number;
  villain_stack?: number;
  hero_hole?: [string, string] | null;
  villain_hole?: [string, string] | null;
  rng_seed?: number | null;
}): Promise<EngineSnapshot> {
  return postJSON("/api/engine/start", input);
}

export async function engineApply(state: GameState, action: Action): Promise<EngineSnapshot> {
  return postJSON("/api/engine/apply", { state, action });
}

export async function engineReveal(state: GameState, cards: string[]): Promise<EngineSnapshot> {
  return postJSON("/api/engine/reveal", { state, cards });
}

export async function createDecision(input: {
  session_id: string;
  hand_id?: string | null;
  model_preset: string;
  prompt_name: string;
  prompt_version: string;
  game_state: GameState;
  retry_of?: string | null;
  villain_profile?: VillainProfile;
}): Promise<{ decision_id: string }> {
  return postJSON("/api/decisions", input);
}

export async function recordAction(input: {
  decision_id: string;
  action: Action;
}): Promise<{ id: number }> {
  return postJSON("/api/actions", input);
}

export async function fetchCost(sessionId?: string | null): Promise<CostResponse> {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return getJSON<CostResponse>(`/api/cost${qs}`);
}

export async function listDecisions(params: {
  limit?: number;
  offset?: number;
  session_id?: string | null;
  model_id?: string | null;
  prompt_version?: string | null;
  status?: string | null;
}): Promise<DecisionListRow[]> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v != null && v !== "") qs.set(k, String(v));
  }
  const query = qs.toString();
  return getJSON<DecisionListRow[]>(`/api/decisions${query ? `?${query}` : ""}`);
}

export async function getDecisionDetail(decisionId: string): Promise<DecisionDetail> {
  return getJSON<DecisionDetail>(`/api/decisions/${decisionId}/detail`);
}

export async function listPacks(): Promise<Pack[]> {
  return getJSON<Pack[]>("/api/prompts");
}

export async function getPrompt(pack: string, version: string): Promise<PromptDetail> {
  return getJSON<PromptDetail>(`/api/prompts/${pack}/${version}`);
}

export async function savePrompt(
  pack: string,
  version: string,
  content: string,
): Promise<{ pack: string; version: string; path: string }> {
  return postJSON(`/api/prompts/${pack}`, { version, content });
}

export async function translateText(text: string): Promise<{
  translation: string;
  cost_usd: number;
}> {
  return postJSON("/api/translate", { text });
}
