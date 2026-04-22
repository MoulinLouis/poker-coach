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


def test_populated_downgrade_then_upgrade_preserves_data_0004_to_0006(
    alembic_cfg: tuple[Config, str],
) -> None:
    """Run upgrade to head, insert a row that uses columns added by migrations
    0004 (hands.ante), 0005 (hero/villain_stack_start), 0006 (payout_structure,
    blind_level_label), then downgrade to 0003 and back up to head. Columns
    added along the way should be dropped and recreated cleanly."""
    from sqlalchemy import text

    cfg, url = alembic_cfg
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.begin() as conn:
        # Insert session + hand using the new columns.
        conn.execute(
            text(
                "INSERT INTO sessions (session_id, mode, payout_structure, blind_level_label) "
                "VALUES (:sid, 'live', :payouts, :label)"
            ),
            {"sid": "sess-1", "payouts": "[0.65, 0.35]", "label": "50/100"},
        )
        conn.execute(
            text(
                "INSERT INTO hands (hand_id, session_id, bb, effective_stack_start, "
                "hero_stack_start, villain_stack_start, ante) "
                "VALUES (:hid, :sid, 100, 10000, 10000, 10000, 50)"
            ),
            {"hid": "hand-1", "sid": "sess-1"},
        )

    # Downgrade to 0003 — this must drop payout_structure, blind_level_label,
    # hero/villain_stack_start, and ante. Data in remaining columns should
    # survive.
    command.downgrade(cfg, "0003")

    engine = create_engine(url)
    inspector = inspect(engine)
    session_cols = {c["name"] for c in inspector.get_columns("sessions")}
    hands_cols = {c["name"] for c in inspector.get_columns("hands")}
    assert "payout_structure" not in session_cols
    assert "blind_level_label" not in session_cols
    assert "hero_stack_start" not in hands_cols
    assert "villain_stack_start" not in hands_cols
    assert "ante" not in hands_cols

    # Pre-existing row should still be there with its bb and effective_stack_start.
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT bb, effective_stack_start FROM hands WHERE hand_id = 'hand-1'")
        ).one()
    assert row.bb == 100
    assert row.effective_stack_start == 10_000

    # Upgrade back to head — columns should reappear.
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    inspector = inspect(engine)
    session_cols_after = {c["name"] for c in inspector.get_columns("sessions")}
    hands_cols_after = {c["name"] for c in inspector.get_columns("hands")}
    assert {"payout_structure", "blind_level_label"} <= session_cols_after
    assert {"hero_stack_start", "villain_stack_start", "ante"} <= hands_cols_after
