"""add hands.ante column

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # BB-ante, one ante size per hand. Default 0 keeps pre-tournament hands working.
    op.add_column(
        "hands",
        sa.Column("ante", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("hands", "ante")
