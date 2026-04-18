"""SQLAlchemy engine construction.

Default database_url comes from settings; tests and embedded contexts can
override by passing an explicit URL. Engines are cached per URL so the
FastAPI lifespan only builds one for the process.
"""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from poker_coach.settings import settings


def make_engine(database_url: str) -> Engine:
    # SQLite note: check_same_thread=False is safe because we use a single
    # synchronous engine and FastAPI's threadpool dispatch. JSON1 is
    # compiled into Python's bundled SQLite build on all supported
    # platforms so no pragmas are required here.
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(database_url, future=True, connect_args=connect_args)


@lru_cache(maxsize=4)
def cached_engine(database_url: str) -> Engine:
    return make_engine(database_url)


def default_engine() -> Engine:
    return cached_engine(settings.database_url)
