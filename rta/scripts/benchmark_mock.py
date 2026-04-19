"""Benchmark the CV pipeline against the 5-step mock recording.

Emits CV accuracy (cards, OCR) and end-to-end latency per step. Numbers feed
the paper's 'technical feasibility' section.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from poker_rta.cv.cards import CardClassifier
from poker_rta.cv.pipeline import observe_frame
from poker_rta.profile.io import load_profile
from poker_rta.record import replay_session


def main() -> None:
    root = Path("rta/tests/fixtures/recordings/mock_script")
    profile = load_profile(Path("rta/profiles/mock_html.yaml"))
    classifier = CardClassifier(templates_dir=Path(profile.card_templates_dir))
    gold = json.loads((root / "ground_truth.json").read_text())

    card_hits = 0
    card_total = 0
    num_hits = 0
    num_total = 0
    latencies: list[float] = []

    for i, frame in enumerate(replay_session(root)):
        t0 = time.perf_counter()
        obs = observe_frame(frame, profile, classifier)
        latencies.append((time.perf_counter() - t0) * 1000)

        exp = gold[i]
        for got, want in zip(obs.board, exp["board"], strict=False):
            card_hits += got == want
            card_total += 1
        if obs.hero_cards and exp.get("hero_cards"):
            for got, want in zip(obs.hero_cards, exp["hero_cards"], strict=True):
                card_hits += got == want
                card_total += 1

        for field in ("pot_chips", "hero_stack_chips", "villain_stack_chips"):
            want = exp.get(field)
            got = getattr(obs, field)
            if want is not None:
                num_hits += got == want
                num_total += 1

    print(f"card accuracy: {card_hits}/{card_total} = {card_hits / card_total:.2%}")
    print(f"number accuracy: {num_hits}/{num_total} = {num_hits / num_total:.2%}")
    print(f"median observe latency: {sorted(latencies)[len(latencies) // 2]:.1f} ms")


if __name__ == "__main__":
    main()
