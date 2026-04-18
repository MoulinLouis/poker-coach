from poker_coach.oracle.presets import DEFAULT_PRESET_ID, MODEL_PRESETS


def test_default_is_in_registry() -> None:
    assert DEFAULT_PRESET_ID in MODEL_PRESETS


def test_selector_ids_match_keys() -> None:
    for key, spec in MODEL_PRESETS.items():
        assert spec.selector_id == key


def test_effort_signals_match_provider() -> None:
    """OpenAI presets always carry reasoning_effort. Anthropic presets may
    carry thinking_budget, or neither (Haiku runs without thinking so
    tool_choice can be forced — thinking+forced_tool is a 400 on the API).
    """
    for spec in MODEL_PRESETS.values():
        if spec.provider == "openai":
            assert spec.reasoning_effort is not None, spec.selector_id
            assert spec.thinking_budget is None, spec.selector_id
        else:
            assert spec.reasoning_effort is None, spec.selector_id
