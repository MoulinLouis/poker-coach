# Model strategy — GPT-5.3-codex primary, Claude secondary

## Context

The original design doc called for Claude Opus 4.7 as the primary model with GPT and Gemini deferred to "phase 2". Pricing analysis (owner's own data) revealed GPT-5.3-codex at `reasoning_effort=xhigh` delivered comparable quality at ~82% lower cost per decision (~$0.06 vs ~$0.33 for a typical spot). A published benchmark (-16 bb/100 vs GTO Wizard) also favored it.

## Decision

`gpt-5.3-codex-xhigh` is the default preset. Multi-provider oracle from day one, not a future phase. Claude Opus 4.7 and Sonnet 4.6 stay in the selector for qualitative comparison. Haiku 4.5 fills the cheap/fast exploration slot.

## Rationale

The research use case (many decisions, prompt iteration) is cost-sensitive. Paying 5× for Opus only pays off for depth that Haiku and GPT-5.3 can't match — which remains to be demonstrated. Cheaper primary + selective Opus runs for comparison is strictly better economics.

## Canary

`MODEL_PRESETS` in `backend/src/poker_coach/oracle/presets.py` should carry exactly these four selector_ids: `gpt-5.3-codex-xhigh`, `gpt-5.4-medium`, `claude-opus-4-7-deep`, `claude-sonnet-4-6-medium`, `claude-haiku-4-5-min`. `DEFAULT_PRESET_ID == "gpt-5.3-codex-xhigh"`. If you change the default, update this ADR.

## Implementing commits

- `b0ec4f0` — oracle presets + tool schema
- `3dfaf33` — add Sonnet 4.6 preset
- `9fb05d2` — Haiku runs without thinking
