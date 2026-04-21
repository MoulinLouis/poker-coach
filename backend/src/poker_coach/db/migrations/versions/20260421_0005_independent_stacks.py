"""add hero_stack_start + villain_stack_start to hands

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # New columns nullable for back-compat with rows that only have
    # effective_stack_start. New hands always write both.
    op.add_column("hands", sa.Column("hero_stack_start", sa.Integer(), nullable=True))
    op.add_column("hands", sa.Column("villain_stack_start", sa.Integer(), nullable=True))
    # Backfill historical rows from effective_stack_start (both seats equal).
    op.execute(
        "UPDATE hands SET hero_stack_start = effective_stack_start, "
        "villain_stack_start = effective_stack_start "
        "WHERE hero_stack_start IS NULL"
    )


def downgrade() -> None:
    op.drop_column("hands", "villain_stack_start")
    op.drop_column("hands", "hero_stack_start")
