"""log schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-18

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(32), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "hands",
        sa.Column("hand_id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id", sa.String(32), sa.ForeignKey("sessions.session_id"), nullable=False
        ),
        sa.Column("bb", sa.Integer(), nullable=False),
        sa.Column("effective_stack_start", sa.Integer(), nullable=False),
        sa.Column("deck_snapshot", sa.JSON(), nullable=True),
        sa.Column("rng_seed", sa.Integer(), nullable=True),
        sa.Column("winner", sa.String(16), nullable=True),
        sa.Column("showdown_state", sa.JSON(), nullable=True),
    )
    op.create_index("ix_hands_session_id", "hands", ["session_id"])

    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.String(32), primary_key=True),
        sa.Column(
            "session_id", sa.String(32), sa.ForeignKey("sessions.session_id"), nullable=False
        ),
        sa.Column("hand_id", sa.String(32), sa.ForeignKey("hands.hand_id"), nullable=True),
        sa.Column("retry_of", sa.String(32), sa.ForeignKey("decisions.decision_id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column("stream_opened_at", sa.DateTime(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("game_state", sa.JSON(), nullable=False),
        sa.Column("prompt_name", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column("template_raw", sa.Text(), nullable=False),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("reasoning_effort", sa.String(16), nullable=True),
        sa.Column("thinking_budget", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("other_params", sa.JSON(), nullable=True),
        sa.Column("reasoning_text", sa.Text(), nullable=True),
        sa.Column("raw_tool_input", sa.JSON(), nullable=True),
        sa.Column("parsed_advice", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("pricing_snapshot", sa.JSON(), nullable=True),
    )
    op.create_index("ix_decisions_session_id", "decisions", ["session_id"])
    op.create_index("ix_decisions_hand_id", "decisions", ["hand_id"])
    op.create_index("ix_decisions_model_prompt", "decisions", ["model_id", "prompt_version"])
    op.create_index("ix_decisions_status", "decisions", ["status"])
    op.create_index("ix_decisions_created_at", "decisions", ["created_at"])

    op.create_table(
        "actual_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "decision_id", sa.String(32), sa.ForeignKey("decisions.decision_id"), nullable=False
        ),
        sa.Column("action_type", sa.String(16), nullable=False),
        sa.Column("to_amount", sa.Integer(), nullable=True),
        sa.Column(
            "taken_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
    )
    op.create_index("ix_actual_actions_decision_id", "actual_actions", ["decision_id"])


def downgrade() -> None:
    op.drop_index("ix_actual_actions_decision_id", table_name="actual_actions")
    op.drop_table("actual_actions")
    op.drop_index("ix_decisions_created_at", table_name="decisions")
    op.drop_index("ix_decisions_status", table_name="decisions")
    op.drop_index("ix_decisions_model_prompt", table_name="decisions")
    op.drop_index("ix_decisions_hand_id", table_name="decisions")
    op.drop_index("ix_decisions_session_id", table_name="decisions")
    op.drop_table("decisions")
    op.drop_index("ix_hands_session_id", table_name="hands")
    op.drop_table("hands")
    op.drop_table("sessions")
