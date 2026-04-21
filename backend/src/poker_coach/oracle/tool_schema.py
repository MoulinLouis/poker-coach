"""Shared submit_advice tool schema and provider-specific normalizers.

The same logical schema is emitted as two dialect variants:

- Anthropic Messages: permissive JSON Schema via `input_schema`.
- OpenAI Responses: strict mode (`additionalProperties: false`,
  all properties in `required`, nullable-typed optionals).

Two prompt-version shapes:

- v1 / v2: single deterministic verdict (action + optional to_amount_bb +
  reasoning + confidence).
- v3: adds `strategy` — a GTO-solver-style list of (action, to_amount_bb,
  frequency). `action` and `to_amount_bb` become server-derived (argmax of
  strategy) and are therefore no longer required on Anthropic; on OpenAI
  strict they stay in `required` but become nullable.

Hand-written rather than auto-derived so we own the exact wire shape.
Fixture snapshot tests catch drift between the two providers and between
versions.
"""

from __future__ import annotations

from typing import Any

TOOL_NAME = "submit_advice"

_TOOL_DESCRIPTION_V2 = (
    "Submit the final recommendation for the hero's action. Call this exactly once "
    "when you have a conclusion. action must be one of the legal types the prompt "
    "listed; to_amount_bb is required for bet and raise, omitted otherwise; "
    "reasoning is plain prose, exactly 2 sentences, 40-60 words total, no headers "
    "or markdown (sentence 1 = action + key reason; sentence 2 = next-street plan "
    "or tie-break exploit); confidence reflects mix closeness (high = dominant, "
    "medium = close, low = borderline)."
)

_TOOL_DESCRIPTION_V3 = (
    "Submit the hero's mixed strategy. Call this exactly once when you have a "
    "conclusion. `strategy` is the full GTO-style distribution: one entry per "
    "(action, sizing) you actually play at >= 5% frequency; frequencies sum to 1; "
    "rounded to 0.05 steps. For bet/raise you may include up to two sizings "
    "(polarized). `action` and `to_amount_bb` are derived server-side from the "
    "strategy argmax — you may leave them null. `reasoning` is 2 sentences, "
    "40-60 words; `confidence` reflects how close the top action is to its "
    "alternatives (high = dominant, medium = close, low = borderline)."
)

_ACTION_ENUM = ["fold", "check", "call", "bet", "raise", "allin"]
_CONFIDENCE_ENUM = ["low", "medium", "high"]


def anthropic_tool_spec(prompt_version: str) -> dict[str, Any]:
    if prompt_version == "v3":
        return _anthropic_v3()
    return _anthropic_v2()


def openai_tool_spec(prompt_version: str) -> dict[str, Any]:
    if prompt_version == "v3":
        return _openai_v3()
    return _openai_v2()


# ---------- v2 (legacy) ----------


def _anthropic_v2() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V2,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": _ACTION_ENUM},
                "to_amount_bb": {
                    "type": "number",
                    "description": "Sizing in BB; required for bet and raise.",
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
            },
            "required": ["action", "reasoning", "confidence"],
        },
    }


def _openai_v2() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V2,
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": "string", "enum": _ACTION_ENUM},
                "to_amount_bb": {
                    "type": ["number", "null"],
                    "description": "Sizing in BB; null unless action is bet or raise.",
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
            },
            "required": ["action", "to_amount_bb", "reasoning", "confidence"],
        },
    }


# ---------- v3 (mixed strategy) ----------


def _strategy_item_anthropic() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": _ACTION_ENUM},
            "to_amount_bb": {
                "type": ["number", "null"],
                "description": "Sizing in BB for bet/raise; null otherwise.",
            },
            "frequency": {"type": "number"},
        },
        "required": ["action", "to_amount_bb", "frequency"],
    }


def _strategy_item_openai() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "action": {"type": "string", "enum": _ACTION_ENUM},
            "to_amount_bb": {
                "type": ["number", "null"],
                "description": "Sizing in BB for bet/raise; null otherwise.",
            },
            "frequency": {"type": "number"},
        },
        "required": ["action", "to_amount_bb", "frequency"],
    }


def _anthropic_v3() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V3,
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": ["string", "null"],
                    "enum": [*_ACTION_ENUM, None],
                },
                "to_amount_bb": {"type": ["number", "null"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
                "strategy": {
                    "type": "array",
                    "items": _strategy_item_anthropic(),
                    "minItems": 1,
                },
            },
            "required": ["strategy", "reasoning", "confidence"],
        },
    }


def _openai_v3() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": _TOOL_DESCRIPTION_V3,
        "strict": True,
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "action": {"type": ["string", "null"], "enum": [*_ACTION_ENUM, None]},
                "to_amount_bb": {"type": ["number", "null"]},
                "reasoning": {"type": "string"},
                "confidence": {"type": "string", "enum": _CONFIDENCE_ENUM},
                "strategy": {
                    "type": "array",
                    "items": _strategy_item_openai(),
                },
            },
            "required": ["action", "to_amount_bb", "reasoning", "confidence", "strategy"],
        },
    }
