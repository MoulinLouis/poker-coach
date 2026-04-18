from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from poker_coach.db.tables import metadata


@pytest.fixture
def alembic_cfg(tmp_path: Path) -> tuple[Config, str]:
    """Isolated alembic config pointing at a throwaway SQLite DB."""
    db_file = tmp_path / "test.db"
    url = f"sqlite:///{db_file}"
    backend_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "src/poker_coach/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg, url


def test_upgrade_head_creates_all_tables(alembic_cfg: tuple[Config, str]) -> None:
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert {"sessions", "hands", "decisions", "actual_actions"} <= table_names


def test_upgrade_matches_declared_metadata(alembic_cfg: tuple[Config, str]) -> None:
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    declared_tables = set(metadata.tables.keys())
    live_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert declared_tables == live_tables


def test_downgrade_then_upgrade_round_trips(alembic_cfg: tuple[Config, str]) -> None:
    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - {"alembic_version"} == set()
    command.upgrade(cfg, "head")
    inspector = inspect(engine)
    assert {"sessions", "hands", "decisions", "actual_actions"} <= set(inspector.get_table_names())
