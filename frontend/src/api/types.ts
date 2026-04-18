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
  pending_reveal: "flop" | "turn" | "river" | "runout" | null;
  reveals: string[][];
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

export interface CostBreakdownRow {
  model_id: string;
  reasoning_effort: string;
  decision_count: number;
  cost_usd: number;
}

export interface CostResponse {
  session_usd: number;
  all_time_usd: number;
  by_model: CostBreakdownRow[];
}

export interface DecisionListRow {
  decision_id: string;
  created_at: string;
  session_id: string;
  hand_id: string | null;
  model_id: string;
  prompt_name: string;
  prompt_version: string;
  status: string;
  parsed_advice: Advice | null;
  cost_usd: number | null;
  latency_ms: number | null;
}

export interface DecisionDetail extends DecisionListRow {
  game_state: GameState;
  template_hash: string;
  template_raw: string;
  rendered_prompt: string;
  reasoning_text: string | null;
  raw_tool_input: Record<string, unknown> | null;
  reasoning_effort: string | null;
  thinking_budget: number | null;
  temperature: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  total_tokens: number | null;
  pricing_snapshot: Record<string, unknown> | null;
  error_message: string | null;
  retry_of: string | null;
}

export interface PackVersion {
  version: string;
  description: string | null;
}

export interface Pack {
  name: string;
  versions: PackVersion[];
}

export interface PromptDetail {
  pack: string;
  version: string;
  description: string | null;
  declared_variables: string[];
  template_raw: string;
  template_hash: string;
}
