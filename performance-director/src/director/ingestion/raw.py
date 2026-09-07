"""Raw batch persistence: every envelope is stored once with request hash + checksum and a retention TTL.
Records stored here are already pseudonymous (normalizers drop PII)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.contracts.envelope import DataEnvelope
from director.db.models import IngestionBatch


def _h(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def store_batch(
    session: Session,
    env: DataEnvelope,
    *,
    source_account_id: uuid.UUID | None,
    retention_days: int,
    keep_payload: bool = True,
) -> IngestionBatch:
    """Idempotent: the same request fetched at the same instant returns the existing batch (at-least-once safe)."""
    request_hash = _h(env.request_signature)
    existing = session.execute(
        select(IngestionBatch).where(
            IngestionBatch.request_hash == request_hash, IngestionBatch.fetched_at == env.fetched_at_utc
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    batch = IngestionBatch(
        source=env.source.value,
        stream=env.stream,
        source_account_id=source_account_id,
        request_hash=request_hash,
        request_signature=env.request_signature,
        range_start=env.requested_range[0] if env.requested_range else None,
        range_end=env.requested_range[1] if env.requested_range else None,
        raw_payload={"records": env.records, "warnings": env.warnings} if keep_payload else None,
        checksum=_h(env.records),
        record_count=len(env.records),
        status=env.status.value,
        pagination_complete=env.pagination_complete,
        warnings=env.warnings,
        fetched_at=env.fetched_at_utc,
        expires_at=env.fetched_at_utc + timedelta(days=retention_days),
    )
    session.add(batch)
    session.flush()
    return batch
