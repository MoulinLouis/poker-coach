"""add villain_profile + system_prompt snapshot columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "villain_profile",
            sa.String(16),
            nullable=False,
            server_default="unknown",
        ),
    )
    # System prompt + hash are nullable: historical rows have no
    # system prompt snapshot. New rows always write both.
    op.add_column("decisions", sa.Column("system_prompt", sa.Text(), nullable=True))
    op.add_column("decisions", sa.Column("system_prompt_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "system_prompt_hash")
    op.drop_column("decisions", "system_prompt")
    op.drop_column("decisions", "villain_profile")
