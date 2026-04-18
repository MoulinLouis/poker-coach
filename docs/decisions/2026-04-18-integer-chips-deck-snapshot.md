# Integer chips; `deck_snapshot` over `rng_seed` for replay

## Context

Two questions during engine design: (1) how to represent money? (2) how to make a hand reproducible for the "retry with prompt v2" workflow?

## Decision

1. All engine amounts are integer chips. `bb=100` means one big blind is 100 chips. Display layer divides.
2. Hands carry both `rng_seed: int | None` and `deck_snapshot: list[str] | None` on `GameState`. `deck_snapshot` — the 52-card deck in dealing order — is the **authoritative** replay artifact. `rng_seed` is informational only.

## Rationale

- Floats eventually round-trip-break in any system that does arithmetic over them. Integer chips mirror what every production poker room stores.
- Seeds are fragile across Python versions and `random.shuffle` implementation changes — a seed that reproduces hand X today may not tomorrow. Storing the resulting deck bypasses that risk. Seeds remain useful for generating deterministic test hands.

## Canary

- Any `float` in `engine/rules.py` money math is a red flag. Grep for `/` and `*` in that file.
- `GameState.deck_snapshot` presence is not optional for live-mode hands — `start_hand(rng_seed=...)` must populate it.
- Replay idempotency property test: `reduce(apply_action, state.history, initial_state(state)) == state` in `tests/engine/test_invariants.py`. If it fails, reproduction is broken.

## Implementing commits

- `10853fc` — domain models and seeded deck
- `f85db12` — rules engine
- `8bc574b` — Hypothesis invariants
