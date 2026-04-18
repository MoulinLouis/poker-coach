import { useEffect } from "react";

export interface HotkeyBinding {
  key: string;
  handler: () => void;
  disabled?: boolean;
}

export function useHotkeys(bindings: HotkeyBinding[]): void {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't swallow typing in form fields.
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        e.target instanceof HTMLSelectElement
      ) {
        return;
      }
      const match = bindings.find(
        (b) => !b.disabled && b.key.toLowerCase() === e.key.toLowerCase(),
      );
      if (match) {
        e.preventDefault();
        match.handler();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [bindings]);
}
