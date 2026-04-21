import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ActionBar } from "./ActionBar";
import type { GameState, LegalAction, Seat } from "../api/types";

function state(overrides: Partial<GameState> = {}): GameState {
  return {
    hand_id: "h",
    bb: 100,
    ante: 0,
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

// Mirrors backend/src/poker_coach/engine/rules.py:legal_actions when hero is
// SB facing a 1bb BB — call has NO min_to/max_to; its amount is derived from
// state.committed[opponent].
const raiseLegal: LegalAction[] = [
  { type: "fold" },
  { type: "call" },
  { type: "raise", min_to: 200, max_to: 10000 },
  { type: "allin", min_to: 10000, max_to: 10000 },
];

function renderHero(legal: LegalAction[] = raiseLegal, s: Partial<GameState> = {}) {
  const onAction = vi.fn();
  render(
    <ActionBar
      state={state(s)}
      legal={legal}
      actor={"hero" as Seat}
      onAction={onAction}
    />,
  );
  return { onAction };
}

describe("ActionBar — header", () => {
  it("shows 'Your turn' for hero", () => {
    renderHero();
    expect(screen.getByText(/your turn/i)).toBeInTheDocument();
  });

  it("shows 'Villain to act' + data-entry hint for villain", () => {
    const onAction = vi.fn();
    render(
      <ActionBar
        state={state({ to_act: "villain" })}
        legal={raiseLegal}
        actor="villain"
        onAction={onAction}
      />,
    );
    expect(screen.getByText(/villain to act/i)).toBeInTheDocument();
    expect(screen.getByText(/click what villain just did/i)).toBeInTheDocument();
  });
});

describe("ActionBar — sizing panel", () => {
  it("renders preset pills for preflop", () => {
    renderHero();
    for (const label of ["min", "2.5x", "3x", "3.5x", "max"]) {
      expect(screen.getByTestId(`preset-${label}`)).toBeInTheDocument();
    }
  });

  it("clicking a preset updates the amount readout", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("3.0");
  });

  it("slider change updates the amount readout", () => {
    renderHero();
    const slider = screen.getByTestId("size-slider") as HTMLInputElement;
    fireEvent.change(slider, { target: { value: "400" } });
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("4.0");
  });

  it("+ button nudges up by 1bb; - button nudges down by 1bb", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x")); // 3bb = 300 chips
    fireEvent.click(screen.getByTestId("size-plus"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("4.0");
    fireEvent.click(screen.getByTestId("size-minus"));
    expect(screen.getByTestId("size-readout-bb")).toHaveTextContent("3.0");
  });

  it("does not render a sizing panel when no raise/bet is legal", () => {
    renderHero([{ type: "fold" }, { type: "call", min_to: 100 }]);
    expect(screen.queryByTestId("size-slider")).not.toBeInTheDocument();
    expect(screen.queryByTestId("preset-min")).not.toBeInTheDocument();
  });
});

describe("ActionBar — action buttons", () => {
  it("fold fires action 'fold'", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("action-fold"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "fold",
      to_amount: null,
    });
  });

  it("call fires action 'call' with to_amount: null (backend derives from state)", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("action-call"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "call",
      to_amount: null,
    });
  });

  it("call button label shows the bb delta derived from state.committed", () => {
    // hero committed 50, villain committed 100, bb=100 → call delta = 50 chips = 0.5bb
    renderHero(raiseLegal, {
      committed: { hero: 50, villain: 100 },
      to_act: "hero",
    });
    expect(screen.getByTestId("action-call")).toHaveTextContent(/call.*0\.5.*bb/i);
  });

  it("raise fires action 'raise' with the current slider amount", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    fireEvent.click(screen.getByTestId("action-raise"));
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "raise",
      to_amount: 300,
    });
  });

  it("raise button label embeds the bet amount in bb", () => {
    renderHero();
    fireEvent.click(screen.getByTestId("preset-3x"));
    expect(screen.getByTestId("action-raise")).toHaveTextContent(/raise to.*3\.0.*bb/i);
  });

  it("clicking max preset turns the primary button into all-in and fires 'allin'", () => {
    const { onAction } = renderHero();
    fireEvent.click(screen.getByTestId("preset-max"));
    const primary = screen.getByTestId("action-raise");
    expect(primary).toHaveTextContent(/all[- ]?in/i);
    fireEvent.click(primary);
    expect(onAction).toHaveBeenCalledWith({
      actor: "hero",
      type: "allin",
      to_amount: 10000,
    });
  });

  it("defensively clamps a stale below-min size when re-rendered with new legal", () => {
    // Same ActionBar instance, new legal props (simulates LiveCoach NOT
    // remounting). The previous 3bb=300 sizeChips should be visually clamped
    // up to the new min_to=600, and firing dispatches the clamped amount so
    // the backend never sees an illegal raise.
    const onAction = vi.fn();
    const { rerender } = render(
      <ActionBar
        state={state()}
        legal={raiseLegal}
        actor="hero"
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId("preset-3x")); // sets sizeChips = 300
    const tighterLegal: LegalAction[] = [
      { type: "fold" },
      { type: "call" },
      { type: "raise", min_to: 600, max_to: 10000 },
      { type: "allin", min_to: 10000, max_to: 10000 },
    ];
    rerender(
      <ActionBar
        state={state()}
        legal={tighterLegal}
        actor="hero"
        onAction={onAction}
      />,
    );
    fireEvent.click(screen.getByTestId("action-raise"));
    expect(onAction).toHaveBeenLastCalledWith({
      actor: "hero",
      type: "raise",
      to_amount: 600,
    });
  });
});

describe("ActionBar — advise affordance", () => {
  it("shows advise button only when onRequestAdvice is provided", () => {
    const onAction = vi.fn();
    const onRequestAdvice = vi.fn();
    render(
      <ActionBar
        state={state()}
        legal={raiseLegal}
        actor="hero"
        onAction={onAction}
        onRequestAdvice={onRequestAdvice}
      />,
    );
    expect(screen.getByTestId("request-advice")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("request-advice"));
    expect(onRequestAdvice).toHaveBeenCalled();
  });

  it("hides advise button when onRequestAdvice is not provided (villain turn)", () => {
    const onAction = vi.fn();
    render(
      <ActionBar
        state={state({ to_act: "villain" })}
        legal={raiseLegal}
        actor="villain"
        onAction={onAction}
      />,
    );
    expect(screen.queryByTestId("request-advice")).not.toBeInTheDocument();
  });
});
