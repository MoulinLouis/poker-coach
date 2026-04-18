"""Shared submit_advice tool schema and provider-specific normalizers.

The same logical schema is emitted as two dialect variants:

- Anthropic Messages: permissive JSON Schema via `input_schema`.
- OpenAI Responses: strict mode (`additionalProperties: false`,
  all properties in `required`, nullable-typed optionals).

Hand-written rather than auto-derived so we own the exact wire shape.
A fixture snapshot test catches drift between the two.
"""

from __future__ import annotations

from typing import Any

TOOL_NAME = "submit_advice"
TOOL_DESCRIPTION = (
    "Submit the final recommendation for the hero's action. Call this exactly once "
    "when you have a conclusion. action must be one of the legal types the prompt "
    "listed; to_amount_bb is required for bet and raise, omitted otherwise; "
    "reasoning is a concise (<=200 word) explanation; confidence is self-assessed."
)

_ACTION_ENUM = ["fold", "check", "call", "bet", "raise", "allin"]
_CONFIDENCE_ENUM = ["low", "medium", "high"]


def anthropic_tool_spec() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
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


def openai_tool_spec() -> dict[str, Any]:
    return {
        "type": "function",
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
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
