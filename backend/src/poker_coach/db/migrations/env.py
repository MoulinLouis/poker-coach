from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from poker_coach.db.tables import metadata
from poker_coach.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Let callers override via `cfg.set_main_option("sqlalchemy.url", ...)` before
# invoking alembic (e.g. tests targeting a throwaway DB). Fall back to settings
# only when nothing's been set.
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
