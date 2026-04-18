# Anthropic thinking API — two dispatches (enabled / adaptive)

## Context

Anthropic shipped a new thinking API shape for Opus 4.7. The legacy shape still works for Sonnet 4.6 / Haiku 4.5, but Opus 4.7 rejects it:

> `"thinking.type.enabled" is not supported for this model. Use "thinking.type.adaptive" and "output_config.effort" to control thinking behavior.`

## Decision

`ModelSpec.thinking_mode: Literal["enabled", "adaptive"] | None`. Anthropic presets declare their mode; the oracle branches:

| Mode | Request shape | Used by |
|---|---|---|
| `"enabled"` | `thinking={"type":"enabled","budget_tokens":N}`, `max_tokens > N + 2048` | Sonnet 4.6 (budget=4096) |
| `"adaptive"` | `thinking={"type":"adaptive"}` + `output_config={"effort": spec.reasoning_effort}`, `max_tokens=16384` | Opus 4.7 (effort="high") |
| `None` | no thinking params at all | Haiku 4.5 |

## Rationale

Opus 4.7's adaptive thinking lets the model self-pace effort. Sonnet 4.6 hasn't been upgraded to that shape yet; sending `adaptive` to it 400s back. Dispatch is the only safe path until all Anthropic models converge.

## Canary

- `ModelSpec.thinking_mode` presence + value matches the model. `backend/tests/oracle/test_presets.py::test_provider_configuration_is_consistent` enforces the field combinations.
- A 400 mentioning `thinking.type.enabled is not supported` means a new model was added to the `enabled` branch that should be `adaptive`. Move it.
- On `"enabled"`, **`max_tokens` must exceed `thinking.budget_tokens`** — otherwise 400 with `max_tokens must be greater than thinking.budget_tokens`. The oracle bumps `max_tokens = budget + 2048` defensively.

## Implementing commits

- `7d121ea` — use `tool_choice=auto` with thinking (pre-dispatch fix)
- `6fd5cc5` — bump `max_tokens` above thinking budget
- `e6b5f4f` — support Opus 4.7 adaptive thinking
