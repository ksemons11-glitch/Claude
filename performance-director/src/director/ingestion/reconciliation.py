"""Daily cross-source reconciliation. Discrepancies become DATA_ISSUE rows (with dedupe and
auto-resolution), never automatic verdicts about advertising performance."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from director.db.models import (
    Ad,
    AdInsight,
    AdSet,
    Campaign,
    DailyMetric,
    DataQualityIssue,
    IngestionBatch,
    Order,
    Shop,
    SourceAccount,
    SyncCheckpoint,
)

TOLERANCE_PCT = Decimal("0.02")
TOLERANCE_ABS = Decimal("1.00")


def _issue(
    session: Session,
    *,
    scope: str,
    check: str,
    expected: Any,
    actual: Any,
    severity: str,
    message: str,
    business_date: date | None,
    now: datetime,
    open_keys: set[str],
) -> None:
    key = f"{scope}|{check}|{business_date.isoformat() if business_date else '-'}"
    open_keys.add(key)
    row = session.execute(
        select(DataQualityIssue).where(
            DataQualityIssue.dedupe_key == key, DataQualityIssue.resolved_at.is_(None)
        )
    ).scalar_one_or_none()
    if row is None:
        session.add(
            DataQualityIssue(
                scope=scope,
                check_name=check,
                expected=expected,
                actual=actual,
                severity=severity,
                message=message,
                business_date=business_date,
                detected_at=now,
                dedupe_key=key,
            )
        )
    else:
        row.actual, row.severity, row.message = actual, severity, message


def _resolve_stale(
    session: Session, scope_prefix: str, business_date: date, open_keys: set[str], now: datetime
) -> None:
    rows = session.execute(
        select(DataQualityIssue).where(
            DataQualityIssue.resolved_at.is_(None),
            DataQualityIssue.business_date == business_date,
            DataQualityIssue.scope.like(f"{scope_prefix}%"),
        )
    ).scalars()
    for r in rows:
        if r.dedupe_key not in open_keys:
            r.resolved_at = now


def _panel_value(session: Session, shop_key: str, metric: str, day: date) -> Decimal | None:
    row = session.execute(
        select(DailyMetric)
        .where(
            DailyMetric.scope == "panel",
            DailyMetric.entity_key == shop_key,
            DailyMetric.metric == metric,
            DailyMetric.business_date == day,
        )
        .order_by(DailyMetric.as_of.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.value if row else None


def _within(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= max(TOLERANCE_ABS, abs(b) * TOLERANCE_PCT)


def reconcile_shop_day(
    session: Session,
    *,
    shop: Shop,
    meta_account: SourceAccount | None,
    base_account: SourceAccount | None,
    day: date,
    now: datetime,
    freshness_minutes: int,
) -> dict[str, Any]:
    open_keys: set[str] = set()
    scope = f"shop:{shop.shop_key}"
    summary: dict[str, Any] = {"shop": shop.shop_key, "date": day.isoformat(), "checks": {}}

    # --- orders: ledger vs panel aggregate ------------------------------------------------
    orders_q = session.execute(
        select(func.count(), func.coalesce(func.sum(Order.gross_amount), 0)).where(
            Order.shop_id == shop.id, Order.business_date == day, Order.is_valid.is_(True)
        )
    ).one()
    ledger_orders, ledger_revenue = int(orders_q[0]), Decimal(orders_q[1])
    summary["checks"]["ledger_orders"] = ledger_orders
    summary["checks"]["ledger_revenue"] = str(ledger_revenue)
    panel_orders = _panel_value(session, shop.shop_key, "panel_orders", day)
    panel_revenue = _panel_value(session, shop.shop_key, "panel_revenue", day)
    if panel_orders is not None and int(panel_orders) != ledger_orders:
        _issue(
            session,
            scope=scope,
            check="orders_count_vs_panel",
            expected=int(panel_orders),
            actual=ledger_orders,
            severity="WATCH",
            message=f"Liczba zamówień Base ({ledger_orders}) ≠ panel ({int(panel_orders)}) dla {day}",
            business_date=day,
            now=now,
            open_keys=open_keys,
        )
    if panel_revenue is not None and not _within(ledger_revenue, panel_revenue):
        _issue(
            session,
            scope=scope,
            check="revenue_vs_panel",
            expected=str(panel_revenue),
            actual=str(ledger_revenue),
            severity="WATCH",
            message=f"Obrót Base ({ledger_revenue}) ≠ panel ({panel_revenue}) dla {day}",
            business_date=day,
            now=now,
            open_keys=open_keys,
        )

    # --- spend: Meta vs panel cost ---------------------------------------------------------
    if meta_account is not None:
        spend = session.execute(
            select(func.coalesce(func.sum(AdInsight.spend), 0))
            .join(Ad, Ad.id == AdInsight.ad_id)
            .where(
                Ad.source_account_id == meta_account.id,
                AdInsight.business_date == day,
                AdInsight.hour == -1,
                AdInsight.breakdown_key == "none",
            )
        ).scalar()
        spend = Decimal(spend or 0)
        summary["checks"]["meta_spend"] = str(spend)
        panel_spend = _panel_value(session, shop.shop_key, "panel_ad_spend", day)
        if panel_spend is not None and not _within(spend, panel_spend):
            _issue(
                session,
                scope=scope,
                check="spend_vs_panel",
                expected=str(panel_spend),
                actual=str(spend),
                severity="WATCH",
                message=f"Spend Meta ({spend}) ≠ koszt panelu ({panel_spend}) dla {day}",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )
        # currency / timezone consistency
        if meta_account.currency and meta_account.currency != shop.currency:
            _issue(
                session,
                scope=scope,
                check="currency_mismatch",
                expected=shop.currency,
                actual=meta_account.currency,
                severity="CRITICAL",
                message="Waluta konta Meta różni się od waluty sklepu; metryki ROAS/CPA nieporównywalne bez przeliczenia",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )
        if meta_account.timezone and meta_account.timezone != shop.timezone:
            _issue(
                session,
                scope=scope,
                check="timezone_mismatch",
                expected=shop.timezone,
                actual=meta_account.timezone,
                severity="WATCH",
                message="Strefa konta Meta ≠ strefa sklepu: granice dnia nieporównywalne; reguły dzienne wyłączone dla tego konta",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )

    # --- freshness / completeness of batches ------------------------------------------------
    for acct, label in ((base_account, "baselinker"), (meta_account, "meta")):
        if acct is None:
            _issue(
                session,
                scope=scope,
                check=f"{label}_unconfigured",
                expected="account",
                actual=None,
                severity="WATCH",
                message=f"Brak skonfigurowanego konta {label} dla sklepu",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )
            continue
        cps = (
            session.execute(select(SyncCheckpoint).where(SyncCheckpoint.source_account_id == acct.id))
            .scalars()
            .all()
        )
        if not cps or all(cp.last_success_at is None for cp in cps):
            _issue(
                session,
                scope=scope,
                check=f"{label}_never_synced",
                expected="sync",
                actual=None,
                severity="CRITICAL",
                message=f"Źródło {label} nigdy nie zsynchronizowane",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )
            continue
        newest = max(cp.last_success_at for cp in cps if cp.last_success_at)
        lag = (now - newest).total_seconds() / 60
        summary["checks"][f"{label}_lag_minutes"] = round(lag, 1)
        if lag > freshness_minutes:
            _issue(
                session,
                scope=scope,
                check=f"{label}_stale",
                expected=f"<= {freshness_minutes} min",
                actual=f"{lag:.0f} min",
                severity="CRITICAL",
                message=f"Źródło {label} nieaktualne od {lag:.0f} min - zero zamówień/spendu nie jest faktem biznesowym",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )
        incomplete = session.execute(
            select(func.count())
            .select_from(IngestionBatch)
            .where(
                IngestionBatch.source_account_id == acct.id,
                IngestionBatch.pagination_complete.is_(False),
                IngestionBatch.fetched_at >= now - timedelta(days=2),
            )
        ).scalar()
        if incomplete:
            _issue(
                session,
                scope=scope,
                check=f"{label}_pagination_incomplete",
                expected=0,
                actual=incomplete,
                severity="CRITICAL",
                message=f"{incomplete} partii {label} z niekompletną paginacją w ostatnich 48h",
                business_date=day,
                now=now,
                open_keys=open_keys,
            )

    # --- duplicates -------------------------------------------------------------------------
    dup = session.execute(
        select(Order.customer_hash, Order.gross_amount, func.count())
        .where(Order.shop_id == shop.id, Order.business_date == day, Order.customer_hash.isnot(None))
        .group_by(Order.customer_hash, Order.gross_amount)
        .having(func.count() > 1)
    ).all()
    if dup:
        _issue(
            session,
            scope=scope,
            check="possible_duplicate_orders",
            expected=0,
            actual=len(dup),
            severity="INFO",
            message=f"{len(dup)} grup zamówień o identycznym kliencie i kwocie - sprawdź duplikaty",
            business_date=day,
            now=now,
            open_keys=open_keys,
        )

    _resolve_stale(session, scope, day, open_keys, now)
    summary["open_issues"] = sorted(open_keys)
    return summary


def open_issues(
    session: Session, *, scope_prefix: str | None = None, min_severity: str = "INFO"
) -> list[DataQualityIssue]:
    order = {"INFO": 0, "WATCH": 1, "CRITICAL": 2}
    q = select(DataQualityIssue).where(DataQualityIssue.resolved_at.is_(None))
    if scope_prefix:
        q = q.where(DataQualityIssue.scope.like(f"{scope_prefix}%"))
    return [r for r in session.execute(q).scalars() if order[r.severity] >= order[min_severity]]


def structure_counts(session: Session, account_id: uuid.UUID) -> dict[str, int]:
    return {
        "campaigns": session.execute(
            select(func.count()).select_from(Campaign).where(Campaign.source_account_id == account_id)
        ).scalar()
        or 0,
        "adsets": session.execute(
            select(func.count()).select_from(AdSet).where(AdSet.source_account_id == account_id)
        ).scalar()
        or 0,
        "ads": session.execute(
            select(func.count()).select_from(Ad).where(Ad.source_account_id == account_id)
        ).scalar()
        or 0,
    }
