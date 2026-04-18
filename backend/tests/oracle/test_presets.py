from poker_coach.oracle.presets import DEFAULT_PRESET_ID, MODEL_PRESETS


def test_default_is_in_registry() -> None:
    assert DEFAULT_PRESET_ID in MODEL_PRESETS


def test_selector_ids_match_keys() -> None:
    for key, spec in MODEL_PRESETS.items():
        assert spec.selector_id == key


def test_provider_configuration_is_consistent() -> None:
    """Per-provider invariants:

    - OpenAI: reasoning_effort set, thinking_* unused.
    - Anthropic with thinking_mode="enabled": needs a thinking_budget.
    - Anthropic with thinking_mode="adaptive": needs a reasoning_effort.
    - Anthropic with thinking_mode=None: no thinking at all.
    """
    for spec in MODEL_PRESETS.values():
        if spec.provider == "openai":
            assert spec.reasoning_effort is not None, spec.selector_id
            assert spec.thinking_budget is None, spec.selector_id
            assert spec.thinking_mode is None, spec.selector_id
            continue

        if spec.thinking_mode == "enabled":
            assert spec.thinking_budget is not None, spec.selector_id
            assert spec.reasoning_effort is None, spec.selector_id
        elif spec.thinking_mode == "adaptive":
            assert spec.reasoning_effort is not None, spec.selector_id
            assert spec.thinking_budget is None, spec.selector_id
        else:
            assert spec.thinking_mode is None, spec.selector_id
            assert spec.thinking_budget is None, spec.selector_id
            assert spec.reasoning_effort is None, spec.selector_id
