from poker_coach.oracle.tool_schema import (
    anthropic_tool_spec,
    openai_tool_spec,
)

# ---------- v2 (legacy) shape ----------


def test_anthropic_v2_structure() -> None:
    spec = anthropic_tool_spec("v2")
    assert spec["name"] == "submit_advice"
    schema = spec["input_schema"]
    props = schema["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert props["action"]["enum"] == ["fold", "check", "call", "bet", "raise", "allin"]
    assert props["confidence"]["enum"] == ["low", "medium", "high"]
    assert schema["required"] == ["action", "reasoning", "confidence"]
    assert "additionalProperties" not in schema


def test_openai_v2_structure() -> None:
    spec = openai_tool_spec("v2")
    assert spec["strict"] is True
    params = spec["parameters"]
    assert params["additionalProperties"] is False
    assert set(params["required"]) == {"action", "to_amount_bb", "reasoning", "confidence"}
    assert params["properties"]["to_amount_bb"]["type"] == ["number", "null"]


def test_v1_emits_same_shape_as_v2() -> None:
    assert anthropic_tool_spec("v1") == anthropic_tool_spec("v2")
    assert openai_tool_spec("v1") == openai_tool_spec("v2")


# ---------- v3 (mixed strategy) shape ----------


def test_anthropic_v3_adds_strategy_and_relaxes_required() -> None:
    spec = anthropic_tool_spec("v3")
    schema = spec["input_schema"]
    props = schema["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence", "strategy"}
    # In v3, action/to_amount_bb are derived server-side — no longer required.
    assert set(schema["required"]) == {"strategy", "reasoning", "confidence"}
    strat = props["strategy"]
    assert strat["type"] == "array"
    item = strat["items"]
    assert item["type"] == "object"
    item_props = item["properties"]
    assert set(item_props) == {"action", "to_amount_bb", "frequency"}
    assert item_props["action"]["enum"] == ["fold", "check", "call", "bet", "raise", "allin"]
    assert item_props["frequency"]["type"] == "number"
    assert set(item["required"]) == {"action", "to_amount_bb", "frequency"}


def test_openai_v3_strict_adds_strategy() -> None:
    spec = openai_tool_spec("v3")
    params = spec["parameters"]
    assert params["additionalProperties"] is False
    props = params["properties"]
    assert set(props) == {"action", "to_amount_bb", "reasoning", "confidence", "strategy"}
    # OpenAI strict mode: every property in required, optionals are nullable.
    assert set(params["required"]) == {
        "action",
        "to_amount_bb",
        "reasoning",
        "confidence",
        "strategy",
    }
    assert props["action"]["type"] == ["string", "null"]
    assert props["to_amount_bb"]["type"] == ["number", "null"]

    strat = props["strategy"]
    assert strat["type"] == "array"
    item = strat["items"]
    assert item["additionalProperties"] is False
    item_props = item["properties"]
    assert set(item_props) == {"action", "to_amount_bb", "frequency"}
    assert item_props["to_amount_bb"]["type"] == ["number", "null"]
    assert set(item["required"]) == {"action", "to_amount_bb", "frequency"}


def test_v3_specs_share_strategy_shape() -> None:
    a_strat = anthropic_tool_spec("v3")["input_schema"]["properties"]["strategy"]
    o_strat = openai_tool_spec("v3")["parameters"]["properties"]["strategy"]
    a_items = a_strat["items"]["properties"]
    o_items = o_strat["items"]["properties"]
    assert set(a_items) == set(o_items) == {"action", "to_amount_bb", "frequency"}
    assert a_items["action"]["enum"] == o_items["action"]["enum"]
