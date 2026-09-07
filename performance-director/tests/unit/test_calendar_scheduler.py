"""Scenario 12: DST days have 23/25 hours and the UTC range is correct."""

from datetime import UTC, date, datetime

from director.config import ScheduleEntry
from director.jobs.scheduler import due_occurrences
from director.metrics.calendar import (
    business_date_of,
    business_day_bounds,
    business_day_hours,
    preceding_window,
)


def test_dst_days():
    assert business_day_hours(date(2026, 3, 29), "Europe/Warsaw") == 23.0
    assert business_day_hours(date(2026, 10, 25), "Europe/Warsaw") == 25.0
    assert business_day_hours(date(2026, 9, 6), "Europe/Warsaw") == 24.0
    start, end = business_day_bounds(date(2026, 10, 25), "Europe/Warsaw")
    assert start == datetime(2026, 10, 24, 22, 0, tzinfo=UTC) and end == datetime(
        2026, 10, 25, 23, 0, tzinfo=UTC
    )


def test_business_date_and_preceding_window():
    assert business_date_of(datetime(2026, 9, 6, 22, 30, tzinfo=UTC), "Europe/Warsaw") == date(2026, 9, 7)
    assert preceding_window(date(2026, 9, 7), 7) == (date(2026, 8, 31), date(2026, 9, 6))


def test_daily_schedule_across_dst_change_keeps_local_time():
    e = ScheduleEntry(job="report_daily", at=["07:30"])
    occ = due_occurrences(
        e, datetime(2026, 10, 24, 0, 0, tzinfo=UTC), datetime(2026, 10, 27, 0, 0, tzinfo=UTC), "Europe/Warsaw"
    )
    hours = [o.hour for o in occ]
    assert hours == [
        5,
        6,
        6,
    ]  # CEST -> CET on 25.10 03:00: 07:30 local is 05:30 UTC on 24.10 and 06:30 UTC afterwards
