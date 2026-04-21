import { act, render, renderHook, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LocaleProvider, useLocale } from "./LocaleContext";

function wrapper({ children }: { children: React.ReactNode }) {
  return <LocaleProvider>{children}</LocaleProvider>;
}

describe("LocaleProvider + useLocale", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("defaults to EN when localStorage is empty", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.lang).toBe("en");
    expect(result.current.t("nav.live")).toBe("Live Coach");
  });

  it("reads persisted language on init", () => {
    window.localStorage.setItem("locale", "fr");
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.lang).toBe("fr");
    expect(result.current.t("nav.live")).toBe("Coach en direct");
  });

  it("ignores garbage localStorage values and defaults to EN", () => {
    window.localStorage.setItem("locale", "de");
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(result.current.lang).toBe("en");
  });

  it("setLang updates state and writes localStorage", () => {
    const { result } = renderHook(() => useLocale(), { wrapper });
    act(() => result.current.setLang("fr"));
    expect(result.current.lang).toBe("fr");
    expect(window.localStorage.getItem("locale")).toBe("fr");
    expect(result.current.t("nav.spot")).toBe("Analyse de situation");
  });

  it("t() falls back to the key and warns on missing keys in dev", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { result } = renderHook(() => useLocale(), { wrapper });
    // Cast to bypass the compile-time restriction for this negative test.
    const missing = (result.current.t as (k: string) => string)("nav.missing");
    expect(missing).toBe("nav.missing");
    expect(warn).toHaveBeenCalled();
  });

  it("useLocale without a provider falls back to EN", () => {
    function Probe() {
      const { lang, t } = useLocale();
      return <span data-testid="probe">{lang}:{t("nav.history")}</span>;
    }
    render(<Probe />);
    expect(screen.getByTestId("probe").textContent).toBe("en:History");
  });

  it("survives localStorage being unavailable", () => {
    const setItem = vi
      .spyOn(window.localStorage.__proto__, "setItem")
      .mockImplementation(() => {
        throw new Error("disabled");
      });
    const { result } = renderHook(() => useLocale(), { wrapper });
    expect(() => act(() => result.current.setLang("fr"))).not.toThrow();
    expect(result.current.lang).toBe("fr"); // in-memory still works
    setItem.mockRestore();
  });
});
