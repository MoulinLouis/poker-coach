import { SUITS, type Suit } from "../utils/cards";

const RANK_NAMES: Record<string, string> = {
  A: "ace",
  K: "king",
  Q: "queen",
  J: "jack",
  T: "ten",
};

const SIZE_CLASS = {
  sm: "w-10 h-14",
  md: "w-14 h-20",
  lg: "w-20 h-28",
} as const;

export function PlayingCard({
  code,
  size = "md",
}: {
  code: string | null;
  size?: keyof typeof SIZE_CLASS;
}) {
  const sizeClass = SIZE_CLASS[size];

  if (!code) {
    return (
      <div
        data-facedown="true"
        className={`${sizeClass} rounded-md border-2 border-white/30 bg-gradient-to-br from-blue-900 to-blue-700 shadow-md`}
      />
    );
  }

  const rank = code[0];
  const suit = SUITS[code[1] as Suit];
  if (!suit) {
    return <div data-invalid="true" className={`${sizeClass} rounded-md bg-red-900`} />;
  }
  const rankName = RANK_NAMES[rank] ?? rank;
  const label = `${rankName} of ${suit.name}`;

  return (
    <svg
      viewBox="0 0 60 84"
      className={`${sizeClass} drop-shadow-md`}
      data-suit={code[1]}
      data-rank={rank}
      aria-label={label}
      role="img"
    >
      <rect
        x="1"
        y="1"
        width="58"
        height="82"
        rx="6"
        className="fill-[color:var(--color-card-bg)] stroke-black/20"
        strokeWidth="1"
      />
      <text x="6" y="18" className={`${suit.textClass} font-bold`} fontSize="14">
        {rank}
      </text>
      <text x="6" y="30" className={suit.textClass} fontSize="12">
        {suit.glyph}
      </text>
      <text x="30" y="56" textAnchor="middle" className={suit.textClass} fontSize="34">
        {suit.glyph}
      </text>
      <g transform="rotate(180 30 42)">
        <text x="6" y="18" className={`${suit.textClass} font-bold`} fontSize="14">
          {rank}
        </text>
        <text x="6" y="30" className={suit.textClass} fontSize="12">
          {suit.glyph}
        </text>
      </g>
    </svg>
  );
}
