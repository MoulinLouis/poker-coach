from pathlib import Path

import pytest

from poker_coach.prompts.renderer import (
    PromptMetadataError,
    PromptRenderer,
    PromptVariableError,
)
from poker_coach.settings import PROMPTS_ROOT


@pytest.fixture
def temp_renderer(tmp_path: Path) -> PromptRenderer:
    return PromptRenderer(prompts_root=tmp_path)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_load_and_render_minimal(tmp_path: Path, temp_renderer: PromptRenderer) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v1\nvariables: [who]\n---\nHello {{ who }}!\n",
    )
    rendered = temp_renderer.render("mini", "v1", {"who": "world"})
    assert rendered.pack == "mini"
    assert rendered.version == "v1"
    assert rendered.rendered_prompt.strip() == "Hello world!"
    assert rendered.template_raw.startswith("---\n")
    assert len(rendered.template_hash) == 64


def test_template_hash_changes_with_file_bytes(tmp_path: Path) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v1\nvariables: [who]\n---\nHello {{ who }}!\n",
    )
    r = PromptRenderer(tmp_path)
    h1 = r.load("mini", "v1").template_hash

    (tmp_path / "mini" / "v1.md").write_text(
        "---\nname: mini\nversion: v1\nvariables: [who]\n---\nHi {{ who }}.\n"
    )
    h2 = r.load("mini", "v1").template_hash
    assert h1 != h2


def test_missing_variable_rejected(tmp_path: Path, temp_renderer: PromptRenderer) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v1\nvariables: [a, b]\n---\n{{ a }} {{ b }}\n",
    )
    with pytest.raises(PromptVariableError, match="missing"):
        temp_renderer.render("mini", "v1", {"a": 1})


def test_extra_variable_rejected(tmp_path: Path, temp_renderer: PromptRenderer) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v1\nvariables: [a]\n---\n{{ a }}\n",
    )
    with pytest.raises(PromptVariableError, match="unexpected"):
        temp_renderer.render("mini", "v1", {"a": 1, "b": 2})


def test_body_references_undeclared_variable(tmp_path: Path, temp_renderer: PromptRenderer) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v1\nvariables: [a]\n---\n{{ a }} {{ b }}\n",
    )
    with pytest.raises(PromptVariableError, match="undeclared"):
        temp_renderer.render("mini", "v1", {"a": 1})


def test_frontmatter_name_mismatch_rejected(tmp_path: Path, temp_renderer: PromptRenderer) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: wrong\nversion: v1\nvariables: []\n---\nhi\n",
    )
    with pytest.raises(PromptMetadataError, match="name"):
        temp_renderer.load("mini", "v1")


def test_frontmatter_version_mismatch_rejected(
    tmp_path: Path, temp_renderer: PromptRenderer
) -> None:
    _write(
        tmp_path / "mini" / "v1.md",
        "---\nname: mini\nversion: v9\nvariables: []\n---\nhi\n",
    )
    with pytest.raises(PromptMetadataError, match="version"):
        temp_renderer.load("mini", "v1")


def test_coach_v1_renders_against_sample_state() -> None:
    """Smoke test: the shipped coach prompt renders without errors from a
    fresh GameState projection.
    """
    from poker_coach.engine.rules import start_hand
    from poker_coach.prompts.context import state_to_coach_variables

    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render("coach", "v1", state_to_coach_variables(state))
    assert "As Kd" in rendered.rendered_prompt
    assert "submit_advice" in rendered.rendered_prompt
    assert "fold" in rendered.rendered_prompt  # in legal actions


def test_coach_v2_renders_against_sample_state() -> None:
    """Smoke test: coach v2 renders cleanly with villain_profile included."""
    from poker_coach.analytics import VillainStats
    from poker_coach.engine.rules import start_hand
    from poker_coach.prompts.context import state_to_coach_variables

    state = start_hand(
        effective_stack=10_000,
        bb=100,
        button="hero",
        hero_hole=("As", "Kd"),
        villain_hole=("Qc", "Qh"),
    )
    renderer = PromptRenderer(PROMPTS_ROOT)
    rendered = renderer.render(
        "coach",
        "v2",
        state_to_coach_variables(
            state,
            villain_profile="reg",
            villain_stats=VillainStats.zero().as_prompt_payload(),
        ),
    )
    assert "As Kd" in rendered.rendered_prompt
    assert "reg" in rendered.rendered_prompt
    # v2 no longer carries the strategic intro paragraph — it lives in system prompt.
    assert "Your job: evaluate" not in rendered.rendered_prompt
