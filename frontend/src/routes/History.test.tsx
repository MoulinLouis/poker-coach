import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import type { DecisionDetail, DecisionListRow } from "../api/types";
import { LocaleProvider } from "../i18n/LocaleContext";
import { History } from "./History";

function renderWithProviders(ui: React.ReactElement) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

function makeRow(overrides: Partial<DecisionListRow>): DecisionListRow {
  return {
    decision_id: "d1",
    created_at: "2026-04-22T10:00:00Z",
    session_id: "s1",
    hand_id: null,
    model_id: "claude-opus-4-7",
    prompt_name: "coach",
    prompt_version: "v3",
    villain_profile: "reg",
    status: "complete",
    parsed_advice: null,
    cost_usd: 0.01,
    latency_ms: 1000,
    ...overrides,
  };
}

function makeDetail(row: DecisionListRow): DecisionDetail {
  return {
    ...row,
    game_state: {} as DecisionDetail["game_state"],
    template_hash: "hash",
    template_raw: "",
    rendered_prompt: "",
    system_prompt_hash: null,
    reasoning_text: null,
    raw_tool_input: null,
    reasoning_effort: null,
    thinking_budget: null,
    temperature: null,
    input_tokens: null,
    output_tokens: null,
    reasoning_tokens: null,
    total_tokens: null,
    pricing_snapshot: null,
    error_message: null,
    retry_of: null,
  };
}

describe("History route — v2 vs v3 strategy rendering", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders StrategyBars for a v3 decision with a strategy distribution", async () => {
    const row = makeRow({
      decision_id: "d1",
      prompt_version: "v3",
      parsed_advice: {
        action: "bet",
        to_amount_bb: 3.0,
        reasoning: "mix",
        confidence: "medium",
        strategy: [
          { action: "bet", to_amount_bb: 3.0, frequency: 0.65 },
          { action: "check", to_amount_bb: null, frequency: 0.35 },
        ],
      },
    });
    vi.spyOn(client, "listDecisions").mockResolvedValue([row]);
    vi.spyOn(client, "getDecisionDetail").mockResolvedValue(makeDetail(row));

    renderWithProviders(<History />);

    // Open detail panel by clicking the row.
    const rowEl = await screen.findByTestId("history-row-d1");
    fireEvent.click(rowEl);

    const bars = await screen.findAllByTestId(/^strategy-row-/);
    expect(bars.length).toBe(2);
  });

  it("does NOT render StrategyBars for a v2 decision with no strategy field", async () => {
    const row = makeRow({
      decision_id: "d2",
      prompt_version: "v2",
      parsed_advice: {
        action: "fold",
        to_amount_bb: null,
        reasoning: "bad spot",
        confidence: "high",
        // no `strategy` on v2
      },
    });
    vi.spyOn(client, "listDecisions").mockResolvedValue([row]);
    vi.spyOn(client, "getDecisionDetail").mockResolvedValue(makeDetail(row));

    renderWithProviders(<History />);

    const rowEl = await screen.findByTestId("history-row-d2");
    fireEvent.click(rowEl);

    // Wait for the detail panel to render the advice text, then assert no bars.
    await waitFor(() => {
      expect(screen.getAllByText(/fold/i).length).toBeGreaterThan(0);
    });
    expect(screen.queryAllByTestId(/^strategy-row-/)).toHaveLength(0);
    expect(screen.queryByTestId("strategy-bars")).toBeNull();
  });
});
