"""Turns SchedulesConfig into job_runs rows. Idempotent: running two schedulers is safe
because enqueue() relies on UNIQUE(job, scheduled_for, scope).

Catch-up policy after downtime: daily jobs get every missed occurrence (bounded), interval
jobs only their latest missed occurrence, so we never replay a series of stale intraday alerts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from director.config import ScheduleEntry, SchedulesConfig
from director.jobs.queue import enqueue
from director.metrics.calendar import local_datetime, tz, weekday_name

MAX_DAILY_CATCHUP_DAYS = 3


def _interval_occurrences(entry: ScheduleEntry, since: datetime, until: datetime) -> list[datetime]:
    assert entry.every_minutes
    step = timedelta(minutes=entry.every_minutes)
    # align to the epoch grid so two schedulers agree on the same timestamps
    epoch = datetime(2020, 1, 1, tzinfo=UTC)
    n = int((since - epoch) / step)
    t = epoch + step * n
    if t <= since:
        t += step
    out: list[datetime] = []
    while t <= until:
        out.append(t)
        t += step
    return out[-1:]  # latest missed occurrence only


def _daily_occurrences(
    entry: ScheduleEntry, since: datetime, until: datetime, tz_name: str
) -> list[datetime]:
    out: list[datetime] = []
    zone = tz(tz_name)
    day = (since.astimezone(zone).date()) - timedelta(days=1)
    last_day = until.astimezone(zone).date()
    while day <= last_day:
        if not entry.days or weekday_name(day) in entry.days:
            for hhmm in entry.at:
                when = local_datetime(day, hhmm, tz_name).astimezone(UTC)
                if since < when <= until:
                    out.append(when)
        day += timedelta(days=1)
    return out[-MAX_DAILY_CATCHUP_DAYS * max(1, len(entry.at)) :]


def due_occurrences(entry: ScheduleEntry, since: datetime, until: datetime, tz_name: str) -> list[datetime]:
    if not entry.enabled:
        return []
    if entry.every_minutes:
        return _interval_occurrences(entry, since, until)
    if entry.at:
        return _daily_occurrences(entry, since, until, tz_name)
    return []


def tick(
    session: Session,
    schedules: SchedulesConfig,
    *,
    since: datetime,
    until: datetime | None = None,
    scopes: dict[str, list[str]] | None = None,
) -> int:
    """Enqueue every due occurrence in (since, until]. Returns number of new rows."""
    until = until or datetime.now(UTC)
    scopes = scopes or {}
    created = 0
    for entry in schedules.entries:
        for when in due_occurrences(entry, since, until, schedules.timezone):
            targets = scopes.get(entry.scope, ["global"]) if entry.scope != "global" else ["global"]
            for scope in targets:
                if enqueue(
                    session,
                    entry.job,
                    when,
                    scope=scope,
                    timeout_seconds=entry.timeout_seconds,
                    max_attempts=entry.max_attempts,
                ):
                    created += 1
    session.commit()
    return created
