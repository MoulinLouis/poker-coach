from __future__ import annotations

from poker_rta.calibration.painter import CalibrationDoc, emit_profile

__all__ = ["CalibrationDoc", "emit_profile", "run"]


def __getattr__(name: str) -> object:
    if name == "run":
        from poker_rta.calibration.gui import run

        return run
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
