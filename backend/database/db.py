"""Database session utilities for transactional operations."""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session

from backend.database.database import db
from backend.database.models import Trade


__all__ = ["Trade", "session_scope"]


@contextmanager
def session_scope() -> Iterator[Session]:
    """Provide a transactional scope around a series of operations.

    Yields an active SQLAlchemy session and guarantees proper cleanup.
    Commits on success, rolls back on exceptions, and always closes the
    session when exiting the context.
    """

    session = db.get_session()
    if session is None:
        raise RuntimeError("Database session unavailable")

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
