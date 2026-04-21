"""SQLAlchemy Core table definitions.

Append-only log-shaped schema with JSON columns. Do not evolve these
tables through SQLAlchemy ORM patterns — use Alembic migrations.

`other_params` on `decisions` is intentionally schema-unstable: it
holds provider-specific knobs that don't warrant first-class columns.
Do not index into it from SQL; reader code should tolerate missing
keys.
"""

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.schema import Column

metadata = MetaData()


sessions = Table(
    "sessions",
    metadata,
    Column("session_id", String(32), primary_key=True),
    Column("started_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("ended_at", DateTime, nullable=True),
    Column("mode", String(16), nullable=False),  # 'live' | 'spot'
    Column("notes", Text, nullable=True),
    Column("payout_structure", JSON, nullable=True),
    Column("blind_level_label", String(64), nullable=True),
)


hands = Table(
    "hands",
    metadata,
    Column("hand_id", String(32), primary_key=True),
    Column("session_id", String(32), ForeignKey("sessions.session_id"), nullable=False),
    Column("bb", Integer, nullable=False),
    Column("ante", Integer, nullable=False, server_default="0"),
    Column("effective_stack_start", Integer, nullable=False),
    Column("hero_stack_start", Integer, nullable=True),
    Column("villain_stack_start", Integer, nullable=True),
    Column("deck_snapshot", JSON, nullable=True),
    Column("rng_seed", Integer, nullable=True),
    Column("winner", String(16), nullable=True),  # 'hero' | 'villain' | 'tie'
    Column("showdown_state", JSON, nullable=True),
    Index("ix_hands_session_id", "session_id"),
)


decisions = Table(
    "decisions",
    metadata,
    Column("decision_id", String(32), primary_key=True),
    Column("session_id", String(32), ForeignKey("sessions.session_id"), nullable=False),
    Column("hand_id", String(32), ForeignKey("hands.hand_id"), nullable=True),
    Column("retry_of", String(32), ForeignKey("decisions.decision_id"), nullable=True),
    Column("created_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("stream_opened_at", DateTime, nullable=True),
    Column("latency_ms", Integer, nullable=True),
    # Input snapshot
    Column("game_state", JSON, nullable=False),
    Column("prompt_name", String(64), nullable=False),
    Column("prompt_version", String(32), nullable=False),
    Column("template_hash", String(64), nullable=False),
    Column("template_raw", Text, nullable=False),
    Column("rendered_prompt", Text, nullable=False),
    Column("variables", JSON, nullable=False),
    Column("villain_profile", String(16), nullable=False, server_default="unknown"),
    Column("system_prompt", Text, nullable=True),
    Column("system_prompt_hash", String(64), nullable=True),
    # Model config
    Column("provider", String(32), nullable=False),
    Column("model_id", String(64), nullable=False),
    Column("reasoning_effort", String(16), nullable=True),
    Column("thinking_budget", Integer, nullable=True),
    Column("temperature", Float, nullable=True),
    Column("other_params", JSON, nullable=True),
    # Response
    Column("reasoning_text", Text, nullable=True),
    Column("raw_tool_input", JSON, nullable=True),
    Column("parsed_advice", JSON, nullable=True),
    Column(
        "status", String(32), nullable=False
    ),  # in_flight|ok|invalid_response|illegal_action|provider_error|cancelled|abandoned|timeout
    Column("error_message", Text, nullable=True),
    # Accounting
    Column("input_tokens", Integer, nullable=True),
    Column("output_tokens", Integer, nullable=True),
    Column("reasoning_tokens", Integer, nullable=True),
    Column("total_tokens", Integer, nullable=True),
    Column("cost_usd", Float, nullable=True),
    Column("pricing_snapshot", JSON, nullable=True),
    Index("ix_decisions_session_id", "session_id"),
    Index("ix_decisions_hand_id", "hand_id"),
    Index("ix_decisions_model_prompt", "model_id", "prompt_version"),
    Index("ix_decisions_status", "status"),
    Index("ix_decisions_created_at", "created_at"),
)


actual_actions = Table(
    "actual_actions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("decision_id", String(32), ForeignKey("decisions.decision_id"), nullable=False),
    Column("action_type", String(16), nullable=False),
    Column("to_amount", Integer, nullable=True),
    Column("taken_at", DateTime, nullable=False, server_default=func.current_timestamp()),
    Index("ix_actual_actions_decision_id", "decision_id"),
)
