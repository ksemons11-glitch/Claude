"""Intraday alerts without false alarms: cumulative-to-same-local-hour comparison against comparable days,
consecutive-read confirmation, dedupe per (scope, rule, episode), cooldown and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from director.config import IntradayPolicy
from director.db.models import Alert, Order, Shop
from director.metrics.calendar import business_day_bounds, same_weekday_dates

SEVERITY_RANK = {"INFO": 0, "WATCH": 1, "CRITICAL": 2}


@dataclass
class IntradayReading:
    shop_key: str
    day: date
    local_hour: int
    cumulative_orders: int
    comparable: list[int]
    fresh: bool
    ratio: Decimal | None
    verdict: str  # OK | LOW | INSUFFICIENT_HISTORY | STALE | LOW_VOLUME


def cumulative_orders_to_hour(session: Session, shop: Shop, day: date, local_hour: int, tz_name: str) -> int:
    start, _ = business_day_bounds(day, tz_name)
    until = start + timedelta(hours=local_hour)
    return int(
        session.execute(
            select(func.count())
            .select_from(Order)
            .where(
                Order.shop_id == shop.id,
                Order.is_valid.is_(True),
                Order.created_at_source >= start,
                Order.created_at_source < until,
            )
        ).scalar()
        or 0
    )


def intraday_reading(
    session: Session,
    *,
    shop: Shop,
    now: datetime,
    tz_name: str,
    policy: IntradayPolicy,
    source_lag_minutes: float | None,
) -> IntradayReading:
    from director.metrics.calendar import local_now

    ln = local_now(tz_name, now)
    day, hour = ln.date(), ln.hour
    cum = cumulative_orders_to_hour(session, shop, day, hour, tz_name)
    comps = [cumulative_orders_to_hour(session, shop, d, hour, tz_name) for d in same_weekday_dates(day, 4)]
    fresh = source_lag_minutes is not None and source_lag_minutes <= policy.max_source_lag_minutes
    daily_totals = [
        int(
            session.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.shop_id == shop.id, Order.is_valid.is_(True), Order.business_date == d)
            ).scalar()
            or 0
        )
        for d in same_weekday_dates(day, 4)
    ]
    if not fresh:
        return IntradayReading(shop.shop_key, day, hour, cum, comps, False, None, "STALE")
    if len([c for c in comps if c is not None]) < 3:
        return IntradayReading(shop.shop_key, day, hour, cum, comps, True, None, "INSUFFICIENT_HISTORY")
    if (sum(daily_totals) / max(1, len(daily_totals))) < policy.min_daily_orders_for_business_signal:
        return IntradayReading(shop.shop_key, day, hour, cum, comps, True, None, "LOW_VOLUME")
    base = sorted(comps)[len(comps) // 2]
    if base == 0:
        return IntradayReading(shop.shop_key, day, hour, cum, comps, True, None, "INSUFFICIENT_HISTORY")
    ratio = Decimal(cum) / Decimal(base)
    verdict = "LOW" if (ratio < Decimal("0.4") and base >= 5) else "OK"
    return IntradayReading(shop.shop_key, day, hour, cum, comps, True, ratio, verdict)


def upsert_alert(
    session: Session,
    *,
    scope: str,
    rule_id: str,
    episode_key: str,
    severity: str,
    message: str,
    evidence: dict[str, Any],
    now: datetime,
    policy: IntradayPolicy,
    immediate: bool = False,
) -> tuple[Alert, bool]:
    """Returns (alert, should_notify). Business signals need `consecutive_reads_required` readings; availability failures can be immediate."""
    dedupe = f"{scope}|{rule_id}|{episode_key}"
    alert = session.execute(select(Alert).where(Alert.dedupe_key == dedupe)).scalar_one_or_none()
    if alert is None:
        alert = Alert(
            scope=scope,
            rule_id=rule_id,
            episode_key=episode_key,
            dedupe_key=dedupe,
            severity=severity,
            message=message,
            evidence=evidence,
            consecutive_reads=1,
            first_seen_at=now,
            last_seen_at=now,
            status="PENDING",
        )
        session.add(alert)
        session.flush()
    else:
        alert.consecutive_reads += 1
        alert.last_seen_at = now
        alert.evidence = evidence
        alert.message = message
    escalated = SEVERITY_RANK.get(severity, 0) > SEVERITY_RANK.get(alert.severity, 0)
    alert.severity = severity if escalated or alert.status == "PENDING" else alert.severity
    confirmed = immediate or alert.consecutive_reads >= policy.consecutive_reads_required
    if not confirmed:
        return alert, False
    alert.status = "ACTIVE"
    in_cooldown = alert.last_notified_at is not None and (now - alert.last_notified_at) < timedelta(
        hours=policy.cooldown_hours
    )
    if in_cooldown and not escalated:
        return alert, False
    alert.last_notified_at = now
    return alert, True


def recover_alert(session: Session, *, scope: str, rule_id: str, episode_key: str, now: datetime) -> bool:
    dedupe = f"{scope}|{rule_id}|{episode_key}"
    alert = session.execute(
        select(Alert).where(Alert.dedupe_key == dedupe, Alert.status != "RECOVERED")
    ).scalar_one_or_none()
    if alert is None:
        return False
    alert.status, alert.recovered_at = "RECOVERED", now
    return True


def active_alerts(session: Session) -> list[Alert]:
    return list(
        session.execute(
            select(Alert).where(Alert.status == "ACTIVE").order_by(Alert.last_seen_at.desc())
        ).scalars()
    )


def utcnow() -> datetime:
    return datetime.now(UTC)
