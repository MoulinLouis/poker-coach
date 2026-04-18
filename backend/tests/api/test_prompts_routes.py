from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def _write_prompt(root: Path, pack: str, version: str, body_text: str) -> None:
    pack_dir = root / pack
    pack_dir.mkdir(parents=True, exist_ok=True)
    content = (
        f"---\nname: {pack}\nversion: {version}\ndescription: test\n"
        f"variables:\n  - who\n---\n{body_text}"
    )
    (pack_dir / f"{version}.md").write_text(content)


def test_list_packs_and_versions(api_app: Any, tmp_path: Path, migrated_engine: Any) -> None:
    # Override prompts_root via app.state override is awkward with fastapi;
    # instead re-build the app pointing at tmp_path.
    from poker_coach.api.app import create_app
    from poker_coach.api.deps import OracleFactory
    from poker_coach.oracle.base import ModelSpec, Oracle
    from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot

    class _Dummy(OracleFactory):
        def for_spec(self, spec: ModelSpec) -> Oracle:
            raise AssertionError("not used")

    _write_prompt(tmp_path, "coach", "v1", "Hello {{ who }}")
    _write_prompt(tmp_path, "coach", "v2", "Hi {{ who }}")
    app = create_app(
        engine=migrated_engine,
        oracle_factory=_Dummy(),
        pricing=PricingSnapshot(
            snapshot_date="2026-04-18",
            snapshot_source="test",
            models={"m": PricingEntry(input_per_mtok=1.0, output_per_mtok=1.0)},
        ),
        prompts_root=tmp_path,
        sweeper_interval_seconds=0,
    )
    with TestClient(app) as client:
        resp = client.get("/api/prompts")
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "coach"
    versions = [v["version"] for v in body[0]["versions"]]
    assert versions == ["v1", "v2"]


def test_get_prompt_returns_content(api_app: Any, tmp_path: Path, migrated_engine: Any) -> None:
    from poker_coach.api.app import create_app
    from poker_coach.api.deps import OracleFactory
    from poker_coach.oracle.base import ModelSpec, Oracle
    from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot

    class _Dummy(OracleFactory):
        def for_spec(self, spec: ModelSpec) -> Oracle:
            raise AssertionError("not used")

    _write_prompt(tmp_path, "coach", "v1", "Hello {{ who }}")
    app = create_app(
        engine=migrated_engine,
        oracle_factory=_Dummy(),
        pricing=PricingSnapshot(
            snapshot_date="x",
            snapshot_source="x",
            models={"m": PricingEntry(input_per_mtok=1.0, output_per_mtok=1.0)},
        ),
        prompts_root=tmp_path,
        sweeper_interval_seconds=0,
    )
    with TestClient(app) as client:
        resp = client.get("/api/prompts/coach/v1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["declared_variables"] == ["who"]
    assert "Hello {{ who }}" in body["template_raw"]


def test_save_new_version(api_app: Any, tmp_path: Path, migrated_engine: Any) -> None:
    from poker_coach.api.app import create_app
    from poker_coach.api.deps import OracleFactory
    from poker_coach.oracle.base import ModelSpec, Oracle
    from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot

    class _Dummy(OracleFactory):
        def for_spec(self, spec: ModelSpec) -> Oracle:
            raise AssertionError("not used")

    _write_prompt(tmp_path, "coach", "v1", "Hello {{ who }}")
    app = create_app(
        engine=migrated_engine,
        oracle_factory=_Dummy(),
        pricing=PricingSnapshot(
            snapshot_date="x",
            snapshot_source="x",
            models={"m": PricingEntry(input_per_mtok=1.0, output_per_mtok=1.0)},
        ),
        prompts_root=tmp_path,
        sweeper_interval_seconds=0,
    )
    content = (
        "---\nname: coach\nversion: v2\ndescription: tweaked\n"
        "variables:\n  - who\n---\nHowdy {{ who }}"
    )
    with TestClient(app) as client:
        resp = client.post("/api/prompts/coach", json={"version": "v2", "content": content})
    assert resp.status_code == 200, resp.text
    assert (tmp_path / "coach" / "v2.md").exists()


def test_save_refuses_existing_version(api_app: Any, tmp_path: Path, migrated_engine: Any) -> None:
    from poker_coach.api.app import create_app
    from poker_coach.api.deps import OracleFactory
    from poker_coach.oracle.base import ModelSpec, Oracle
    from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot

    class _Dummy(OracleFactory):
        def for_spec(self, spec: ModelSpec) -> Oracle:
            raise AssertionError("not used")

    _write_prompt(tmp_path, "coach", "v1", "Hello {{ who }}")
    app = create_app(
        engine=migrated_engine,
        oracle_factory=_Dummy(),
        pricing=PricingSnapshot(
            snapshot_date="x",
            snapshot_source="x",
            models={"m": PricingEntry(input_per_mtok=1.0, output_per_mtok=1.0)},
        ),
        prompts_root=tmp_path,
        sweeper_interval_seconds=0,
    )
    content = (
        "---\nname: coach\nversion: v1\ndescription: collide\n"
        "variables:\n  - who\n---\nHi {{ who }}"
    )
    with TestClient(app) as client:
        resp = client.post("/api/prompts/coach", json={"version": "v1", "content": content})
    assert resp.status_code == 409


def test_save_rejects_invalid_template(api_app: Any, tmp_path: Path, migrated_engine: Any) -> None:
    from poker_coach.api.app import create_app
    from poker_coach.api.deps import OracleFactory
    from poker_coach.oracle.base import ModelSpec, Oracle
    from poker_coach.oracle.pricing import PricingEntry, PricingSnapshot

    class _Dummy(OracleFactory):
        def for_spec(self, spec: ModelSpec) -> Oracle:
            raise AssertionError("not used")

    app = create_app(
        engine=migrated_engine,
        oracle_factory=_Dummy(),
        pricing=PricingSnapshot(
            snapshot_date="x",
            snapshot_source="x",
            models={"m": PricingEntry(input_per_mtok=1.0, output_per_mtok=1.0)},
        ),
        prompts_root=tmp_path,
        sweeper_interval_seconds=0,
    )
    # version in frontmatter mismatches the POST version → renderer rejects.
    content = "---\nname: coach\nversion: v9\nvariables:\n  - who\n---\nHi {{ who }}"
    with TestClient(app) as client:
        resp = client.post("/api/prompts/coach", json={"version": "v1", "content": content})
    assert resp.status_code == 400
    # File should have been cleaned up.
    assert not (tmp_path / "coach" / "v1.md").exists()
