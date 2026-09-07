"""Scenario 11: two schedulers + two workers, crash and retry -> exactly one logical execution per job."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from director.config import ScheduleEntry, SchedulesConfig
from director.db.models import JobRun
from director.jobs import queue
from director.jobs.scheduler import tick
from director.jobs.worker import RetryableError, Worker

pytestmark = pytest.mark.db


def test_enqueue_is_idempotent(session):
    when = datetime(2026, 9, 7, 5, 30, tzinfo=UTC)
    a = queue.enqueue(session, "report_daily", when, scope="global")
    b = queue.enqueue(session, "report_daily", when, scope="global")
    session.commit()
    assert a is not None and b is None
    assert session.execute(select(JobRun)).scalars().all().__len__() == 1


def test_two_schedulers_produce_one_row_per_occurrence(session):
    sched = SchedulesConfig(
        timezone="Europe/Warsaw",
        entries=[
            ScheduleEntry(job="report_daily", at=["07:30"]),
            ScheduleEntry(job="sync_orders", every_minutes=15),
        ],
    )
    since = datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    until = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    n1 = tick(session, sched, since=since, until=until)
    n2 = tick(session, sched, since=since, until=until)
    assert n1 >= 2 and n2 == 0
    rows = session.execute(select(JobRun)).scalars().all()
    daily = [r for r in rows if r.job_name == "report_daily"]
    assert len(daily) == 2  # 06.09 and 07.09 at 07:30 local
    assert daily[0].scheduled_for.astimezone(UTC).hour == 5  # 07:30 CEST == 05:30 UTC
    interval = [r for r in rows if r.job_name == "sync_orders"]
    assert len(interval) == 1  # only the latest missed occurrence after downtime


def test_concurrent_workers_execute_each_job_once(session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        for i in range(20):
            queue.enqueue(s, "noop", now - timedelta(minutes=i + 1), scope=f"s{i}")
        s.commit()
    executed: list[str] = []
    lock = threading.Lock()

    def handler(ctx):
        with lock:
            executed.append(ctx.job.scope)
        return {"ok": True}

    workers = [
        Worker(
            session_factory,
            {"noop": handler},
            services=None,
            owner=f"w{i}",
            lease_seconds=30,
            poll_seconds=0.01,
        )
        for i in range(2)
    ]

    def drain(w: Worker):
        while w.run_once():
            pass

    threads = [threading.Thread(target=drain, args=(w,)) for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(executed) == sorted(f"s{i}" for i in range(20))
    with session_factory() as s:
        statuses = {r.status for r in s.execute(select(JobRun)).scalars()}
    assert statuses == {"SUCCEEDED"}


def test_crash_expired_lease_is_reclaimed_and_retry_backoff(session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        queue.enqueue(s, "flaky", now - timedelta(minutes=1))
        s.commit()
    # worker A claims and "crashes" (never completes); lease is set in the past to simulate expiry
    with session_factory() as s:
        job = queue.claim(s, "A", lease_seconds=1)
        assert job is not None
    with session_factory() as s:
        row = s.get(JobRun, job.id)
        row.lease_until = now - timedelta(seconds=5)
        s.commit()
    # worker B re-claims the expired lease
    with session_factory() as s:
        job2 = queue.claim(s, "B", lease_seconds=30)
        assert (
            job2 is not None
            and job2.id == job.id
            and job2.attempts == 2
            and job2.error_class == "LeaseExpired"
        )
        # transient failure -> RETRY with future next_attempt_at
        status = queue.fail(s, job2.id, "B", "RetryableError", "network", retryable=True)
        assert status == "RETRY"
    with session_factory() as s:
        row = s.get(JobRun, job.id)
        assert row.status == "RETRY" and row.next_attempt_at > datetime.now(UTC)
        # exhaust attempts -> FAILED
        row.attempts = row.max_attempts
        row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        s.commit()
    with session_factory() as s:
        j = queue.claim(s, "C", lease_seconds=30)
        assert j is not None
        assert queue.fail(s, j.id, "C", "RetryableError", "still failing", retryable=True) == "FAILED"


def test_worker_maps_exceptions(session_factory):
    now = datetime.now(UTC)
    with session_factory() as s:
        queue.enqueue(s, "boom", now - timedelta(minutes=1))
        queue.enqueue(s, "nohandler", now - timedelta(minutes=1))
        s.commit()

    def boom(ctx):
        raise RetryableError("429", retry_after=120)

    w = Worker(session_factory, {"boom": boom}, services=None, owner="w", lease_seconds=30)
    assert w.run_once() and w.run_once()
    with session_factory() as s:
        rows = {r.job_name: r for r in s.execute(select(JobRun)).scalars()}
    assert rows["boom"].status == "RETRY" and rows["boom"].next_attempt_at >= datetime.now(UTC) + timedelta(
        seconds=100
    )
    assert rows["nohandler"].status == "FAILED" and rows["nohandler"].error_class == "PermanentError"
