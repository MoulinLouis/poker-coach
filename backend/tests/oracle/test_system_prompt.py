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


def test_system_prompt_reasoning_budget_is_two_sentences() -> None:
    assert "2 sentences" in SYSTEM_PROMPT
    assert "40-60 words" in SYSTEM_PROMPT


def test_system_prompt_forbids_markdown_in_reasoning() -> None:
    # The output contract must explicitly ban the formatting that made v2's
    # first batch of advice hard to scan (headers, bold, bullets).
    assert "No headers" in SYSTEM_PROMPT
    assert "no markdown" in SYSTEM_PROMPT
