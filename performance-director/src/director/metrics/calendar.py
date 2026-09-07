"""Business-day arithmetic. A business day is the local interval [00:00, next 00:00)
converted to UTC; DST days have 23 or 25 hours. Baselines never include the analysed day."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def tz(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def business_day_bounds(day: date, tz_name: str) -> tuple[datetime, datetime]:
    """UTC [start, end) of the local calendar day."""
    zone = tz(tz_name)
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def business_day_hours(day: date, tz_name: str) -> float:
    start, end = business_day_bounds(day, tz_name)
    return (end - start).total_seconds() / 3600.0


def business_date_of(moment: datetime, tz_name: str) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(tz(tz_name)).date()


def local_now(tz_name: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return now.astimezone(tz(tz_name))


def preceding_window(day: date, days: int) -> tuple[date, date]:
    """`days` full days strictly before `day`: [day-days, day-1]."""
    return day - timedelta(days=days), day - timedelta(days=1)


def same_weekday_dates(day: date, count: int) -> list[date]:
    """Up to `count` previous dates with the same weekday, most recent first."""
    return [day - timedelta(days=7 * i) for i in range(1, count + 1)]


def local_datetime(day: date, hhmm: str, tz_name: str) -> datetime:
    hh, mm = (int(x) for x in hhmm.split(":"))
    return datetime.combine(day, time(hh, mm), tzinfo=tz(tz_name))


def weekday_name(day: date) -> str:
    return WEEKDAYS[day.weekday()]


def week_bounds(day: date) -> tuple[date, date]:
    """Monday..Sunday of the week containing `day`."""
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)
