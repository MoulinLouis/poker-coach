# tool_choice + thinking — auto only, system prompt enforces

## Context

Two desires that conflict on Anthropic:

1. Use extended thinking for quality reasoning.
2. Guarantee the model emits a structured `submit_advice` tool call, not prose.

`tool_choice={"type":"tool","name":"..."}` is the standard way to force a tool. But Anthropic rejects it when thinking is on:

> `Thinking may not be enabled when tool_choice forces tool use.`

And with `tool_choice={"type":"auto"}`, thinking-heavy models (especially with verbose responses) tend to narrate their conclusion in a text block instead of calling the tool — leading to "no tool_use block in response" errors.

## Decision

- **No thinking** (Haiku preset): use `tool_choice={"type":"tool","name":"submit_advice"}`. Forced tool use is reliable.
- **Thinking on** (Sonnet, Opus): use `tool_choice={"type":"auto"}` + a short, strict system prompt that explicitly forbids text-only responses. System prompt carries more weight than inline instructions for behavioral constraints.

The system prompt (`_SYSTEM_ENFORCE_TOOL` in `backend/src/poker_coach/oracle/anthropic_oracle.py`): "YOUR ONLY VISIBLE OUTPUT MUST BE A SINGLE CALL TO `submit_advice`. Do not reply with a text block. Do not narrate your conclusion. …"

## Rationale

Haiku 4.5 with `tool_choice=auto` is particularly flaky — it prefers prose. Dropping thinking on Haiku is cheap (Haiku is the fast-and-cheap slot) and restores forced tool use, which the API rate-limits on compliance. For models where thinking is the reason we're using them, the system-prompt route trades a small probabilistic failure mode for the depth gain. If it still regresses, escalate to the `interleaved-thinking-2025-05-14` beta header (would allow forced tool_choice with thinking); untested here.

## Canary

- Error `Thinking may not be enabled when tool_choice forces tool use.` → someone changed the thinking branch to use forced tool_choice. Revert to auto.
- Repeated `OracleError(kind="invalid_schema", message="no tool_use block in response")` from Anthropic only → system prompt isn't holding. Try (a) strengthening it, (b) the interleaved-thinking beta, (c) dropping thinking for that preset.

## Implementing commits

- `7d121ea` — tool_choice=auto with thinking
- `9fb05d2` — Haiku no-thinking for forced tool_choice
- `5ce638f` — system prompt enforces tool call
