import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as client from "./client";
import { useTranslation } from "./useTranslation";

describe("useTranslation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("starts in EN with no cached translation", () => {
    const { result } = renderHook(() => useTranslation("hello"));
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("fetches FR on first toggle and caches the result", async () => {
    const spy = vi
      .spyOn(client, "translateText")
      .mockResolvedValue({ translation: "bonjour", cost_usd: 0.001 });

    const { result } = renderHook(() => useTranslation("hello"));
    act(() => {
      result.current.toggle();
    });

    await waitFor(() => expect(result.current.lang).toBe("fr"));
    expect(result.current.frText).toBe("bonjour");
    expect(spy).toHaveBeenCalledTimes(1);

    act(() => result.current.toggle());
    expect(result.current.lang).toBe("en");
    act(() => result.current.toggle());
    expect(result.current.lang).toBe("fr");
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("resets cache when text changes", async () => {
    vi.spyOn(client, "translateText")
      .mockResolvedValueOnce({ translation: "bonjour", cost_usd: 0.001 })
      .mockResolvedValueOnce({ translation: "salut", cost_usd: 0.001 });

    const { result, rerender } = renderHook(
      ({ text }: { text: string }) => useTranslation(text),
      { initialProps: { text: "hello" } },
    );

    act(() => result.current.toggle());
    await waitFor(() => expect(result.current.frText).toBe("bonjour"));

    rerender({ text: "hi" });
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();

    act(() => result.current.toggle());
    await waitFor(() => expect(result.current.frText).toBe("salut"));
  });

  it("reverts to EN on error", async () => {
    vi.spyOn(client, "translateText").mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useTranslation("hello"));
    act(() => result.current.toggle());

    await waitFor(() => expect(result.current.error).toBe("boom"));
    expect(result.current.lang).toBe("en");
    expect(result.current.frText).toBeNull();
  });

  it("ignores clicks while a request is in flight", async () => {
    let resolveFn: (v: { translation: string; cost_usd: number }) => void = () => {};
    const pending = new Promise<{ translation: string; cost_usd: number }>((r) => {
      resolveFn = r;
    });
    const spy = vi.spyOn(client, "translateText").mockReturnValue(pending);

    const { result } = renderHook(() => useTranslation("hello"));
    act(() => result.current.toggle());
    expect(result.current.loading).toBe(true);

    act(() => result.current.toggle());
    expect(spy).toHaveBeenCalledTimes(1);

    resolveFn({ translation: "bonjour", cost_usd: 0.001 });
    await waitFor(() => expect(result.current.lang).toBe("fr"));
  });
});
