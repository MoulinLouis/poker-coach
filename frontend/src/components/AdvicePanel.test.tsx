import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AdvicePanel } from "./AdvicePanel";
import type { StreamState } from "../api/useAdviceStream";
import type { Advice } from "../api/types";

function streamWithAdvice(advice: Advice): StreamState {
  return {
    status: "done",
    reasoning: "Short reasoning.",
    advice,
    costUsd: 0.001,
    errorMessage: null,
    terminalStatus: "ok",
  };
}

const raiseAdvice: Advice = {
  action: "raise",
  to_amount_bb: 7.5,
  reasoning: "Value raise with top pair.",
  confidence: "high",
};

describe("AdvicePanel — follow button", () => {
  it("renders when onFollow is provided and advice is present", () => {
    render(
      <AdvicePanel
        stream={streamWithAdvice(raiseAdvice)}
        diverged={false}
        presetLabel="test"
        onFollow={() => undefined}
      />,
    );
    const btn = screen.getByTestId("follow-advice");
    expect(btn).toBeInTheDocument();
    expect(btn.textContent).toContain("Follow");
    expect(btn.textContent).toContain("raise");
    expect(btn.textContent).toContain("7.5bb");
  });

  it("calls onFollow when clicked", () => {
    const onFollow = vi.fn();
    render(
      <AdvicePanel
        stream={streamWithAdvice(raiseAdvice)}
        diverged={false}
        presetLabel="test"
        onFollow={onFollow}
      />,
    );
    fireEvent.click(screen.getByTestId("follow-advice"));
    expect(onFollow).toHaveBeenCalledTimes(1);
  });

  it("is not rendered when onFollow is omitted (e.g. not hero's turn)", () => {
    render(
      <AdvicePanel
        stream={streamWithAdvice(raiseAdvice)}
        diverged={false}
        presetLabel="test"
      />,
    );
    expect(screen.queryByTestId("follow-advice")).toBeNull();
  });

  it("omits sizing suffix for fold/check/call", () => {
    const foldAdvice: Advice = {
      action: "fold",
      reasoning: "Too weak to continue.",
      confidence: "medium",
    };
    render(
      <AdvicePanel
        stream={streamWithAdvice(foldAdvice)}
        diverged={false}
        presetLabel="test"
        onFollow={() => undefined}
      />,
    );
    const btn = screen.getByTestId("follow-advice");
    expect(btn.textContent).toContain("fold");
    expect(btn.textContent).not.toContain("bb");
  });
});
