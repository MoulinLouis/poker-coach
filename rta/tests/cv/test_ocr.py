from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from poker_rta.cv.ocr import NumberReader, parse_chip_amount
from poker_rta.profile.model import OCRPreprocess


def _render_text(text: str, size: tuple[int, int] = (120, 30)) -> np.ndarray:
    img = Image.new("RGB", size, "black")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    draw.text((4, 2), text, fill="yellow", font=font)
    return np.asarray(img)[..., ::-1]  # RGB -> BGR


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("123", 123),
        ("1,234", 1234),
        ("$1,234", 1234),
        ("10000", 10000),
    ],
)
def test_parse_chip_amount(raw: str, expected: int) -> None:
    assert parse_chip_amount(raw) == expected


def test_parse_rejects_nonnumeric() -> None:
    assert parse_chip_amount("abc") is None


@pytest.mark.slow
def test_reader_reads_simple_number() -> None:
    reader = NumberReader(OCRPreprocess(grayscale=True, threshold=128, scale=2.0))
    img = _render_text("9700")
    value = reader.read(img)
    assert value == 9700
