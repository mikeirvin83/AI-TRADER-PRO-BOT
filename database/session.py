"""Database engine & session factory.

Provides a synchronous SQLAlchemy engine/sessionmaker plus context-manager and
FastAPI-dependency helpers. Uses ``get_settings().DATABASE_URL``.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.logging_config import get_logger
from config.settings import get_settings
from database.models import Base

log = get_logger(__name__)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            future=True,
        )
        log.info("db_engine_created", url=settings.DATABASE_URL.split("@")[-1])
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, future=True
        )
    return _SessionFactory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional scope. Commits on success, rolls back on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. For dev/test; production uses Alembic migrations."""
    Base.metadata.create_all(bind=get_engine())
    log.info("db_initialized", tables=len(Base.metadata.tables))
