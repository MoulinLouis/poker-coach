export type Suit = "s" | "h" | "d" | "c";

export const SUIT_META: Record<Suit, { glyph: string; textClass: string; colorClass: string }> = {
  s: { glyph: "♠", textClass: "fill-[color:var(--color-card-black)]", colorClass: "text-stone-200" },
  h: { glyph: "♥", textClass: "fill-[color:var(--color-card-red)]", colorClass: "text-red-400" },
  d: { glyph: "♦", textClass: "fill-[color:var(--color-card-red)]", colorClass: "text-red-400" },
  c: { glyph: "♣", textClass: "fill-[color:var(--color-card-black)]", colorClass: "text-stone-200" },
};

export function parseHole(raw: string): [string, string] | null {
  if (raw.length !== 4) return null;
  return [raw.slice(0, 2), raw.slice(2, 4)];
}
