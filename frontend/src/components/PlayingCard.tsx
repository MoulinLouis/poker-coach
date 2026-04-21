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
  lg: "w-[5.2rem] h-[7.4rem]",
  // `board` scales with viewport so all 5 fit on phone
  board:
    "w-[3.25rem] sm:w-[4rem] lg:w-[5.2rem] h-[4.6rem] sm:h-[5.7rem] lg:h-[7.4rem]",
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
        className={`${sizeClass} relative rounded-[8px] overflow-hidden shadow-[0_6px_14px_-4px_rgba(0,0,0,0.7),inset_0_0_0_1px_rgba(201,162,94,0.35)]`}
        style={{
          background:
            "radial-gradient(circle at 30% 25%, #3a1014 0%, #20080a 55%, #120406 100%)",
        }}
      >
        <svg
          viewBox="0 0 60 84"
          className="absolute inset-0 w-full h-full"
          aria-hidden
        >
          <defs>
            <pattern
              id="deco-back"
              x="0"
              y="0"
              width="8"
              height="8"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="8" height="8" fill="transparent" />
              <path d="M0 4 L4 0 L8 4 L4 8 Z" fill="none" stroke="#c9a25e" strokeWidth="0.35" opacity="0.35" />
            </pattern>
          </defs>
          <rect x="3" y="3" width="54" height="78" rx="5" fill="url(#deco-back)" />
          <rect x="3" y="3" width="54" height="78" rx="5" fill="none" stroke="#c9a25e" strokeWidth="0.6" opacity="0.7" />
          <rect x="6" y="6" width="48" height="72" rx="3" fill="none" stroke="#c9a25e" strokeWidth="0.35" opacity="0.4" />
          <text
            x="30"
            y="48"
            textAnchor="middle"
            fontSize="20"
            fill="#c9a25e"
            opacity="0.85"
            fontFamily="Fraunces, serif"
            fontStyle="italic"
          >
            M
          </text>
        </svg>
      </div>
    );
  }

  const rank = code[0];
  const suit = SUITS[code[1] as Suit];
  if (!suit) {
    return <div data-invalid="true" className={`${sizeClass} rounded-md bg-red-900`} />;
  }
  const rankName = RANK_NAMES[rank] ?? rank;
  const label = `${rankName} of ${suit.name}`;
  const isRed = code[1] === "h" || code[1] === "d";
  const inkColor = isRed ? "var(--color-card-red)" : "var(--color-card-black)";

  return (
    <div
      className={`${sizeClass} relative rounded-[8px] overflow-hidden`}
      style={{
        background:
          "linear-gradient(180deg, #f8f1dc 0%, var(--color-card-face) 50%, #e0d4b2 100%)",
        boxShadow:
          "0 6px 14px -4px rgba(0,0,0,0.7), inset 0 0 0 1px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.6)",
      }}
      data-suit={code[1]}
      data-rank={rank}
      aria-label={label}
      role="img"
    >
      {/* subtle linen texture */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.18] mix-blend-multiply pointer-events-none"
        aria-hidden
      >
        <filter id="linen">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" />
          <feColorMatrix values="0 0 0 0 0.4  0 0 0 0 0.35  0 0 0 0 0.25  0 0 0 0.5 0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#linen)" />
      </svg>

      <svg
        viewBox="0 0 60 84"
        className="relative w-full h-full"
        aria-hidden
      >
        {/* deco frame */}
        <rect
          x="2.5"
          y="2.5"
          width="55"
          height="79"
          rx="5"
          fill="none"
          stroke="rgba(0,0,0,0.15)"
          strokeWidth="0.6"
        />
        {/* corner fleurons */}
        <g fill={inkColor} opacity="0.55">
          <circle cx="5.5" cy="5.5" r="0.9" />
          <circle cx="54.5" cy="5.5" r="0.9" />
          <circle cx="5.5" cy="78.5" r="0.9" />
          <circle cx="54.5" cy="78.5" r="0.9" />
        </g>

        {/* top-left index */}
        <text
          x="6"
          y="17"
          fill={inkColor}
          fontSize="14"
          fontWeight="700"
          fontFamily="Fraunces, Georgia, serif"
          style={{ fontVariationSettings: "'opsz' 144" }}
        >
          {rank}
        </text>
        <text
          x="6"
          y="29"
          fill={inkColor}
          fontSize="11"
        >
          {suit.glyph}
        </text>

        {/* center ornament + suit */}
        <text
          x="30"
          y="53"
          textAnchor="middle"
          fill={inkColor}
          fontSize="30"
        >
          {suit.glyph}
        </text>

        {/* bottom-right index */}
        <g transform="rotate(180 30 42)">
          <text
            x="6"
            y="17"
            fill={inkColor}
            fontSize="14"
            fontWeight="700"
            fontFamily="Fraunces, Georgia, serif"
            style={{ fontVariationSettings: "'opsz' 144" }}
          >
            {rank}
          </text>
          <text
            x="6"
            y="29"
            fill={inkColor}
            fontSize="11"
          >
            {suit.glyph}
          </text>
        </g>
      </svg>
    </div>
  );
}
