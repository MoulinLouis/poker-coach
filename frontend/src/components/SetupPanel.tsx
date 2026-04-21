import type { PresetSummary, Seat, VillainProfile } from "../api/types";
import { parseHole } from "../utils/cards";
import { CardPicker } from "./CardPicker";
import { useLocale } from "../i18n";

export interface SetupValues {
  heroHole: string;
  villainHole: string;
  heroStack: number;
  villainStack: number;
  ante: number;
  button: Seat;
  presetId: string;
  villainProfile: VillainProfile;
}

export function SetupPanel({
  values,
  presets,
  onChange,
  onStart,
  disabled,
}: {
  values: SetupValues;
  presets: PresetSummary[];
  onChange: (patch: Partial<SetupValues>) => void;
  onStart: () => void;
  disabled?: boolean;
}) {
  const hero = parseHole(values.heroHole);
  const villain = parseHole(values.villainHole);
  const { t } = useLocale();

  return (
    <section
      className="relative rounded-2xl p-4 sm:p-6 flex flex-col gap-4 sm:gap-5 overflow-hidden"
      style={{
        background:
          "linear-gradient(180deg, rgba(29,23,24,0.85), rgba(20,16,18,0.9))",
        border: "1px solid rgba(201,162,94,0.2)",
        boxShadow:
          "0 20px 60px -30px rgba(0,0,0,0.85), inset 0 1px 0 rgba(201,162,94,0.14)",
      }}
    >
      {/* Header ribbon */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-4">
        <div className="flex flex-col">
          <span className="font-mono text-[9px] tracking-[0.35em] sm:tracking-[0.4em] uppercase text-[color:var(--color-parchment-dim)]">
            {t("setup.kicker")}
          </span>
          <span className="text-lg sm:text-xl font-semibold tracking-tight text-[color:var(--color-bone)]">
            {t("setup.title")}
          </span>
        </div>
        <button
          data-testid="new-hand"
          onClick={onStart}
          disabled={disabled}
          className="chip-button h-11 sm:h-12 px-4 sm:px-5 flex items-center justify-center gap-2 sm:gap-3 group shrink-0"
          style={
            {
              "--chip-core":
                "linear-gradient(180deg, #e6c584 0%, #a07a2e 100%)",
              color: "var(--color-ink)",
            } as React.CSSProperties
          }
        >
          <kbd className="hidden sm:inline font-mono text-[9px] tracking-widest px-1.5 py-0.5 rounded border border-[color:var(--color-ink)]/30 bg-black/15">
            N
          </kbd>
          <span className="font-semibold text-sm tracking-tight">
            {t("setup.newHand")}
          </span>
          <span className="text-base leading-none group-hover:translate-x-0.5 transition-transform">
            →
          </span>
        </button>
      </div>

      <div className="deco-rule" />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-5 lg:gap-6 items-start">
        {/* left column — fields */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <Field label={t("setup.heroStack")} unit={t("setup.chipsUnit")}>
            <input
              type="number"
              value={values.heroStack}
              onChange={(e) =>
                onChange({ heroStack: parseInt(e.target.value || "0", 10) })
              }
              className="w-full bg-transparent px-3 py-2 rounded-md font-mono tabular-nums text-[color:var(--color-bone)] outline-none transition-colors"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            />
          </Field>
          <Field label={t("setup.villainStack")} unit={t("setup.chipsUnit")}>
            <input
              type="number"
              value={values.villainStack}
              onChange={(e) =>
                onChange({ villainStack: parseInt(e.target.value || "0", 10) })
              }
              className="w-full bg-transparent px-3 py-2 rounded-md font-mono tabular-nums text-[color:var(--color-bone)] outline-none transition-colors"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            />
          </Field>
          <Field label={t("setup.ante")} unit={t("setup.chipsUnit")}>
            <input
              type="number"
              value={values.ante}
              onChange={(e) =>
                onChange({ ante: parseInt(e.target.value || "0", 10) })
              }
              className="w-full bg-transparent px-3 py-2 rounded-md font-mono tabular-nums text-[color:var(--color-bone)] outline-none transition-colors"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            />
          </Field>
          <Field label={t("setup.button")}>
            <select
              value={values.button}
              onChange={(e) => onChange({ button: e.target.value as Seat })}
              className="w-full px-3 py-2 rounded-md text-sm text-[color:var(--color-bone)] outline-none transition-colors appearance-none cursor-pointer"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            >
              <option value="hero">{t("setup.hero")}</option>
              <option value="villain">{t("setup.villain")}</option>
            </select>
          </Field>
          <Field label={t("setup.oracleModel")}>
            <select
              value={values.presetId}
              onChange={(e) => onChange({ presetId: e.target.value })}
              className="w-full px-3 py-2 rounded-md font-mono text-[11px] text-[color:var(--color-bone)] outline-none transition-colors appearance-none cursor-pointer"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            >
              {presets.map((p) => (
                <option key={p.selector_id} value={p.selector_id}>
                  {p.selector_id}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t("setup.villainProfile")}>
            <div
              className="flex p-1 rounded-md"
              style={{
                border: "1px solid rgba(201,162,94,0.22)",
                background: "rgba(10,7,6,0.45)",
              }}
            >
              {(["reg", "unknown"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  data-testid={`villain-profile-${p}`}
                  className="flex-1 rounded px-2 py-1 font-mono text-[10px] uppercase tracking-[0.2em] transition"
                  style={{
                    color:
                      values.villainProfile === p
                        ? "var(--color-ink)"
                        : "var(--color-parchment-dim)",
                    background:
                      values.villainProfile === p
                        ? "linear-gradient(180deg, var(--color-gold-bright), var(--color-gold-deep))"
                        : "transparent",
                  }}
                  onClick={() => onChange({ villainProfile: p })}
                >
                  {p === "reg" ? t("setup.profileReg") : t("setup.profileUnknown")}
                </button>
              ))}
            </div>
          </Field>
          <div className="col-span-2 sm:col-span-4 font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
            {t("setup.effectiveStack")}:{" "}
            <span className="text-[color:var(--color-bone)] tabular-nums">
              {Math.min(values.heroStack, values.villainStack)}
            </span>{" "}
            {t("setup.chipsUnit")}
          </div>
        </div>

        {/* right column — card picker area */}
        <div className="shrink-0">
          <CardPicker
            heroHole={hero}
            villainHole={villain}
            onChange={({ hero: h, villain: v }) =>
              onChange({
                heroHole: h ? h[0] + h[1] : "",
                villainHole: v ? v[0] + v[1] : "",
              })
            }
          />
        </div>
      </div>
    </section>
  );
}

function Field({
  label,
  unit,
  children,
}: {
  label: string;
  unit?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="flex items-baseline justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.3em] text-[color:var(--color-parchment-dim)]">
          {label}
        </span>
        {unit && (
          <span className="font-mono text-[8px] uppercase tracking-widest text-[color:var(--color-gold-deep)]">
            {unit}
          </span>
        )}
      </span>
      {children}
    </label>
  );
}
