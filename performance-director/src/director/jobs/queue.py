"""PostgreSQL-backed job queue.

Guarantees: at-least-once execution with idempotent handlers. UNIQUE(job, scheduled_for, scope)
prevents duplicate enqueues from concurrent schedulers; SELECT ... FOR UPDATE SKIP LOCKED
lets many workers claim without blocking; a lease (renewed by heartbeat) lets a crashed
worker's job be re-claimed after expiry. The claim transaction is short: it never spans
an external HTTP/LLM call.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from director.db.base import DEFAULT_TENANT
from director.db.models import JobRun

RETRYABLE_STATES = ("PENDING", "RETRY")


def utcnow() -> datetime:
    return datetime.now(UTC)


def enqueue(
    session: Session,
    job_name: str,
    scheduled_for: datetime,
    *,
    scope: str = "global",
    params: dict[str, Any] | None = None,
    timeout_seconds: int = 900,
    max_attempts: int = 5,
    correlation_id: str | None = None,
) -> uuid.UUID | None:
    """Insert a job run; returns its id or None if an identical (job, scheduled_for, scope) exists."""
    stmt = (
        insert(JobRun)
        .values(
            id=uuid.uuid4(),
            tenant_id=DEFAULT_TENANT,
            job_name=job_name,
            scheduled_for=scheduled_for,
            scope=scope,
            params=params or {},
            status="PENDING",
            attempts=0,
            max_attempts=max_attempts,
            next_attempt_at=scheduled_for,
            timeout_seconds=timeout_seconds,
            correlation_id=correlation_id or uuid.uuid4().hex,
        )
        .on_conflict_do_nothing(constraint="uq_job_runs")
        .returning(JobRun.id)
    )
    return session.execute(stmt).scalar_one_or_none()


def claim(session: Session, owner: str, lease_seconds: int, now: datetime | None = None) -> JobRun | None:
    """Claim one due job. Commits the claim so the lease is visible before any external work."""
    now = now or utcnow()
    stmt = (
        select(JobRun)
        .where(
            or_(
                (JobRun.status.in_(RETRYABLE_STATES)) & (JobRun.next_attempt_at <= now),
                (JobRun.status == "RUNNING") & (JobRun.lease_until < now),  # expired lease -> crash recovery
            )
        )
        .order_by(JobRun.next_attempt_at, JobRun.scheduled_for)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = session.execute(stmt).scalars().first()
    if job is None:
        session.commit()
        return None
    if job.status == "RUNNING":
        job.error_class = "LeaseExpired"
        job.error_message = f"lease held by {job.lease_owner} expired; re-claimed by {owner}"
    job.status = "RUNNING"
    job.attempts += 1
    job.lease_owner = owner
    job.lease_until = now + timedelta(seconds=lease_seconds)
    job.heartbeat_at = now
    job.started_at = job.started_at or now
    session.commit()
    return job


def heartbeat(session: Session, job_id: uuid.UUID, owner: str, lease_seconds: int) -> bool:
    """Extend the lease; returns False if the lease was lost (another worker re-claimed)."""
    now = utcnow()
    job = session.get(JobRun, job_id)
    if job is None or job.lease_owner != owner or job.status != "RUNNING":
        session.rollback()
        return False
    job.heartbeat_at = now
    job.lease_until = now + timedelta(seconds=lease_seconds)
    session.commit()
    return True


def complete(
    session: Session, job_id: uuid.UUID, owner: str, result: dict[str, Any], records: int = 0
) -> bool:
    job = session.get(JobRun, job_id)
    if job is None or job.lease_owner != owner:
        session.rollback()
        return False
    job.status = "SUCCEEDED"
    job.finished_at = utcnow()
    job.result = result
    job.records_processed = records
    job.lease_until = None
    session.commit()
    return True


def backoff_seconds(attempt: int, base: float = 30.0, cap: float = 3600.0) -> float:
    """Exponential backoff with full jitter."""
    exp = min(cap, base * (2 ** max(0, attempt - 1)))
    return random.uniform(exp / 2, exp)


def fail(
    session: Session,
    job_id: uuid.UUID,
    owner: str,
    error_class: str,
    message: str,
    *,
    retryable: bool = True,
    retry_after: float | None = None,
) -> str:
    job = session.get(JobRun, job_id)
    if job is None or job.lease_owner != owner:
        session.rollback()
        return "LOST"
    job.error_class = error_class
    job.error_message = message[:4000]
    if retryable and job.attempts < job.max_attempts:
        delay = retry_after if retry_after is not None else backoff_seconds(job.attempts)
        job.status = "RETRY"
        job.next_attempt_at = utcnow() + timedelta(seconds=delay)
        job.lease_until = None
        session.commit()
        return "RETRY"
    job.status = "FAILED"
    job.finished_at = utcnow()
    job.lease_until = None
    session.commit()
    return "FAILED"


def try_advisory_lock(session: Session, key: str) -> bool:
    """Transaction-scoped advisory lock for per-account / per-mutation-type exclusivity."""
    return bool(session.execute(text("SELECT pg_try_advisory_xact_lock(hashtext(:k))"), {"k": key}).scalar())


def queue_stats(session: Session) -> dict[str, Any]:
    rows = session.execute(select(JobRun.status, func.count()).group_by(JobRun.status)).all()
    oldest = session.execute(
        select(func.min(JobRun.next_attempt_at)).where(JobRun.status.in_(RETRYABLE_STATES))
    ).scalar()
    age = (utcnow() - oldest).total_seconds() if oldest else 0.0
    return {"by_status": {s: c for s, c in rows}, "oldest_pending_age_seconds": max(0.0, age)}


def last_success(session: Session, job_name: str) -> datetime | None:
    return session.execute(
        select(func.max(JobRun.finished_at)).where(JobRun.job_name == job_name, JobRun.status == "SUCCEEDED")
    ).scalar()
