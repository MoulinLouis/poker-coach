import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlayingCard } from "./PlayingCard";

describe("PlayingCard", () => {
  it("renders rank and is labelled with rank + suit name", () => {
    render(<PlayingCard code="As" />);
    expect(screen.getByLabelText(/ace of spades/i)).toBeInTheDocument();
  });

  it("sets data-suit for styling hooks", () => {
    const { container } = render(<PlayingCard code="Qh" />);
    expect(container.querySelector('[data-suit="h"]')).not.toBeNull();
  });

  it("renders face-down card when code is null", () => {
    const { container } = render(<PlayingCard code={null} />);
    expect(container.querySelector('[data-facedown="true"]')).not.toBeNull();
  });

  it("falls back to invalid marker for malformed code", () => {
    const { container } = render(<PlayingCard code="Zz" />);
    expect(container.querySelector('[data-invalid="true"]')).not.toBeNull();
  });
});
