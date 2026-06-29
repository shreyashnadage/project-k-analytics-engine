"""Session management for Postgres."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from analytics_engine.db.engine import get_pg_engine

_SessionFactory: sessionmaker | None = None


def _get_factory() -> sessionmaker:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            autocommit=False, autoflush=False, bind=get_pg_engine()
        )
    return _SessionFactory


def get_session() -> Generator[Session, None, None]:
    session = _get_factory()()
    try:
        yield session
    finally:
        session.close()


def create_session() -> Session:
    return _get_factory()()
