from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from director.db.base import Base, get_engine

TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://director@127.0.0.1:54329/director_test")
ROOT = Path(__file__).resolve().parents[1]


def _db_available() -> bool:
    try:
        with get_engine(TEST_DB).connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def db_url() -> str:
    if not _db_available():
        pytest.skip("PostgreSQL test database not available (set TEST_DATABASE_URL)")
    engine = get_engine(TEST_DB)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return TEST_DB


@pytest.fixture()
def session_factory(db_url: str) -> Iterator[sessionmaker[Session]]:
    engine = get_engine(db_url)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    yield factory
    # wipe all tables between tests (order-independent)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE " + ", ".join(t.name for t in Base.metadata.sorted_tables) + " CASCADE"))


@pytest.fixture()
def session(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def uid() -> uuid.UUID:
    return uuid.uuid4()
