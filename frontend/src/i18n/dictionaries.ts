import { en } from "./en";
import { fr } from "./fr";

export type Lang = "en" | "fr";

// Widen the literal types introduced by `as const` in en.ts so translations
// in other languages (fr, etc.) can assign different strings to the same shape.
type Widen<T> = T extends string
  ? string
  : { -readonly [K in keyof T]: Widen<T[K]> };

export type Dict = Widen<typeof en>;

// Recursively build the union of dotted string paths through Dict.
// "nav.live" | "nav.spot" | ...
type Join<K, P> = K extends string
  ? P extends string
    ? `${K}.${P}`
    : never
  : never;

export type DictKey<T = Dict> = {
  [K in keyof T]: T[K] extends string
    ? K & string
    : Join<K, DictKey<T[K]>>;
}[keyof T];

export const DICTIONARIES: Record<Lang, Dict> = { en, fr };

export function lookup(dict: Dict, key: string): string {
  const parts = key.split(".");
  let node: unknown = dict;
  for (const p of parts) {
    if (node && typeof node === "object" && p in (node as object)) {
      node = (node as Record<string, unknown>)[p];
    } else {
      return key;
    }
  }
  return typeof node === "string" ? node : key;
}
