import { describe, expect, it } from "vitest";
import {
  clampChips,
  getPresets,
  legalByType,
  resolveFireType,
  sizingPotPct,
} from "./sizing";
import type { GameState, LegalAction } from "../../api/types";

function baseState(overrides: Partial<GameState> = {}): GameState {
  return {
    hand_id: "h",
    bb: 100,
    effective_stack: 10000,
    button: "hero",
    hero_hole: ["As", "Kd"],
    villain_hole: null,
    board: [],
    street: "preflop",
    stacks: { hero: 10000, villain: 10000 },
    committed: { hero: 50, villain: 100 },
    pot: 0,
    to_act: "hero",
    last_aggressor: "villain",
    last_raise_size: 100,
    raises_open: true,
    acted_this_street: [],
    history: [],
    rng_seed: null,
    deck_snapshot: null,
    pending_reveal: null,
    reveals: [],
    ...overrides,
  };
}

describe("clampChips", () => {
  it("clamps below min up to min", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(50, la)).toBe(200);
  });

  it("clamps above max down to max", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(20000, la)).toBe(10000);
  });

  it("rounds to integer chips", () => {
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    expect(clampChips(250.6, la)).toBe(251);
  });
});

describe("getPresets preflop", () => {
  it("produces min, ratios, and max", () => {
    const state = baseState();
    const la: LegalAction = { type: "raise", min_to: 200, max_to: 10000 };
    const presets = getPresets(state, la);
    expect(presets.map((p) => p.label)).toEqual(["min", "2.5x", "3x", "3.5x", "max"]);
    expect(presets[0].toChips).toBe(200);
    expect(presets[1].toChips).toBe(250);
    expect(presets[2].toChips).toBe(300);
    expect(presets[3].toChips).toBe(350);
    expect(presets.at(-1)!.toChips).toBe(10000);
  });

  it("clamps ratio presets that fall below min to the min value (dedup removes them)", () => {
    const state = baseState();
    // min_to=400 wipes out 2.5x=250 and 3x=300 and 3.5x=350 — they all clamp
    // to 400 which matches `min`, so they dedup away.
    const la: LegalAction = { type: "raise", min_to: 400, max_to: 10000 };
    const labels = getPresets(state, la).map((p) => p.label);
    expect(labels).toEqual(["min", "max"]);
  });
});

describe("getPresets postflop", () => {
  it("computes ratios off pot + committed", () => {
    const state = baseState({
      street: "flop",
      pot: 600,
      committed: { hero: 0, villain: 0 },
      to_act: "hero",
    });
    const la: LegalAction = { type: "bet", min_to: 100, max_to: 10000 };
    const presets = getPresets(state, la);
    expect(presets.map((p) => p.label)).toEqual([
      "min", "33%", "50%", "75%", "pot", "1.5x", "max",
    ]);
    expect(presets.find((p) => p.label === "pot")!.toChips).toBe(600);
    expect(presets.find((p) => p.label === "75%")!.toChips).toBe(450);
  });
});

describe("resolveFireType", () => {
  it("returns raise when not at max", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(300, lbt)).toEqual({ type: "raise", to: 300 });
  });

  it("returns allin when sizing is at or above max and allin is legal", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(10000, lbt)).toEqual({ type: "allin", to: 10000 });
  });

  it("returns bet when only bet is legal", () => {
    const lbt = legalByType([{ type: "bet", min_to: 100, max_to: 10000 }]);
    expect(resolveFireType(500, lbt)).toEqual({ type: "bet", to: 500 });
  });

  it("returns null when nothing is sizeable", () => {
    // call and fold carry no min_to/max_to — the call amount is derived from state.
    const lbt = legalByType([{ type: "fold" }, { type: "call" }]);
    expect(resolveFireType(500, lbt)).toBeNull();
  });

  it("clamps a below-min stale size up to min_to before dispatching", () => {
    // Guards against sizeChips bleeding across spot transitions (e.g. hero
    // opens 3bb, new min raise for the next spot is 5bb, and the stale 3bb
    // would otherwise crash the backend with IllegalAction).
    const lbt = legalByType([
      { type: "raise", min_to: 500, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(300, lbt)).toEqual({ type: "raise", to: 500 });
  });

  it("clamps an above-max size down to max_to and routes to allin", () => {
    const lbt = legalByType([
      { type: "raise", min_to: 200, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ]);
    expect(resolveFireType(99999, lbt)).toEqual({ type: "allin", to: 10000 });
  });
});

describe("sizingPotPct", () => {
  it("returns null preflop", () => {
    expect(sizingPotPct(500, baseState())).toBeNull();
  });

  it("computes pct of pot for the delta", () => {
    const state = baseState({
      street: "flop",
      pot: 600,
      committed: { hero: 0, villain: 0 },
      to_act: "hero",
    });
    expect(sizingPotPct(300, state)).toBe(50);
  });
});
