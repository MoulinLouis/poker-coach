import type { ActionType, GameState, LegalAction } from "../../api/types";

export interface Preset {
  label: string;
  toChips: number;
  kind: "min" | "ratio" | "max";
}

export type SizeableType = "bet" | "raise";

export interface LegalByType {
  fold?: LegalAction;
  check?: LegalAction;
  call?: LegalAction;
  bet?: LegalAction;
  raise?: LegalAction;
  allin?: LegalAction;
}

export function legalByType(legal: LegalAction[]): LegalByType {
  return Object.fromEntries(legal.map((l) => [l.type, l])) as LegalByType;
}

export function sizeableType(lbt: LegalByType): SizeableType | null {
  if (lbt.raise) return "raise";
  if (lbt.bet) return "bet";
  return null;
}

export function clampChips(chips: number, la: LegalAction): number {
  if (la.min_to == null || la.max_to == null) return chips;
  if (chips < la.min_to) return la.min_to;
  if (chips > la.max_to) return la.max_to;
  return Math.round(chips);
}

export function bbToChips(bb: number, state: GameState): number {
  return Math.round(bb * state.bb);
}

export function chipsToBb(chips: number, state: GameState): number {
  return chips / state.bb;
}

// Snap-to-chip presets for the given street. All returned presets are clamped
// into [min_to, max_to]; any that would collapse onto min (other than `min`
// itself) are deduped.
export function getPresets(state: GameState, la: LegalAction): Preset[] {
  if (la.min_to == null || la.max_to == null) return [];
  const min = la.min_to;
  const max = la.max_to;
  const raw: Preset[] =
    state.street === "preflop"
      ? [
          { label: "min", toChips: min, kind: "min" },
          { label: "2.5x", toChips: bbToChips(2.5, state), kind: "ratio" },
          { label: "3x", toChips: bbToChips(3, state), kind: "ratio" },
          { label: "3.5x", toChips: bbToChips(3.5, state), kind: "ratio" },
        ]
      : postflopRaw(state, la);
  const filtered = raw
    .map((p) => ({ ...p, toChips: clampChips(p.toChips, la) }))
    .filter((p, i, arr) =>
      p.kind === "min" ? true : arr.findIndex((q) => q.toChips === p.toChips) === i,
    );
  return [...filtered, { label: "max", toChips: max, kind: "max" }];
}

function postflopRaw(state: GameState, la: LegalAction): Preset[] {
  const pot = state.pot + state.committed.hero + state.committed.villain;
  const actorCommitted =
    state.to_act === "hero" ? state.committed.hero : state.committed.villain;
  const min = la.min_to!;
  return [
    { label: "min", toChips: min, kind: "min" },
    { label: "33%", toChips: actorCommitted + Math.round(pot * 0.33), kind: "ratio" },
    { label: "50%", toChips: actorCommitted + Math.round(pot * 0.5), kind: "ratio" },
    { label: "75%", toChips: actorCommitted + Math.round(pot * 0.75), kind: "ratio" },
    { label: "pot", toChips: actorCommitted + pot, kind: "ratio" },
    { label: "1.5x", toChips: actorCommitted + Math.round(pot * 1.5), kind: "ratio" },
  ];
}

// Resolves the ActionType + to_amount to dispatch when the user confirms the
// sizing. If the sizing hits the max AND `allin` is legal, prefer `allin`.
// Defensive clamp: even if the caller's `sizeChips` is stale and below min_to
// (e.g. because the legal min changed between renders), the dispatched amount
// is clamped into [min_to, max_to] so the backend never sees an IllegalAction.
export function resolveFireType(
  sizeChips: number,
  lbt: LegalByType,
): { type: ActionType; to: number } | null {
  const s = sizeableType(lbt);
  if (!s) return null;
  const la = lbt[s]!;
  if (la.max_to == null || la.min_to == null) return null;
  const clamped = clampChips(sizeChips, la);
  if (clamped >= la.max_to && lbt.allin?.max_to != null) {
    return { type: "allin", to: lbt.allin.max_to };
  }
  return { type: s, to: clamped };
}

export function potForDisplay(state: GameState): number {
  return state.pot + state.committed.hero + state.committed.villain;
}

// Pot-ratio % for the amount the actor would *add* beyond what's already
// committed. Returns null preflop (ratio framing is not useful preflop).
export function sizingPotPct(
  sizeChips: number,
  state: GameState,
): number | null {
  if (state.street === "preflop") return null;
  const pot = potForDisplay(state);
  if (pot === 0) return null;
  const actorCommitted =
    state.to_act === "hero" ? state.committed.hero : state.committed.villain;
  const delta = sizeChips - actorCommitted;
  return (delta / pot) * 100;
}
