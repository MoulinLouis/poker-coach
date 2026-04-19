"""YAML load/save for PlatformProfile."""

from __future__ import annotations

from pathlib import Path

import yaml

from poker_rta.profile.model import PlatformProfile


def load_profile(path: Path) -> PlatformProfile:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return PlatformProfile.model_validate(raw)


def save_profile(profile: PlatformProfile, path: Path) -> None:
    path.write_text(
        yaml.safe_dump(profile.model_dump(mode="python"), sort_keys=False),
        encoding="utf-8",
    )
