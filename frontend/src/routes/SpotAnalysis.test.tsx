import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { SpotAnalysis } from "./SpotAnalysis";

const MOCK_PRESETS = [
  { selector_id: "preset-a", provider: "openai", model_id: "m1", reasoning_effort: null, thinking_budget: null },
  { selector_id: "preset-b", provider: "openai", model_id: "m2", reasoning_effort: null, thinking_budget: null },
  { selector_id: "preset-c", provider: "openai", model_id: "m3", reasoning_effort: null, thinking_budget: null },
];

beforeEach(() => {
  vi.spyOn(client, "listPresets").mockResolvedValue({
    presets: MOCK_PRESETS,
    default: "preset-a",
  });
  vi.spyOn(client, "createSession").mockResolvedValue({ session_id: "s1" });
  vi.spyOn(client, "engineStart").mockResolvedValue({
    state: {
      hand_id: "h1",
      street: "preflop",
      to_act: "hero",
      pot: 150,
      bb: 100,
      ante: 0,
      stacks: { hero: 9850, villain: 9850 },
      committed: { hero: 50, villain: 100 },
      hero_hole: ["As", "Kd"],
      villain_hole: null,
      board: [],
      acted_this_street: [],
      pending_reveal: null,
      effective_stack: 10000,
      button: "hero",
      last_aggressor: null,
      last_raise_size: 0,
      raises_open: true,
      history: [],
      reveals: [],
    },
    legal_actions: [],
  });
});

describe("SpotAnalysis — hook stability", () => {
  it("renders without hook-count errors across preset toggles", async () => {
    render(<SpotAnalysis />);

    // Wait for presets to load
    await waitFor(() => screen.getByText("preset-a"));

    // Verify all three preset buttons are present
    expect(screen.getByText("preset-a")).toBeInTheDocument();
    expect(screen.getByText("preset-b")).toBeInTheDocument();
    expect(screen.getByText("preset-c")).toBeInTheDocument();

    // Toggle preset-b on (2 selected)
    fireEvent.click(screen.getByText("preset-b"));
    // Toggle preset-c on (3 selected — max)
    fireEvent.click(screen.getByText("preset-c"));
    // Toggle preset-b off (back to 2)
    fireEvent.click(screen.getByText("preset-b"));
    // Toggle preset-a off (1 selected)
    fireEvent.click(screen.getByText("preset-a"));

    // If hook count changed, React would have thrown by now
    expect(screen.getByTestId("spot-start")).toBeInTheDocument();
  });
});
