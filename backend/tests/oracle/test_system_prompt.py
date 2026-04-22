from poker_coach.oracle.system_prompt import (
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_V2,
    SYSTEM_PROMPT_V3,
    system_prompt_for,
)


def test_v2_keeps_never_randomize_instruction() -> None:
    assert "Never randomize" in SYSTEM_PROMPT_V2


def test_v3_drops_never_randomize_instruction() -> None:
    assert "Never randomize" not in SYSTEM_PROMPT_V3
    assert "Never output two actions" not in SYSTEM_PROMPT_V3


def test_v3_instructs_mixed_strategy_output() -> None:
    # v3 replaces "pick one deterministically" with solver-style framing.
    assert "mixed strategy" in SYSTEM_PROMPT_V3.lower()


def test_system_prompt_for_dispatch() -> None:
    assert system_prompt_for("v2") is SYSTEM_PROMPT_V2
    assert system_prompt_for("v3") is SYSTEM_PROMPT_V3
    # v1 is the legacy single-verdict prompt pack — treat like v2.
    assert system_prompt_for("v1") is SYSTEM_PROMPT_V2


def test_legacy_alias_still_exported() -> None:
    # Historical imports (`from ... import SYSTEM_PROMPT`) must keep working
    # until every caller is migrated. It points at v2.
    assert SYSTEM_PROMPT is SYSTEM_PROMPT_V2


def test_v2_contains_short_stack_push_fold_band() -> None:
    # Core sub-25bb guidance must be explicit — LLM must not improvise.
    assert "push/fold" in SYSTEM_PROMPT_V2.lower() or "jam/fold" in SYSTEM_PROMPT_V2.lower()
    assert "10bb" in SYSTEM_PROMPT_V2
    assert "limp" in SYSTEM_PROMPT_V2.lower()


def test_v3_contains_short_stack_push_fold_band() -> None:
    assert "push/fold" in SYSTEM_PROMPT_V3.lower() or "jam/fold" in SYSTEM_PROMPT_V3.lower()
    assert "10bb" in SYSTEM_PROMPT_V3


def test_prompts_reference_antes_in_sizing() -> None:
    for prompt in (SYSTEM_PROMPT_V2, SYSTEM_PROMPT_V3):
        assert "ante" in prompt.lower()


def test_prompts_contain_icm_framework() -> None:
    for prompt in (SYSTEM_PROMPT_V2, SYSTEM_PROMPT_V3):
        assert "ICM" in prompt
        assert "payout" in prompt.lower()


def test_v3_system_prompt_stays_above_anthropic_cache_threshold() -> None:
    """Anthropic caching requires >=1024 input tokens on Sonnet/Opus, >=2048 on
    Haiku. Below threshold, `cache_control` is a silent no-op. 3.5 chars/token is
    a conservative average for English prose → assert >= 1024 * 3.5 = 3584 chars.

    If this fails after trimming the prompt, either re-expand the prompt or
    explicitly decide to drop caching for v3 (update CLAUDE.md gotcha #8).
    """
    min_chars = 3584
    assert len(SYSTEM_PROMPT_V3) >= min_chars, (
        f"SYSTEM_PROMPT_V3 is {len(SYSTEM_PROMPT_V3)} chars; "
        f"below {min_chars} risks silently disabling Anthropic caching "
        f"(see CLAUDE.md gotcha #8)"
    )


def test_v2_system_prompt_stays_above_anthropic_cache_threshold() -> None:
    min_chars = 3584
    assert len(SYSTEM_PROMPT_V2) >= min_chars, (
        f"SYSTEM_PROMPT_V2 is {len(SYSTEM_PROMPT_V2)} chars; "
        f"below {min_chars} risks silently disabling Anthropic caching"
    )
