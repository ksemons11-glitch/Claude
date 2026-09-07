from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import SyncCheckpoint


def get_checkpoint(session: Session, source_account_id: uuid.UUID, stream: str) -> SyncCheckpoint:
    cp = session.execute(
        select(SyncCheckpoint).where(
            SyncCheckpoint.source_account_id == source_account_id, SyncCheckpoint.stream == stream
        )
    ).scalar_one_or_none()
    if cp is None:
        cp = SyncCheckpoint(source_account_id=source_account_id, stream=stream)
        session.add(cp)
        session.flush()
    return cp


def mark_success(
    cp: SyncCheckpoint, *, at: datetime, cursor: str | None, high_watermark: datetime | None, records: int
) -> None:
    cp.last_attempt_at = at
    cp.last_success_at = at
    cp.cursor = cursor
    if high_watermark and (cp.high_watermark is None or high_watermark > cp.high_watermark):
        cp.high_watermark = high_watermark
    cp.records_total += records
    cp.last_error = None


def mark_failure(cp: SyncCheckpoint, *, at: datetime, error: str) -> None:
    cp.last_attempt_at = at
    cp.last_error = error[:2000]
