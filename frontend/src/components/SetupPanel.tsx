import type { PresetSummary, Seat } from "../api/types";

export interface SetupValues {
  heroHole: string;
  villainHole: string;
  effectiveStack: number;
  button: Seat;
  presetId: string;
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
  return (
    <section className="rounded-xl bg-stone-800 p-4 text-stone-100 flex flex-wrap items-end gap-4 ring-1 ring-white/5">
      <Field label="Hero hole">
        <input
          value={values.heroHole}
          onChange={(e) => onChange({ heroHole: e.target.value })}
          placeholder="AsKd"
          className="w-20 bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
        />
      </Field>
      <Field label="Villain hole">
        <input
          value={values.villainHole}
          onChange={(e) => onChange({ villainHole: e.target.value })}
          placeholder="QcQh"
          className="w-20 bg-stone-900 rounded px-2 py-1 ring-1 ring-white/10 focus:ring-amber-400 outline-none"
        />
      </Field>
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
      <button
        data-testid="new-hand"
        onClick={onStart}
        disabled={disabled}
        className="px-4 py-2 rounded-lg font-semibold bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 transition"
      >
        <kbd className="mr-2 opacity-60 text-[10px] font-mono">n</kbd>
        New hand
      </button>
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
