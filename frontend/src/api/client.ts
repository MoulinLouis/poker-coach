import type {
  Action,
  EngineSnapshot,
  GameState,
  PresetsResponse,
  Seat,
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
  effective_stack_start: number;
  rng_seed?: number | null;
  deck_snapshot?: string[] | null;
}): Promise<{ hand_id: string }> {
  return postJSON("/api/hands", input);
}

export async function engineStart(input: {
  effective_stack: number;
  bb: number;
  button: Seat;
  hero_hole?: [string, string] | null;
  villain_hole?: [string, string] | null;
  rng_seed?: number | null;
}): Promise<EngineSnapshot> {
  return postJSON("/api/engine/start", input);
}

export async function engineApply(state: GameState, action: Action): Promise<EngineSnapshot> {
  return postJSON("/api/engine/apply", { state, action });
}

export async function createDecision(input: {
  session_id: string;
  hand_id?: string | null;
  model_preset: string;
  prompt_name: string;
  prompt_version: string;
  game_state: GameState;
  retry_of?: string | null;
}): Promise<{ decision_id: string }> {
  return postJSON("/api/decisions", input);
}

export async function recordAction(input: {
  decision_id: string;
  action: Action;
}): Promise<{ id: number }> {
  return postJSON("/api/actions", input);
}
