"""Cross-platform window-title lookup.

Each OS ships its own native adapter — Linux/X11 via `xdotool`, Windows via
`pygetwindow`, macOS via `Quartz`. For portability we call optional adapters
and surface a clear error when no adapter is wired for the current platform.
Callers should prefer `bbox:` in the profile when possible.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Callable

from poker_rta.profile.model import ROI


class WindowLookupUnavailable(RuntimeError):
    """Raised when no title-lookup adapter is available for this OS."""


def _linux_list_windows() -> list[tuple[str, ROI]]:
    if shutil.which("xdotool") is None:
        return []
    out = subprocess.run(
        ["xdotool", "search", "--name", ".*"],
        check=False,
        capture_output=True,
        text=True,
    )
    results: list[tuple[str, ROI]] = []
    for wid in out.stdout.splitlines():
        name = subprocess.run(
            ["xdotool", "getwindowname", wid], check=False, capture_output=True, text=True
        ).stdout.strip()
        geo = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", wid],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        env = dict(line.split("=", 1) for line in geo.splitlines() if "=" in line)
        try:
            roi = ROI(
                x=int(env["X"]),
                y=int(env["Y"]),
                width=int(env["WIDTH"]),
                height=int(env["HEIGHT"]),
            )
        except (KeyError, ValueError):
            continue
        results.append((name, roi))
    return results


_platform_list_windows: Callable[[], list[tuple[str, ROI]]] | None
if sys.platform.startswith("linux"):
    _platform_list_windows = _linux_list_windows
else:
    _platform_list_windows = None  # extend: win32 / darwin adapters


def resolve_title_to_bbox(title_contains: str) -> ROI | None:
    """Find the first window whose title contains `title_contains`.

    Returns the window bbox, or None if not found. Raises
    `WindowLookupUnavailable` if no adapter is wired for the current platform.
    """
    if _platform_list_windows is None:
        raise WindowLookupUnavailable(
            f"no window-title adapter for platform {sys.platform!r}; use explicit bbox in profile"
        )
    for name, roi in _platform_list_windows():
        if title_contains in name:
            return roi
    return None
