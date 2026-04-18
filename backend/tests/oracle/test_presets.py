from poker_coach.oracle.presets import DEFAULT_PRESET_ID, MODEL_PRESETS


def test_default_is_in_registry() -> None:
    assert DEFAULT_PRESET_ID in MODEL_PRESETS


def test_selector_ids_match_keys() -> None:
    for key, spec in MODEL_PRESETS.items():
        assert spec.selector_id == key


def test_every_preset_has_exactly_one_effort_signal() -> None:
    """OpenAI presets use reasoning_effort; Anthropic presets use thinking_budget.
    Either-or, not both.
    """
    for spec in MODEL_PRESETS.values():
        has_effort = spec.reasoning_effort is not None
        has_budget = spec.thinking_budget is not None
        assert has_effort ^ has_budget, f"{spec.selector_id} must have exactly one of the two"
        if spec.provider == "openai":
            assert has_effort
        else:
            assert has_budget
