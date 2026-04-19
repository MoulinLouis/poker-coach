"""One-off: render mock_html cards at fixed size to templates dir."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]
SUITS = ["s", "h", "d", "c"]
OUT = Path("rta/templates/mock_html/cards")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    for r in RANKS:
        for s in SUITS:
            img = Image.new("RGB", (60, 80), "white")
            draw = ImageDraw.Draw(img)
            text = f"{r}{s}"
            bbox = draw.textbbox((0, 0), text, font=font)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((60 - w) / 2, (80 - h) / 2), text, fill="black", font=font)
            img.save(OUT / f"{r}{s}.png")
    print(f"Generated {len(RANKS) * len(SUITS)} card templates in {OUT}")


if __name__ == "__main__":
    main()
