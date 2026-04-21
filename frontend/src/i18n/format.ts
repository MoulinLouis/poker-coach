import type { Lang } from "./dictionaries";

const LOCALE: Record<Lang, string> = { en: "en-US", fr: "fr-FR" };

export function formatUsd(lang: Lang, amount: number, digits = 4): string {
  return new Intl.NumberFormat(LOCALE[lang], {
    style: "currency",
    currency: "USD",
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(amount);
}

export function formatInt(lang: Lang, n: number): string {
  return new Intl.NumberFormat(LOCALE[lang]).format(n);
}

export function formatLatencyMs(lang: Lang, ms: number): string {
  return `${formatInt(lang, ms)} ms`;
}

export function formatDateTime(lang: Lang, iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(LOCALE[lang], {
    dateStyle: "short",
    timeStyle: "medium",
    hourCycle: "h23",
  }).format(d);
}
