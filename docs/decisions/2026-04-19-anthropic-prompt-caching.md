# Anthropic prompt caching on system block

## Context

Every decision on a Claude preset sends the same ~1140-token system prompt plus the `submit_advice` tool schema. Without caching, we pay full input rate for those ~1290 tokens on every call — on Opus 4.7 ($15/Mtok) that's ~$0.019 of billable input per call that never changes.

Within a session (a user working through hands or spot-analyzing), back-to-back decisions land well within Anthropic's 5-minute ephemeral cache TTL.

## Decision

Send the `system` field as a single text block with `cache_control={"type":"ephemeral"}`. Anthropic's canonical request ordering is `tools -> system -> messages`, and a `cache_control` marker caches everything up to and including the marked block — so one marker on system covers tools + system as a single cached prefix.

Parse the two new usage fields (`cache_creation_input_tokens`, `cache_read_input_tokens`) and bill them through `compute_cost` with Anthropic's 5-min ephemeral multipliers: write = 1.25x base input rate, read = 0.1x. The `input_tokens` reported on `UsageComplete` is the total billable input (uncached + write + read) so dashboards stay coherent. Cost is computed from the breakdown.

## Rationale

Cost math on Opus 4.7, cached prefix ~1290 tok, uncached input per call ~200 tok:

- Call 1 (cache write): `(200 + 1290*1.25) * $15/M = $0.0272`
- Call 2+ (cache read): `(200 + 1290*0.1) * $15/M = $0.0049`

Break-even at 2 calls in the 5-min window (which a real session always hits). Steady-state savings on the cached portion are ~87%. Cached reads also skip re-processing through the model's input layers, so TTFT drops on calls 2+ — caching is a latency win, not just cost.

The 1024-token minimum prefix (2048 for Haiku) is why the preceding commit enriched the system prompt: at ~700 tokens it was below threshold and `cache_control` would have been a silent no-op.

## Canary

1. **`usage.cache_read_input_tokens` stays at 0 across a multi-call Claude session** → the cached prefix fell below the 1024-token minimum (e.g. system prompt was trimmed). Re-measure `len(SYSTEM_PROMPT) + tool_schema` in tokens; target >= 1100 for margin.
2. **Anthropic 400 mentioning `cache_control` shape** → SDK contract changed. Re-check the current block shape via `mcp__context7__query-docs` on `/anthropics/anthropic-sdk-python`.
3. **Cost per decision in `decisions.cost_usd` does not drop vs pre-caching baseline on Claude presets** → either (1) or (2) above, or the multipliers in `pricing.py` drifted from Anthropic's published rates.

## Implementing commits

- `<pending>` — enrich system prompt past 1024-token threshold
- `<pending>` — cache_control on system, parse cache tokens, cost multipliers
