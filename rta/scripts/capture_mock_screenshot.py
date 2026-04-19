"""Capture the mock HTML poker table at step 0 (preflop) as a reference screenshot."""

from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("rta/tests/fixtures/screenshots/mock_html_preflop.png")
URL = "http://localhost:8080"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(URL, wait_until="networkidle")
        page.screenshot(
            path=str(OUT),
            clip={"x": 0, "y": 0, "width": 1280, "height": 720},
        )
        browser.close()
    print(f"Screenshot saved: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    sys.exit(main())
