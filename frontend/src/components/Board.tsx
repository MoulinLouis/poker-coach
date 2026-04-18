import { PlayingCard } from "./PlayingCard";

export function Board({ cards }: { cards: string[] }) {
  return (
    <div data-testid="board" className="flex gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center">
          {cards[i] ? (
            <div className="anim-zoom-in">
              <PlayingCard code={cards[i]} size="lg" />
            </div>
          ) : (
            <div className="w-20 h-28 rounded-md border-2 border-dashed border-white/15" />
          )}
        </div>
      ))}
    </div>
  );
}
