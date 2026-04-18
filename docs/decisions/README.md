# Decision log

One file per non-obvious decision that took time to land and would cost
future Claude sessions time to rediscover. Named `YYYY-MM-DD-<slug>.md`
in chronological order.

Structure per ADR: **Context · Decision · Rationale · Canary** (how to
detect if the assumption breaks) · **Implementing commit(s)**.

When you change one of these decisions, update the ADR in the same
commit as the code change. When adding a new ADR, also add a bullet
below.

## Index

- [2026-04-18: Model strategy — GPT-5.3-codex over Claude](2026-04-18-model-strategy.md)
- [2026-04-18: Integer chips; deck_snapshot over rng_seed for replay](2026-04-18-integer-chips-deck-snapshot.md)
- [2026-04-18: Three-layer villain-information guard](2026-04-18-villain-leak-guard.md)
- [2026-04-18: Lazy oracle invocation + atomic SSE claim](2026-04-18-lazy-oracle-invocation.md)
- [2026-04-18: Anthropic thinking API — two dispatches (enabled / adaptive)](2026-04-18-anthropic-thinking-api-dispatch.md)
- [2026-04-18: tool_choice + thinking — auto only, system prompt enforces](2026-04-18-anthropic-tool-choice-with-thinking.md)
- [2026-04-18: Async SDK stream final-message methods must be awaited](2026-04-18-async-stream-await.md)
- [2026-04-18: CardPicker is uncontrolled, no prop resync](2026-04-18-cardpicker-uncontrolled.md)
