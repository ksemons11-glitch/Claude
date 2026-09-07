"""Builds ShopContext from the database and runs the rule library. Order: data quality first,
then business -> shop -> campaign -> adset -> ad -> creative."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.config import PoliciesConfig
from director.contracts.common import MetricValue
from director.contracts.rules import RuleResult
from director.creatives.identity import concentration, creative_map
from director.db.models import (
    Ad,
    AdInsight,
    AdSet,
    Campaign,
    Experiment,
    Shop,
    SourceAccount,
    StructureChange,
)
from director.diagnostics.rules import EntityContext, ShopContext, prioritize, run_rules
from director.ingestion.reconciliation import open_issues
from director.metrics.aggregates import latest_metric_rows, series, spend_since
from director.metrics.calendar import preceding_window
from director.metrics.costs import product_key_for_sku

HISTORY_METRICS = (
    "expected_result_after_ads",
    "revenue_ordered",
    "roas_attributed_ordered",
    "roas_meta",
    "ctr_link",
    "cpm",
    "cpc_link",
    "orders",
    "spend",
)
WINDOW_METRICS = (
    "spend",
    "purchases_meta",
    "attributed_orders",
    "attributed_revenue",
    "revenue_ordered",
    "orders",
)


def _metric_map(session: Session, scope: str, key: str, day: date, as_of: datetime) -> dict[str, MetricValue]:
    rows = session.execute(
        select(latest_rows_cls())
        .where(
            latest_rows_cls().scope == scope,
            latest_rows_cls().entity_key == key,
            latest_rows_cls().business_date == day,
            latest_rows_cls().as_of <= as_of,
        )
        .order_by(latest_rows_cls().as_of)
    ).scalars()
    out: dict[str, MetricValue] = {}
    for r in rows:
        out[r.metric] = MetricValue(
            metric=r.metric,
            value=r.value,
            numerator=r.numerator,
            denominator=r.denominator,
            reason=r.reason,
            flags=[] if r.quality == "OK" else [r.quality],
        )
    return out


def latest_rows_cls():
    from director.db.models import DailyMetric

    return DailyMetric


def days_since_last_change(
    session: Session,
    account: SourceAccount | None,
    day: date,
    as_of: datetime,
    only_ids: set[Any] | None = None,
) -> tuple[int | None, list[dict[str, Any]]]:
    if account is None:
        return None, []
    ids: dict[Any, str] = {}
    for c in session.execute(select(Campaign).where(Campaign.source_account_id == account.id)).scalars():
        ids[c.id] = f"campaign:{c.external_id}"
    for a in session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars():
        ids[a.id] = f"adset:{a.external_id}"
    for ad in session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars():
        ids[ad.id] = f"ad:{ad.external_id}"
    if only_ids is not None:
        ids = {k: v for k, v in ids.items() if k in only_ids}
    if not ids:
        return None, []
    changes = (
        session.execute(
            select(StructureChange)
            .where(
                StructureChange.entity_id.in_(list(ids.keys())),
                StructureChange.observed_to <= as_of,
                StructureChange.field.in_(
                    ("daily_budget", "lifetime_budget", "configured_status", "targeting")
                ),
            )
            .order_by(StructureChange.observed_to.desc())
            .limit(10)
        )
        .scalars()
        .all()
    )
    if not changes:
        return None, []
    latest = changes[0]
    full_days = (day - latest.observed_to.date()).days  # full days of data after the change
    recent = [
        {
            "id": str(c.id),
            "entity_ref": ids.get(c.entity_id),
            "field": c.field,
            "before": c.before,
            "after": c.after,
            "observed_to": c.observed_to.isoformat(),
            "derivation": c.derivation,
        }
        for c in changes
    ]
    return max(0, full_days), recent


def build_context(
    session: Session,
    *,
    shop: Shop,
    day: date,
    as_of: datetime,
    policies: PoliciesConfig,
    sources_fresh: bool,
    pagination_complete: bool,
    windows_compatible: bool,
) -> ShopContext:
    account = session.execute(
        select(SourceAccount).where(
            SourceAccount.shop_id == shop.id, SourceAccount.source == "meta", SourceAccount.active.is_(True)
        )
    ).scalar_one_or_none()
    metrics = _metric_map(session, "shop", shop.shop_key, day, as_of)
    hist_start, hist_end = preceding_window(day, 28)
    dates = [hist_start + timedelta(days=i) for i in range((hist_end - hist_start).days + 1)]
    history = {
        m: series(session, scope="shop", key=shop.shop_key, metric=m, dates=dates, as_of=as_of)
        for m in HISTORY_METRICS
    }
    windows = {k: v for k, v in metrics.items() if "_w" in k}
    issues = open_issues(session, scope_prefix=f"shop:{shop.shop_key}")
    dq_critical = sorted({i.check_name for i in issues if i.severity == "CRITICAL"})
    dq_watch = sorted({i.check_name for i in issues if i.severity == "WATCH"})
    dsl, recent = days_since_last_change(session, account, day, as_of)
    exps = (
        session.execute(
            select(Experiment).where(Experiment.shop_id == shop.id, Experiment.status == "RUNNING")
        )
        .scalars()
        .all()
    )
    entities: list[EntityContext] = []
    conc: dict[str, Any] = {"top_share": None}
    if account is not None:
        cmap = creative_map(session, account)
        w_start, w_end = preceding_window(day + timedelta(days=1), 7)
        attributed_by_ad: dict[str, Decimal] = {}
        ads = session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars().all()
        adsets_by_id = {
            a.id: a
            for a in session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars()
        }
        for ad in ads:
            em = _metric_map(session, "ad", ad.external_id, day, as_of)
            chain = {ad.id, ad.adset_id} | (
                {adsets_by_id[ad.adset_id].campaign_id} if ad.adset_id in adsets_by_id else set()
            )
            ad_dsl, _ = days_since_last_change(session, account, day, as_of, only_ids=chain)
            first = session.execute(
                select(AdInsight.business_date)
                .where(AdInsight.ad_id == ad.id, AdInsight.hour == -1)
                .order_by(AdInsight.business_date)
                .limit(1)
            ).scalar()
            if first is None:
                continue
            spend_total, purchases_total = spend_since(
                session, ad_external_id=ad.external_id, start=first, end=day, as_of=as_of
            )
            rows = latest_metric_rows(
                session,
                scope="ad",
                key=ad.external_id,
                metric="attributed_revenue",
                start=w_start,
                end=w_end,
                as_of=as_of,
            )
            attributed_by_ad[ad.external_id] = sum(
                (r.value or Decimal(0) for r in rows.values()), start=Decimal(0)
            )
            entities.append(
                EntityContext(
                    ref=f"ad:{ad.external_id}",
                    name=ad.name,
                    metrics=em,
                    spend_since_start=spend_total,
                    purchases_since_start=purchases_total,
                    days_running=(day - first).days + 1,
                    product_key=product_key_for_sku(None, None),
                    creative_key=cmap.get(ad.external_id),
                    days_since_change=ad_dsl,
                )
            )
        conc = concentration(attributed_by_ad, cmap)
    pp = policies.product(shop.shop_key, shop.shop_key)
    orders_y = int(metrics.get("orders", MetricValue(metric="orders")).value or 0)
    return ShopContext(
        shop_key=shop.shop_key,
        day=day,
        metrics=metrics,
        history=history,
        windows=windows,
        entities=entities,
        dq_critical=dq_critical,
        dq_watch=dq_watch,
        sources_fresh=sources_fresh,
        pagination_complete=pagination_complete,
        windows_compatible=windows_compatible,
        days_since_last_change=dsl,
        recent_changes=recent,
        active_experiments=[{"id": str(e.id), "kind": e.kind, "hypothesis": e.hypothesis} for e in exps],
        concentration=conc,
        orders_yesterday=orders_y,
        policies=policies,
        target_cpa=pp.target_cpa_pln if pp else None,
        test_loss_cap=pp.test_loss_cap_pln if pp else None,
        stock_known=None,
    )


def diagnose(
    session: Session, *, shop: Shop, day: date, as_of: datetime, policies: PoliciesConfig
) -> tuple[ShopContext, list[RuleResult]]:
    issues = open_issues(session, scope_prefix=f"shop:{shop.shop_key}")
    checks = {i.check_name for i in issues}
    fresh = not any(c.endswith("_stale") or c.endswith("_never_synced") for c in checks)
    complete = not any(c.endswith("_pagination_incomplete") for c in checks)
    compatible = not any(c in ("currency_mismatch", "timezone_mismatch") for c in checks)
    ctx = build_context(
        session,
        shop=shop,
        day=day,
        as_of=as_of,
        policies=policies,
        sources_fresh=fresh,
        pagination_complete=complete,
        windows_compatible=compatible,
    )
    return ctx, prioritize(run_rules(ctx))
