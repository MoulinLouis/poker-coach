"""Registry of (provider, model, effort) presets exposed in the UI selector.

Adding a new selector option = one entry here. Deliberately a preset
registry rather than a model x effort matrix — the cross product has
rows nobody would select and creates configuration surface for no
benefit.
"""

from poker_coach.oracle.base import ModelSpec

MODEL_PRESETS: dict[str, ModelSpec] = {
    "gpt-5.3-codex-xhigh": ModelSpec(
        selector_id="gpt-5.3-codex-xhigh",
        provider="openai",
        model_id="gpt-5.3-codex",
        reasoning_effort="xhigh",
    ),
    "gpt-5.4-medium": ModelSpec(
        selector_id="gpt-5.4-medium",
        provider="openai",
        model_id="gpt-5.4",
        reasoning_effort="medium",
    ),
    "claude-opus-4-7-deep": ModelSpec(
        selector_id="claude-opus-4-7-deep",
        provider="anthropic",
        model_id="claude-opus-4-7",
        thinking_mode="adaptive",
        reasoning_effort="high",
        temperature=1.0,
    ),
    # Sonnet 4.6 runs *without* thinking: observed cost at
    # thinking_budget=4096 was ~$0.028/call (output dominated by thinking
    # tokens billed at output rate). Dropping thinking cuts output ~95%
    # and unlocks forced tool_choice for reliability. The enriched
    # system prompt carries enough strategic frame that Sonnet in one
    # forward pass matches the thinking version on routine spots;
    # borderline spots may degrade but the cost/latency delta is large
    # enough to justify it as the standard Claude option.
    "claude-sonnet-4-6-fast": ModelSpec(
        selector_id="claude-sonnet-4-6-fast",
        provider="anthropic",
        model_id="claude-sonnet-4-6",
    ),
    # Haiku also runs without thinking. Anthropic forbids tool_choice
    # forcing when thinking is enabled, and Haiku with tool_choice=auto
    # is flaky about actually calling the tool. No thinking → forced
    # tool_choice → reliable structured output.
    "claude-haiku-4-5-min": ModelSpec(
        selector_id="claude-haiku-4-5-min",
        provider="anthropic",
        model_id="claude-haiku-4-5-20251001",
        thinking_budget=None,
        temperature=None,
    ),
}

DEFAULT_PRESET_ID = "gpt-5.3-codex-xhigh"
