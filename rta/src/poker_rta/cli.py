"""`poker_rta` CLI — `run`, `calibrate`, `replay` subcommands."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from poker_rta.capture.grab import grab_window
from poker_rta.client.coach_client import CoachClient
from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import observe_frame
from poker_rta.profile.io import load_profile
from poker_rta.runner import RunnerDeps, run_loop


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="poker_rta")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="start the real-time loop")
    run.add_argument("--profile", type=Path, required=True)
    run.add_argument("--coach-url", default="http://localhost:8000")
    run.add_argument("--bb", type=int, default=100)
    run.add_argument("--stack", type=int, default=10000)

    cal = sub.add_parser("calibrate", help="launch the calibration GUI")
    cal.add_argument("--screenshot", type=Path, required=True)

    return p


async def _run_cmd(args: argparse.Namespace) -> int:
    from poker_rta.overlay.window import AdviceOverlay

    profile = load_profile(args.profile)
    classifier = CardClassifier(templates_dir=Path(profile.card_templates_dir))

    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    overlay = AdviceOverlay()
    overlay.show()

    async with CoachClient(base_url=args.coach_url) as coach:
        deps = RunnerDeps(
            grab=lambda: grab_window(profile.window),
            observe=lambda img, pf: observe_frame(img, pf, classifier),
            coach=coach,
            overlay=overlay,
            bb=args.bb,
            starting_stack=args.stack,
        )
        await run_loop(profile, deps)
    app.quit()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "run":
        return asyncio.run(_run_cmd(args))
    if args.cmd == "calibrate":
        from poker_rta.calibration.gui import run as calibrate_run

        calibrate_run(args.screenshot)
        return 0
    raise SystemExit(f"unknown cmd {args.cmd!r}")


if __name__ == "__main__":
    raise SystemExit(main())
