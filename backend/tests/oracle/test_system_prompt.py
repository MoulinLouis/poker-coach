from poker_coach.oracle.system_prompt import SYSTEM_PROMPT


def test_system_prompt_mentions_both_villain_profiles() -> None:
    assert "`reg`" in SYSTEM_PROMPT
    assert "`unknown`" in SYSTEM_PROMPT


def test_system_prompt_enforces_tool_only_output() -> None:
    assert "submit_advice" in SYSTEM_PROMPT
    assert "ONLY VISIBLE OUTPUT" in SYSTEM_PROMPT


def test_system_prompt_documents_confidence_mapping() -> None:
    assert "`high`" in SYSTEM_PROMPT
    assert "`medium`" in SYSTEM_PROMPT
    assert "`low`" in SYSTEM_PROMPT


def test_system_prompt_reasoning_budget_is_150_words() -> None:
    assert "150 words" in SYSTEM_PROMPT or "<=150" in SYSTEM_PROMPT
