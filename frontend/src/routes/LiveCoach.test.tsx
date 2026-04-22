import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "../api/client";
import { LocaleProvider } from "../i18n/LocaleContext";
import { LiveCoach } from "./LiveCoach";

vi.mock("@microsoft/fetch-event-source", () => ({
  fetchEventSource: vi.fn(),
}));

const MOCK_PRESETS = [
  {
    selector_id: "preset-a",
    provider: "openai",
    model_id: "m1",
    reasoning_effort: null,
    thinking_budget: null,
  },
];

function renderWithProviders(ui: React.ReactElement) {
  return render(<LocaleProvider>{ui}</LocaleProvider>);
}

describe("LiveCoach — decision request shape", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(client, "listPresets").mockResolvedValue({
      presets: MOCK_PRESETS,
      default: "preset-a",
    });
    vi.spyOn(client, "createSession").mockResolvedValue({ session_id: "sess-1" });
    vi.spyOn(client, "createHand").mockResolvedValue({ hand_id: "hand-1" });
    vi.spyOn(client, "engineStart").mockResolvedValue({
      state: {
        hand_id: "hand-1",
        street: "preflop",
        to_act: "hero",
        pot: 150,
        bb: 100,
        ante: 0,
        stacks: { hero: 9_950, villain: 9_900 },
        committed: { hero: 50, villain: 100 },
        hero_hole: ["As", "Kd"],
        villain_hole: ["Qc", "Qh"],
        board: [],
        acted_this_street: [],
        pending_reveal: null,
        effective_stack: 10_000,
        hero_stack_start: 10_000,
        villain_stack_start: 10_000,
        button: "hero",
        last_aggressor: "villain",
        last_raise_size: 100,
        raises_open: true,
        history: [],
        reveals: [],
      },
      legal_actions: [
        { type: "fold", min_to: null, max_to: null },
        { type: "call", min_to: null, max_to: null },
        { type: "raise", min_to: 200, max_to: 9_950 },
      ],
    });
  });

  it("POSTs prompt_version=v3 by default when requesting advice", async () => {
    const createDecisionSpy = vi
      .spyOn(client, "createDecision")
      .mockResolvedValue({ decision_id: "dec-1" });

    renderWithProviders(<LiveCoach />);

    // Wait for presets to load, then click "New Hand" to build a snapshot.
    await waitFor(() => expect(client.listPresets).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("new-hand"));

    // Wait for the engine snapshot to arrive and the ActionBar to render.
    const adviceButton = await screen.findByTestId("request-advice");
    fireEvent.click(adviceButton);

    await waitFor(() => {
      expect(createDecisionSpy).toHaveBeenCalled();
    });
    const payload = createDecisionSpy.mock.calls[0][0];
    expect(payload.prompt_version).toBe("v3");
    expect(payload.prompt_name).toBe("coach");
  });
});
