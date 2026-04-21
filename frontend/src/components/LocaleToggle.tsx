import { useLocale } from "../i18n";
import type { Lang } from "../i18n";

export function LocaleToggle() {
  const { lang, setLang } = useLocale();
  return (
    <div
      data-testid="locale-toggle"
      className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.28em]"
    >
      <Btn active={lang === "en"} value="en" setLang={setLang} />
      <span className="w-px h-3 bg-[color:var(--color-gold-shadow)]" />
      <Btn active={lang === "fr"} value="fr" setLang={setLang} />
    </div>
  );
}

function Btn({
  active,
  value,
  setLang,
}: {
  active: boolean;
  value: Lang;
  setLang: (l: Lang) => void;
}) {
  return (
    <button
      type="button"
      data-testid={`locale-${value}`}
      onClick={() => setLang(value)}
      aria-pressed={active}
      className={
        active
          ? "text-[color:var(--color-bone)]"
          : "text-[color:var(--color-parchment-dim)] hover:text-[color:var(--color-bone-soft)] transition"
      }
    >
      {value.toUpperCase()}
    </button>
  );
}
