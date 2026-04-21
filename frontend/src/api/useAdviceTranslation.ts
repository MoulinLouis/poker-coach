import { useCallback, useEffect, useRef, useState } from "react";
import { translateText } from "./client";

export type TranslationState = {
  lang: "en" | "fr";
  frText: string | null;
  loading: boolean;
  error: string | null;
  toggle: () => void;
};

export function useAdviceTranslation(text: string): TranslationState {
  const [lang, setLang] = useState<"en" | "fr">("en");
  const [frText, setFrText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const prevTextRef = useRef(text);
  if (prevTextRef.current !== text) {
    prevTextRef.current = text;
    if (lang !== "en") setLang("en");
    if (frText !== null) setFrText(null);
    if (loading) setLoading(false);
    if (error !== null) setError(null);
  }

  // Set to true on every mount and flipped to false on unmount. StrictMode
  // double-invokes effects in dev (mount → cleanup → mount), so we MUST
  // re-set to true in the effect body — otherwise the first cleanup pass
  // latches the ref at false and every subsequent .then() bails out.
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const toggle = useCallback(() => {
    if (loading) return;

    if (lang === "fr") {
      setLang("en");
      return;
    }
    if (frText !== null) {
      setLang("fr");
      return;
    }
    setLoading(true);
    setError(null);
    translateText(text)
      .then((r) => {
        if (!mountedRef.current) return;
        setFrText(r.translation);
        setLang("fr");
      })
      .catch((e: Error) => {
        if (!mountedRef.current) return;
        setError(e.message);
        setLang("en");
      })
      .finally(() => {
        if (!mountedRef.current) return;
        setLoading(false);
      });
  }, [lang, frText, loading, text]);

  return { lang, frText, loading, error, toggle };
}
