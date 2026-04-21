import { describe, expect, it } from "vitest";
import {
  formatDateTime,
  formatInt,
  formatLatencyMs,
  formatUsd,
} from "./format";

describe("formatUsd", () => {
  it("renders USD with 4 fraction digits in EN locale", () => {
    expect(formatUsd("en", 0.0034)).toBe("$0.0034");
    expect(formatUsd("en", 1234.5678)).toBe("$1,234.5678");
  });

  it("renders USD with comma decimal and narrow symbol in FR locale", () => {
    // FR with narrowSymbol + USD yields '0,0034 $' / '1 234,5678 $'.
    // The space between thousands is a NBSP (U+202F in modern runtimes or U+00A0 in older),
    // so we match structurally rather than on exact whitespace.
    const fr = formatUsd("fr", 1234.5678);
    expect(fr).toMatch(/^1.234,5678\s\$$/);
  });

  it("respects the digits override", () => {
    expect(formatUsd("en", 1.23, 2)).toBe("$1.23");
  });
});

describe("formatInt", () => {
  it("uses no separator for small numbers", () => {
    expect(formatInt("en", 42)).toBe("42");
    expect(formatInt("fr", 42)).toBe("42");
  });

  it("uses comma grouping in EN and non-ASCII space in FR", () => {
    expect(formatInt("en", 1234)).toBe("1,234");
    expect(formatInt("fr", 1234)).toMatch(/^1.234$/);
  });
});

describe("formatLatencyMs", () => {
  it("appends the ms unit with a space", () => {
    expect(formatLatencyMs("en", 123)).toBe("123 ms");
    expect(formatLatencyMs("fr", 1234)).toMatch(/^1.234 ms$/);
  });
});

describe("formatDateTime", () => {
  it("renders a valid ISO string in the current locale", () => {
    const iso = "2026-04-21T10:52:11Z";
    const en = formatDateTime("en", iso);
    const fr = formatDateTime("fr", iso);
    // Exact output depends on ICU version and TZ, so assert on structural shape:
    //  - EN short date uses slashes, starts with the month digit.
    //  - FR short date uses slashes, puts the day first (two digits).
    //  - Both carry a 2-digit hour:minute:second in 24h format.
    expect(en).toMatch(/^\d{1,2}\/\d{1,2}\/\d{2,4}(,|)\s\d{2}:\d{2}:\d{2}$/);
    expect(fr).toMatch(/^\d{2}\/\d{2}\/\d{4}(,|)\s\d{2}:\d{2}:\d{2}$/);
  });

  it("returns the input unchanged when the ISO string is invalid", () => {
    expect(formatDateTime("en", "not-a-date")).toBe("not-a-date");
  });
});
