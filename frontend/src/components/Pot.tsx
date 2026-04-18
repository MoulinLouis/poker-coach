export function Pot({ potBb, committedBb }: { potBb: number; committedBb: number }) {
  const total = potBb + committedBb;
  return (
    <div
      data-testid="pot"
      className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-black/60 text-white backdrop-blur-sm ring-1 ring-white/10"
    >
      <span className="w-3 h-3 rounded-full bg-[color:var(--color-chip-gold)] ring-2 ring-yellow-200/40" />
      <span className="font-semibold tabular-nums">{total.toFixed(1)} bb</span>
      <span className="text-[10px] uppercase tracking-widest opacity-70">pot</span>
    </div>
  );
}
