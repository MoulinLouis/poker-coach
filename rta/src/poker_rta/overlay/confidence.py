"""Per-field confidence classification and HTML rendering utilities."""

from __future__ import annotations

from typing import Literal


def classify(c: float) -> Literal["ok", "warn", "bad"]:
    return "ok" if c >= 0.9 else ("warn" if c >= 0.7 else "bad")


def render_line(label: str, c: float) -> str:
    color = {"ok": "#4f4", "warn": "#fc4", "bad": "#f44"}[classify(c)]
    return f'<span style="color:{color};">●</span> {label} ({c:.2f})'
