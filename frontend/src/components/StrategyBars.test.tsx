import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { StrategyEntry } from "../api/types";
import { StrategyBars } from "./StrategyBars";

describe("StrategyBars", () => {
  const strategy: StrategyEntry[] = [
    { action: "bet", to_amount_bb: 3, frequency: 0.65 },
    { action: "check", to_amount_bb: null, frequency: 0.35 },
  ];

  it("renders one row per entry, preserving order", () => {
    render(<StrategyBars strategy={strategy} />);
    const rows = screen.getAllByTestId(/^strategy-row-/);
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByTestId("strategy-label")).toHaveTextContent(/bet.*3.*bb/i);
    expect(within(rows[1]).getByTestId("strategy-label")).toHaveTextContent(/check/i);
  });

  it("renders percent labels", () => {
    render(<StrategyBars strategy={strategy} />);
    expect(screen.getByText("65%")).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
  });

  it("marks the first row (argmax) as highlighted", () => {
    render(<StrategyBars strategy={strategy} />);
    const rows = screen.getAllByTestId(/^strategy-row-/);
    expect(rows[0]).toHaveAttribute("data-argmax", "true");
    expect(rows[1]).toHaveAttribute("data-argmax", "false");
  });

  it("sets the bar width proportional to frequency", () => {
    render(<StrategyBars strategy={strategy} />);
    const bars = screen.getAllByTestId("strategy-bar-fill");
    expect(bars[0].style.width).toBe("65%");
    expect(bars[1].style.width).toBe("35%");
  });

  it("renders no rows when strategy is empty", () => {
    const { container } = render(<StrategyBars strategy={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
