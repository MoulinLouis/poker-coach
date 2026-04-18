// TypeScript mirror of the backend Pydantic models.
// Kept hand-written rather than generated: one-screen MVP surface,
// and the authoritative engine runs on the backend via /api/engine/*.

export type Seat = "hero" | "villain";

export type Street = "preflop" | "flop" | "turn" | "river" | "showdown" | "complete";

export type ActionType = "fold" | "check" | "call" | "bet" | "raise" | "allin";

export type Confidence = "low" | "medium" | "high";

export interface Action {
  actor: Seat;
  type: ActionType;
  to_amount?: number | null;
}

export interface LegalAction {
  type: ActionType;
  min_to?: number | null;
  max_to?: number | null;
}

export interface GameState {
  hand_id: string;
  bb: number;
  effective_stack: number;
  button: Seat;
  hero_hole: [string, string];
  villain_hole?: [string, string] | null;
  board: string[];
  street: Street;
  stacks: Record<Seat, number>;
  committed: Record<Seat, number>;
  pot: number;
  to_act: Seat | null;
  last_aggressor: Seat | null;
  last_raise_size: number;
  raises_open: boolean;
  acted_this_street: Seat[];
  history: Action[];
  rng_seed?: number | null;
  deck_snapshot?: string[] | null;
}

export interface EngineSnapshot {
  state: GameState;
  legal_actions: LegalAction[];
}

export interface Advice {
  action: ActionType;
  to_amount_bb?: number | null;
  reasoning: string;
  confidence: Confidence;
}

export interface PresetSummary {
  selector_id: string;
  provider: string;
  model_id: string;
  reasoning_effort: string | null;
  thinking_budget: number | null;
}

export interface PresetsResponse {
  default: string;
  presets: PresetSummary[];
}
