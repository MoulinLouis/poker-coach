import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DICTIONARIES, lookup, type DictKey, type Lang } from "./dictionaries";
import { en } from "./en";

const STORAGE_KEY = "locale";

interface LocaleValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: DictKey) => string;
}

const LocaleContext = createContext<LocaleValue | null>(null);

function readInitial(): Lang {
  if (typeof window === "undefined") return "en";
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return v === "fr" || v === "en" ? v : "en";
  } catch {
    return "en";
  }
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(readInitial);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore storage failure (private mode, disabled) */
    }
  }, []);

  const value = useMemo<LocaleValue>(() => {
    const dict = DICTIONARIES[lang];
    return {
      lang,
      setLang,
      t: (key) => {
        const out = lookup(dict, key);
        if (out === key && import.meta.env.DEV) {
          console.warn(`[i18n] missing key: ${key} (lang=${lang})`);
        }
        return out;
      },
    };
  }, [lang, setLang]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

// Fallback: when no provider is present (e.g. a test that doesn't wrap),
// return EN with a no-op setLang. This keeps existing component tests
// passing without forcing wrappers on every render call.
const FALLBACK: LocaleValue = {
  lang: "en",
  setLang: () => undefined,
  t: (key) => lookup(en, key as string),
};

export function useLocale(): LocaleValue {
  return useContext(LocaleContext) ?? FALLBACK;
}
