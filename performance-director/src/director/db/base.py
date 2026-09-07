from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import DateTime, create_engine, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TenantMixin:
    """Common columns for every business table (UUID id, tenant, timestamps)."""

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=DEFAULT_TENANT, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=utcnow
    )


def _json_default(o: object) -> object:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, uuid.UUID):
        return str(o)
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(f"not JSON serializable: {type(o).__name__}")


def json_dumps(obj: object) -> str:
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


@lru_cache(maxsize=8)
def get_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, future=True, json_serializer=json_dumps)


def SessionFactory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(database_url), expire_on_commit=False, future=True)


@contextmanager
def session_scope(database_url: str) -> Iterator[Session]:
    factory = SessionFactory(database_url)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
