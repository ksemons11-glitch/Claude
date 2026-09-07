"""Worker loop: claim -> run handler (with heartbeat thread) -> complete/fail."""

from __future__ import annotations

import logging
import socket
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from director.db.models import JobRun
from director.jobs import queue

log = logging.getLogger("director.worker")


class RetryableError(Exception):
    """Transient failure (network, 429, 5xx). Carries optional Retry-After seconds."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class PermanentError(Exception):
    """Do not retry (401/403, schema mismatch, bad config)."""


@dataclass
class JobContext:
    job: JobRun
    session_factory: sessionmaker[Session]
    services: Any
    correlation_id: str
    checkpoint: dict[str, Any] = field(default_factory=dict)

    def save_checkpoint(self, data: dict[str, Any]) -> None:
        with self.session_factory() as s:
            row = s.get(JobRun, self.job.id)
            if row is not None:
                row.checkpoint = data
                s.commit()
        self.checkpoint = data


Handler = Callable[[JobContext], dict[str, Any]]


class Worker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        handlers: dict[str, Handler],
        services: Any,
        *,
        owner: str | None = None,
        lease_seconds: int = 300,
        poll_seconds: float = 2.0,
    ):
        self.session_factory = session_factory
        self.handlers = handlers
        self.services = services
        self.owner = owner or f"{socket.gethostname()}:{uuid.uuid4().hex[:8]}"
        self.lease_seconds = lease_seconds
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> bool:
        """Claim and execute a single job. Returns True if a job was processed."""
        with self.session_factory() as s:
            job = queue.claim(s, self.owner, self.lease_seconds)
        if job is None:
            return False
        self._execute(job)
        return True

    def run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.run_once():
                    self._stop.wait(self.poll_seconds)
            except Exception:  # pragma: no cover - defensive
                log.exception("worker loop error")
                self._stop.wait(self.poll_seconds)

    def _execute(self, job: JobRun) -> None:
        handler = self.handlers.get(job.job_name)
        ctx = JobContext(
            job=job,
            session_factory=self.session_factory,
            services=self.services,
            correlation_id=job.correlation_id,
            checkpoint=dict(job.checkpoint or {}),
        )
        stop_hb = threading.Event()
        lost_lease = threading.Event()

        def _hb() -> None:
            interval = max(1.0, self.lease_seconds / 3)
            while not stop_hb.wait(interval):
                with self.session_factory() as s:
                    if not queue.heartbeat(s, job.id, self.owner, self.lease_seconds):
                        lost_lease.set()
                        return

        hb = threading.Thread(target=_hb, daemon=True)
        hb.start()
        started = time.monotonic()
        try:
            if handler is None:
                raise PermanentError(f"no handler registered for job {job.job_name}")
            result = handler(ctx)
            elapsed = time.monotonic() - started
            if elapsed > job.timeout_seconds:
                result = {**result, "warning": f"exceeded timeout {job.timeout_seconds}s"}
            stop_hb.set()
            if lost_lease.is_set():
                log.warning("job %s finished after losing lease; result discarded", job.id)
                return
            with self.session_factory() as s:
                queue.complete(s, job.id, self.owner, result, records=int(result.get("records", 0)))
        except RetryableError as exc:
            stop_hb.set()
            with self.session_factory() as s:
                queue.fail(
                    s,
                    job.id,
                    self.owner,
                    type(exc).__name__,
                    str(exc),
                    retryable=True,
                    retry_after=exc.retry_after,
                )
        except PermanentError as exc:
            stop_hb.set()
            with self.session_factory() as s:
                queue.fail(s, job.id, self.owner, type(exc).__name__, str(exc), retryable=False)
        except Exception as exc:
            stop_hb.set()
            log.error("job %s failed: %s", job.job_name, traceback.format_exc())
            with self.session_factory() as s:
                queue.fail(s, job.id, self.owner, type(exc).__name__, str(exc), retryable=True)
        finally:
            stop_hb.set()
