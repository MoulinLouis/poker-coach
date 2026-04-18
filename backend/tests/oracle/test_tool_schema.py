from poker_coach.oracle.tool_schema import (
    anthropic_tool_spec,
    openai_tool_spec,
)


def test_anthropic_spec_structure() -> None:
    spec = anthropic_tool_spec()
    assert spec["name"] == "submit_advice"
    schema = spec["input_schema"]
    assert schema["type"] == "object"
    props = schema["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert props["action"]["enum"] == ["fold", "check", "call", "bet", "raise", "allin"]
    assert props["confidence"]["enum"] == ["low", "medium", "high"]
    # to_amount_bb is optional in Anthropic dialect
    assert schema["required"] == ["action", "reasoning", "confidence"]
    # Permissive: no additionalProperties clause
    assert "additionalProperties" not in schema


def test_openai_spec_structure() -> None:
    spec = openai_tool_spec()
    assert spec["type"] == "function"
    assert spec["name"] == "submit_advice"
    assert spec["strict"] is True
    params = spec["parameters"]
    # Strict mode demands additionalProperties: false
    assert params["additionalProperties"] is False
    # Strict mode demands every property in required
    assert set(params["required"]) == {"action", "to_amount_bb", "reasoning", "confidence"}
    # Optional fields are nullable-typed
    assert params["properties"]["to_amount_bb"]["type"] == ["number", "null"]


def test_specs_share_semantic_schema() -> None:
    """Both specs describe the same four fields with the same enums.

    The dialect differences (strict, additionalProperties, nullable vs optional)
    are the only divergence.
    """
    a_props = anthropic_tool_spec()["input_schema"]["properties"]
    o_props = openai_tool_spec()["parameters"]["properties"]
    assert set(a_props) == set(o_props) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert a_props["action"]["enum"] == o_props["action"]["enum"]
    assert a_props["confidence"]["enum"] == o_props["confidence"]["enum"]
