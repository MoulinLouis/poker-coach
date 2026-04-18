import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BoardPicker } from "./BoardPicker";

describe("BoardPicker", () => {
  it("renders 3 slots for flop", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(3);
  });

  it("renders 1 slot for turn with 3 locked flop cards", () => {
    render(
      <BoardPicker
        street="turn"
        existingBoard={["2c","3d","5s"]}
        excludedCards={["As","Kd","2c","3d","5s"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(1);
    expect(screen.getAllByTestId(/^board-locked-/)).toHaveLength(3);
  });

  it("renders 5 slots for runout from preflop all-in", () => {
    render(
      <BoardPicker
        street="runout"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(5);
  });

  it("renders 2 slots for runout from flop all-in", () => {
    render(
      <BoardPicker
        street="runout"
        existingBoard={["2c","3d","5s"]}
        excludedCards={["As","Kd","2c","3d","5s"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getAllByTestId(/^board-slot-/)).toHaveLength(2);
  });

  it("Confirm button disabled until all slots filled", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByTestId("board-picker-confirm")).toBeDisabled();
  });

  it("calls onConfirm with the picked cards in order", () => {
    const onConfirm = vi.fn();
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId("board-grid-Ah"));
    fireEvent.click(screen.getByTestId("board-grid-Kh"));
    fireEvent.click(screen.getByTestId("board-grid-Qh"));
    fireEvent.click(screen.getByTestId("board-picker-confirm"));
    expect(onConfirm).toHaveBeenCalledWith(["Ah","Kh","Qh"]);
  });

  it("random fills empty slots then enables Confirm", () => {
    const onConfirm = vi.fn();
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As", "Kd"]}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByTestId("board-picker-confirm")).toBeDisabled();
    fireEvent.click(screen.getByTestId("board-picker-random"));
    expect(screen.getByTestId("board-picker-confirm")).not.toBeDisabled();
    fireEvent.click(screen.getByTestId("board-picker-confirm"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    const picked = onConfirm.mock.calls[0][0] as string[];
    expect(picked).toHaveLength(3);
    expect(new Set(picked).size).toBe(3);
    for (const c of picked) expect(["As", "Kd"]).not.toContain(c);
  });

  it("random preserves already-picked slots", () => {
    const onConfirm = vi.fn();
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={[]}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByTestId("board-grid-Ah"));
    fireEvent.click(screen.getByTestId("board-picker-random"));
    fireEvent.click(screen.getByTestId("board-picker-confirm"));
    const picked = onConfirm.mock.calls[0][0] as string[];
    expect(picked[0]).toBe("Ah");
  });

  it("hides excluded cards from the grid", () => {
    render(
      <BoardPicker
        street="flop"
        existingBoard={[]}
        excludedCards={["As","Kd"]}
        onConfirm={() => {}}
      />,
    );
    const asBtn = screen.queryByTestId("board-grid-As");
    if (asBtn) expect(asBtn).toBeDisabled();
  });
});
