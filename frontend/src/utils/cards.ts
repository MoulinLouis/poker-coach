export type Suit = "s" | "h" | "d" | "c";

export const SUITS: Record<Suit, { glyph: string; color: string; name: string; textClass: string }> = {
  s: { glyph: "♠", color: "text-stone-200", name: "spades", textClass: "fill-[color:var(--color-card-black)]" },
  h: { glyph: "♥", color: "text-red-400", name: "hearts", textClass: "fill-[color:var(--color-card-red)]" },
  d: { glyph: "♦", color: "text-red-400", name: "diamonds", textClass: "fill-[color:var(--color-card-red)]" },
  c: { glyph: "♣", color: "text-stone-200", name: "clubs", textClass: "fill-[color:var(--color-card-black)]" },
};

export function parseHole(input: string): [string, string] | null {
  if (input.length !== 4) return null;
  return [input.slice(0, 2), input.slice(2, 4)];
}
