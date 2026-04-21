"""add payout_structure + blind_level_label to sessions

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # payout_structure: [0.65, 0.35] for HU SnG, [0.5, 0.3, 0.2] for 3-max, etc.
    # Nullable — live/cash sessions can skip ICM entirely.
    op.add_column("sessions", sa.Column("payout_structure", sa.JSON(), nullable=True))
    # Free-form label like "50/100 + 100 ante (lvl 8)"; display only.
    op.add_column("sessions", sa.Column("blind_level_label", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "blind_level_label")
    op.drop_column("sessions", "payout_structure")
