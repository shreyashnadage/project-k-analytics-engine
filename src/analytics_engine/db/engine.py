"""Database engine factory for Postgres (serving) and DuckDB (staging)."""

from __future__ import annotations

import os

import duckdb
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///analytics_dev.db")
ANALYTICS_SCHEMA = os.getenv("ANALYTICS_SCHEMA", "analytics")
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

_pg_engine: Engine | None = None


def get_pg_engine() -> Engine:
    global _pg_engine
    if _pg_engine is None:
        kwargs: dict = {"echo": SQL_ECHO}
        if not DATABASE_URL.startswith("sqlite"):
            kwargs.update(pool_size=10, max_overflow=20)
        else:
            kwargs["connect_args"] = {"check_same_thread": False}
        _pg_engine = create_engine(DATABASE_URL, **kwargs)
    return _pg_engine


def get_duck() -> duckdb.DuckDBPyConnection:
    """Create a fresh in-memory DuckDB connection for per-client staging."""
    return duckdb.connect(":memory:")
