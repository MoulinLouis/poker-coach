import type { PresetSummary, Seat, VillainProfile } from "../api/types";
import { parseHole } from "../utils/cards";
import { CardPicker } from "./CardPicker";

export interface SetupValues {
  heroHole: string; // 4-char code like "AsKd"
  villainHole: string;
  effectiveStack: number;
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

  return (
    <section className="rounded-xl bg-stone-800 p-4 text-stone-100 flex flex-col gap-4 ring-1 ring-white/5">
      <div className="flex flex-wrap items-end gap-4">
        <Field label="Effective stack (chips)">
          <input
            type="number"
            value={values.effectiveStack}
            onChange={(e) =>
              onChange({ effectiveStack: parseInt(e.target.value || "0", 10) })
            }
            className="w-24 bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
          />
        </Field>
        <Field label="Button">
          <select
            value={values.button}
            onChange={(e) => onChange({ button: e.target.value as Seat })}
            className="bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
          >
            <option value="hero">hero</option>
            <option value="villain">villain</option>
          </select>
        </Field>
        <Field label="Model">
          <select
            value={values.presetId}
            onChange={(e) => onChange({ presetId: e.target.value })}
            className="bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
          >
            {presets.map((p) => (
              <option key={p.selector_id} value={p.selector_id}>
                {p.selector_id}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Villain profile">
          <div className="flex gap-1 rounded bg-stone-900 p-1 ring-1 ring-white/10">
            {(["reg", "unknown"] as const).map((p) => (
              <button
                key={p}
                type="button"
                data-testid={`villain-profile-${p}`}
                className={`rounded px-2 py-1 text-xs transition ${
                  values.villainProfile === p
                    ? "bg-stone-600 text-stone-100"
                    : "text-stone-400 hover:text-stone-200"
                }`}
                onClick={() => onChange({ villainProfile: p })}
              >
                {p === "reg" ? "Reg" : "Unknown"}
              </button>
            ))}
          </div>
        </Field>
        <button
          data-testid="new-hand"
          onClick={onStart}
          disabled={disabled}
          className="ml-auto px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition"
        >
          <kbd className="mr-2 opacity-60 text-[10px] font-mono">n</kbd>
          New hand
        </button>
      </div>

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
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col text-[11px] uppercase tracking-wider opacity-70 gap-1">
      <span>{label}</span>
      <div className="normal-case opacity-100 text-sm">{children}</div>
    </label>
  );
}
