"""DB-backed metric computation for one shop and one business day, plus rolling windows.

Writes: order_attribution, order_costs, cohort_metrics, daily_metrics (scope shop/campaign/adset/ad).
Every value carries `as_of`; readers pass the same `as_of` to avoid look-ahead leakage in replays."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from director.contracts.common import MetricValue
from director.db.models import (
    Ad,
    AdInsight,
    AdSet,
    Campaign,
    CohortMetric,
    DailyMetric,
    EntitySnapshot,
    Order,
    OrderAttribution,
    OrderCost,
    Refund,
    Settlement,
    Shop,
    SourceAccount,
)
from director.metrics import attribution as attr
from director.metrics.cohorts import expected_outcome, fit_distribution, maturity_days
from director.metrics.costs import cost_rules_for_shop, product_key_for_sku
from director.metrics.economics import (
    AdTotals,
    OrderTotals,
    breakeven,
    business_metrics,
    media_metrics,
    safe_ratio,
)
from director.metrics.ledger import FINAL_STATES, LedgerItem, LedgerOrder

D0 = Decimal("0")
WINDOWS = (3, 7, 30)


@dataclass
class ShopDayResult:
    shop_key: str
    day: date
    as_of: datetime
    metrics: dict[str, MetricValue] = field(default_factory=dict)
    entity_metrics: dict[str, dict[str, MetricValue]] = field(default_factory=dict)  # "ad:<ext>" -> metrics
    coverage: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    cohort: dict[str, Any] = field(default_factory=dict)


def build_ad_index(session: Session, account: SourceAccount) -> attr.AdIndex:
    idx = attr.AdIndex(source_account_id=account.id)
    camps = session.execute(select(Campaign).where(Campaign.source_account_id == account.id)).scalars().all()
    adsets = session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars().all()
    ads = session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars().all()
    camp_by_id = {c.id: c for c in camps}
    adset_by_id = {a.id: a for a in adsets}
    for c in camps:
        idx.campaigns_by_external[c.external_id] = {"id": c.id, "name": c.name}
        idx.campaigns_by_name.setdefault(c.name, []).append(c.external_id)
    for a in adsets:
        idx.adsets_by_external[a.external_id] = {"id": a.id, "campaign_id": a.campaign_id, "name": a.name}
    for ad in ads:
        adset = adset_by_id.get(ad.adset_id)
        idx.ads_by_external[ad.external_id] = {
            "id": ad.id,
            "adset_id": ad.adset_id,
            "campaign_id": adset.campaign_id if adset else None,
            "name": ad.name,
        }
        idx.ads_by_name.setdefault(ad.name, []).append(ad.external_id)
    # historical aliases: names an ad carried in past snapshots, when unique across all ads
    name_hits: dict[str, set[str]] = defaultdict(set)
    ad_by_uuid = {ad.id: ad.external_id for ad in ads}
    for snap in session.execute(
        select(EntitySnapshot).where(
            EntitySnapshot.entity_type == "ad", EntitySnapshot.entity_id.in_(list(ad_by_uuid.keys()))
        )
    ).scalars():
        nm = (snap.attributes or {}).get("name")
        if nm:
            name_hits[nm].add(ad_by_uuid[snap.entity_id])
    for nm, ids in name_hits.items():
        if len(ids) == 1 and len(idx.ads_by_name.get(nm, [])) <= 1:
            idx.aliases_by_name[nm] = next(iter(ids))
    _ = camp_by_id
    return idx


def _meta_account(session: Session, shop: Shop) -> SourceAccount | None:
    return session.execute(
        select(SourceAccount).where(
            SourceAccount.shop_id == shop.id, SourceAccount.source == "meta", SourceAccount.active.is_(True)
        )
    ).scalar_one_or_none()


def _clear_same_as_of(
    session: Session,
    *,
    scopes_keys: list[tuple[str, str]],
    day: date,
    as_of: datetime,
    only_windows: bool = False,
) -> None:
    """At-least-once safety: a re-run at the identical `as_of` replaces its own rows instead of violating uniqueness."""
    for scope, key in scopes_keys:
        stmt = delete(DailyMetric).where(
            DailyMetric.scope == scope,
            DailyMetric.entity_key == key,
            DailyMetric.business_date == day,
            DailyMetric.as_of == as_of,
        )
        if only_windows:
            stmt = stmt.where(DailyMetric.metric.like("%\\_w%", escape="\\"))
        else:
            stmt = stmt.where(~DailyMetric.metric.like("%\\_w%", escape="\\"))
        session.execute(stmt)
    if not only_windows:
        for scope, key in scopes_keys:
            if scope == "shop":
                session.execute(
                    delete(CohortMetric).where(
                        CohortMetric.scope == "shop",
                        CohortMetric.entity_key == key,
                        CohortMetric.cohort_date == day,
                        CohortMetric.as_of == as_of,
                    )
                )


def _write_metric(
    session: Session,
    *,
    scope: str,
    key: str,
    day: date,
    mv: MetricValue,
    as_of: datetime,
    quality: str = "OK",
) -> str:
    eid = f"metric:{mv.metric}:{scope}:{key}:{day.isoformat()}"
    session.add(
        DailyMetric(
            scope=scope,
            entity_key=key,
            business_date=day,
            metric=mv.metric,
            metric_version=mv.definition_version,
            as_of=as_of,
            numerator=mv.numerator,
            denominator=mv.denominator,
            value=mv.value,
            reason=mv.reason,
            quality=quality if not mv.flags else ",".join(mv.flags)[:16],
            evidence_id=eid,
        )
    )
    return eid


def _to_ledger(order: Order, product_keys: dict[uuid.UUID, str | None], refunds: list[Refund]) -> LedgerOrder:
    items = [
        LedgerItem(
            product_keys.get(i.id),
            i.quantity,
            i.unit_price_gross,
            i.discount_amount,
            i.returned_qty,
            i.recovered_qty,
        )
        for i in order.items
    ]
    refund_total = sum((r.amount for r in refunds), start=D0)
    return LedgerOrder(
        order.business_date,
        order.payment_kind,
        order.status_class,
        items,
        order.shipping_amount,
        refund_total,
        sum((r.return_shipping_cost or D0 for r in refunds), start=D0),
        (all(r.goods_recovered for r in refunds) if refunds else None),
    )


def compute_shop_day(
    session: Session,
    *,
    shop: Shop,
    day: date,
    as_of: datetime,
    target_cpa: dict[str, Decimal | None] | None = None,
) -> ShopDayResult:
    res = ShopDayResult(shop.shop_key, day, as_of)
    account = _meta_account(session, shop)
    keys = scope_keys(session, shop)
    _clear_same_as_of(
        session,
        scopes_keys=[("shop", shop.shop_key)] + [(sc, k) for sc, ks in keys.items() for k in ks],
        day=day,
        as_of=as_of,
    )
    rules = cost_rules_for_shop(session, shop)
    orders = (
        session.execute(
            select(Order).where(
                Order.shop_id == shop.id, Order.business_date == day, Order.last_synced_at <= as_of
            )
        )
        .scalars()
        .all()
    )
    valid = [o for o in orders if o.is_valid]
    product_keys = {i.id: product_key_for_sku(i.sku, i.name) for o in orders for i in o.items}
    refunds_by_order: dict[uuid.UUID, list[Refund]] = defaultdict(list)
    if orders:
        for r in session.execute(
            select(Refund).where(Refund.order_id.in_([o.id for o in orders]), Refund.observed_at <= as_of)
        ).scalars():
            refunds_by_order[r.order_id].append(r)

    # --- cohort state distributions from mature orders --------------------------------------
    dists: dict[tuple[str, str | None], Any] = {}
    horizon_start = day - timedelta(days=120)

    def dist_for(payment_kind: str, product_key: str | None):
        key = (payment_kind, product_key)
        if key in dists:
            return dists[key]
        mature_before = as_of - timedelta(days=maturity_days(payment_kind))
        q = select(Order.status_class, Order.id).where(
            Order.shop_id == shop.id,
            Order.payment_kind == payment_kind,
            Order.business_date >= horizon_start,
            Order.created_at_source <= mature_before,
            Order.is_valid.is_(True),
            Order.last_synced_at <= as_of,
        )
        rows = session.execute(q).all()
        finals = [s for s, _ in rows if s in FINAL_STATES]
        # right-censoring: open-but-mature orders count as DELIVERED only if older than 2x maturity (COD payouts lag), else excluded
        very_old = as_of - timedelta(days=2 * maturity_days(payment_kind))
        for s, oid in rows:
            if s == "OPEN":
                o = session.get(Order, oid)
                if o and o.created_at_source <= very_old:
                    finals.append("DELIVERED")
        d = fit_distribution(finals, payment_kind, "shop")
        dists[key] = d
        return d

    # --- attribution ------------------------------------------------------------------------
    idx = build_ad_index(session, account) if account else attr.AdIndex()
    attributed: list[tuple[attr.AttributionResult, Decimal]] = []
    per_ad_orders: dict[uuid.UUID, OrderTotals] = defaultdict(OrderTotals)
    per_adset_orders: dict[uuid.UUID, OrderTotals] = defaultdict(OrderTotals)
    per_camp_orders: dict[uuid.UUID, OrderTotals] = defaultdict(OrderTotals)
    totals = OrderTotals()
    exp_sum: Decimal | None = D0
    exp_low: Decimal | None = D0
    exp_high: Decimal | None = D0
    realized_sum: Decimal | None = D0
    realized_n = 0
    missing_costs: set[str] = set()
    contrib_before_ads: list[Decimal] = []
    for o in valid:
        parsed = attr.parse_utm(o.original_utm)
        result = attr.attribute(parsed, idx)
        _upsert_attribution(session, o, result, parsed, account)
        attributed.append((result, o.gross_amount))
        ledger = _to_ledger(o, product_keys, refunds_by_order.get(o.id, []))
        pk = next((product_keys.get(i.id) for i in o.items), None)
        eo = expected_outcome(ledger, dist_for(o.payment_kind, pk), rules)
        _upsert_costs(session, o, eo, day)
        ot = OrderTotals(
            orders=1,
            revenue=o.gross_amount,
            attributed_orders=1 if result.level != "UNKNOWN" else 0,
            attributed_revenue=o.gross_amount if result.level != "UNKNOWN" else D0,
            expected_contribution=eo.expected_contribution,
        )
        totals = totals + ot
        if eo.missing_costs:
            missing_costs.update(eo.missing_costs)
            exp_sum = exp_low = exp_high = None
        elif exp_sum is not None:
            exp_sum += eo.expected_contribution or D0
            exp_low += eo.low or D0
            exp_high += eo.high or D0
            contrib_before_ads.append(eo.expected_contribution or D0)
        if o.status_class in FINAL_STATES and realized_sum is not None:
            if eo.expected_contribution is None:
                realized_sum = None
            else:
                realized_sum += eo.expected_contribution
                realized_n += 1
        if result.ad_id:
            per_ad_orders[result.ad_id] = per_ad_orders[result.ad_id] + ot
        if result.adset_id:
            per_adset_orders[result.adset_id] = per_adset_orders[result.adset_id] + ot
        if result.campaign_id:
            per_camp_orders[result.campaign_id] = per_camp_orders[result.campaign_id] + ot
    totals = OrderTotals(
        totals.orders,
        totals.revenue,
        totals.attributed_orders,
        totals.attributed_revenue,
        exp_sum,
        realized_sum if realized_n else None,
    )
    if missing_costs:
        res.missing.extend(sorted(f"MISSING_COST:{m}" for m in missing_costs))

    # --- media --------------------------------------------------------------------------------
    per_ad_media: dict[uuid.UUID, AdTotals] = {}
    ad_meta: dict[uuid.UUID, tuple[str, uuid.UUID]] = {}
    if account:
        rows = session.execute(
            select(AdInsight, Ad)
            .join(Ad, Ad.id == AdInsight.ad_id)
            .where(
                Ad.source_account_id == account.id,
                AdInsight.business_date == day,
                AdInsight.hour == -1,
                AdInsight.breakdown_key == "none",
                AdInsight.as_of <= as_of,
            )
        ).all()
        for ins, ad in rows:
            per_ad_media[ad.id] = per_ad_media.get(ad.id, AdTotals()) + AdTotals(
                ins.spend, ins.impressions, ins.link_clicks, ins.clicks_all, ins.purchases, ins.purchase_value
            )
            ad_meta[ad.id] = (ad.external_id, ad.adset_id)
    shop_media = sum(per_ad_media.values(), start=AdTotals())
    spend = shop_media.spend if per_ad_media else None
    if spend is None:
        res.missing.append("MISSING_META_SPEND")

    # --- shop metrics ---------------------------------------------------------------------------
    shop_key = shop.shop_key
    metrics: dict[str, MetricValue] = {}
    metrics.update(business_metrics(totals, spend, only_meta_costs=True, window="D"))
    metrics.update(
        media_metrics(shop_media, window="D")
        if per_ad_media
        else {
            k: MetricValue(metric=k, reason="NO_META_DATA")
            for k in ("ctr_link", "cpc_link", "cpm", "cpa_meta", "roas_meta", "spend", "purchases_meta")
        }
    )
    aov = metrics["aov"].value
    per_order_contrib = (
        (sum(contrib_before_ads, start=D0) / len(contrib_before_ads))
        if contrib_before_ads and not missing_costs
        else None
    )
    metrics.update(breakeven(per_order_contrib, aov, window="D"))
    metrics["attributed_orders"] = MetricValue(
        metric="attributed_orders", value=Decimal(totals.attributed_orders), unit="count", window="D"
    )
    metrics["attributed_revenue"] = MetricValue(
        metric="attributed_revenue", value=totals.attributed_revenue, unit="PLN", window="D"
    )
    if exp_low is not None and exp_sum is not None:
        metrics["expected_contribution_low"] = MetricValue(
            metric="expected_contribution_low", value=exp_low, unit="PLN", flags=["ESTIMATED"]
        )
        metrics["expected_contribution_high"] = MetricValue(
            metric="expected_contribution_high", value=exp_high, unit="PLN", flags=["ESTIMATED"]
        )
        if spend is not None:
            metrics["expected_result_low"] = MetricValue(
                metric="expected_result_low", value=exp_low - spend, unit="PLN", flags=["ESTIMATED"]
            )
            metrics["expected_result_high"] = MetricValue(
                metric="expected_result_high", value=exp_high - spend, unit="PLN", flags=["ESTIMATED"]
            )
    cov_ad = attr.coverage(attributed, "AD")
    cov_camp = attr.coverage(attributed, "CAMPAIGN")
    res.coverage = {"ad": cov_ad, "campaign": cov_camp}
    metrics["attribution_coverage_ad_orders"] = safe_ratio(
        "attribution_coverage_ad_orders", cov_ad["orders_matched"], cov_ad["orders_total"], unit="ratio"
    )
    metrics["attribution_coverage_ad_revenue"] = safe_ratio(
        "attribution_coverage_ad_revenue",
        Decimal(cov_ad["revenue_matched"]),
        Decimal(cov_ad["revenue_total"]),
        unit="ratio",
    )
    metrics["attribution_coverage_campaign_orders"] = safe_ratio(
        "attribution_coverage_campaign_orders",
        cov_camp["orders_matched"],
        cov_camp["orders_total"],
        unit="ratio",
    )
    # cashflow view (settlement-date based) - separate from cohort view
    refund_out = session.execute(
        select(func.coalesce(func.sum(Refund.amount), 0))
        .join(Order, Order.id == Refund.order_id)
        .where(Order.shop_id == shop.id, func.date(Refund.occurred_at) == day, Refund.observed_at <= as_of)
    ).scalar()
    settle_in = session.execute(
        select(func.coalesce(func.sum(Settlement.amount), 0))
        .join(Order, Order.id == Settlement.order_id, isouter=True)
        .where(
            Settlement.settlement_date == day,
            Settlement.settlement_type.in_(("COD_PAYOUT", "CARD")),
            Order.shop_id == shop.id,
        )
    ).scalar()
    metrics["refund_outflow"] = MetricValue(
        metric="refund_outflow", value=Decimal(refund_out or 0), unit="PLN"
    )
    metrics["settlement_inflow"] = MetricValue(
        metric="settlement_inflow", value=Decimal(settle_in or 0), unit="PLN"
    )
    for mv in metrics.values():
        _write_metric(session, scope="shop", key=shop_key, day=day, mv=mv, as_of=as_of)
    res.metrics = metrics

    # --- cohort row -----------------------------------------------------------------------------
    unc = "OK"
    for d in dists.values():
        if d.uncertainty == "LOW_SAMPLE":
            unc = "LOW_SAMPLE"
        elif d.uncertainty == "MEDIUM" and unc == "OK":
            unc = "MEDIUM"
    session.add(
        CohortMetric(
            scope="shop",
            entity_key=shop_key,
            cohort_date=day,
            as_of=as_of,
            age_days=(as_of.date() - day).days,
            orders=totals.orders,
            ordered_revenue=totals.revenue,
            expected_contribution=exp_sum,
            expected_low=exp_low,
            expected_high=exp_high,
            realized_contribution=totals.realized_contribution,
            ad_spend=spend,
            uncertainty=unc if not missing_costs else "MISSING_COSTS",
            details={
                "distributions": {f"{k[0]}|{k[1]}": v.as_dict() for k, v in dists.items()},
                "missing_costs": sorted(missing_costs),
            },
        )
    )
    res.cohort = {
        "expected_contribution": str(exp_sum) if exp_sum is not None else None,
        "uncertainty": unc,
        "distributions": len(dists),
    }

    # --- entity metrics (ad / adset / campaign) ------------------------------------------------
    if account:
        adset_media: dict[uuid.UUID, AdTotals] = defaultdict(AdTotals)
        camp_media: dict[uuid.UUID, AdTotals] = defaultdict(AdTotals)
        adsets = {
            a.id: a
            for a in session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars()
        }
        camps = {
            c.id: c
            for c in session.execute(
                select(Campaign).where(Campaign.source_account_id == account.id)
            ).scalars()
        }
        tcpa = (target_cpa or {}).get(shop_key)
        for ad_id, t in per_ad_media.items():
            ext, adset_id = ad_meta[ad_id]
            em = media_metrics(t, window="D")
            ot = per_ad_orders.get(ad_id, OrderTotals())
            em["attributed_orders"] = MetricValue(
                metric="attributed_orders", value=Decimal(ot.attributed_orders), unit="count"
            )
            em["attributed_revenue"] = MetricValue(
                metric="attributed_revenue", value=ot.attributed_revenue, unit="PLN"
            )
            em["cpa_attributed"] = safe_ratio("cpa_attributed", t.spend, ot.attributed_orders, unit="PLN")
            em["expected_contribution"] = (
                MetricValue(
                    metric="expected_contribution",
                    value=ot.expected_contribution,
                    unit="PLN",
                    flags=["ESTIMATED"],
                )
                if ot.expected_contribution is not None
                else MetricValue(metric="expected_contribution", reason="MISSING_COSTS")
            )
            if ot.expected_contribution is not None:
                em["expected_result_after_ads"] = MetricValue(
                    metric="expected_result_after_ads",
                    value=ot.expected_contribution - t.spend,
                    unit="PLN",
                    flags=["ESTIMATED"],
                )
            em["spend_x_target_cpa"] = safe_ratio("spend_x_target_cpa", t.spend, tcpa, unit="x")
            for mv in em.values():
                _write_metric(session, scope="ad", key=ext, day=day, mv=mv, as_of=as_of)
            res.entity_metrics[f"ad:{ext}"] = em
            adset_media[adset_id] = adset_media[adset_id] + t
            adset = adsets.get(adset_id)
            if adset:
                camp_media[adset.campaign_id] = camp_media[adset.campaign_id] + t
        for adset_id, t in adset_media.items():
            adset = adsets[adset_id]
            em = media_metrics(t, window="D")
            ot = per_adset_orders.get(adset_id, OrderTotals())
            em["attributed_orders"] = MetricValue(
                metric="attributed_orders", value=Decimal(ot.attributed_orders), unit="count"
            )
            em["attributed_revenue"] = MetricValue(
                metric="attributed_revenue", value=ot.attributed_revenue, unit="PLN"
            )
            em["cpa_attributed"] = safe_ratio("cpa_attributed", t.spend, ot.attributed_orders, unit="PLN")
            for mv in em.values():
                _write_metric(session, scope="adset", key=adset.external_id, day=day, mv=mv, as_of=as_of)
            res.entity_metrics[f"adset:{adset.external_id}"] = em
        for camp_id, t in camp_media.items():
            camp = camps[camp_id]
            em = media_metrics(t, window="D")
            ot = per_camp_orders.get(camp_id, OrderTotals())
            em["attributed_orders"] = MetricValue(
                metric="attributed_orders", value=Decimal(ot.attributed_orders), unit="count"
            )
            em["attributed_revenue"] = MetricValue(
                metric="attributed_revenue", value=ot.attributed_revenue, unit="PLN"
            )
            em["cpa_attributed"] = safe_ratio("cpa_attributed", t.spend, ot.attributed_orders, unit="PLN")
            for mv in em.values():
                _write_metric(session, scope="campaign", key=camp.external_id, day=day, mv=mv, as_of=as_of)
            res.entity_metrics[f"campaign:{camp.external_id}"] = em
    session.flush()
    return res


def _upsert_attribution(
    session: Session,
    order: Order,
    result: attr.AttributionResult,
    parsed: attr.ParsedUTM,
    account: SourceAccount | None,
) -> None:
    row = session.execute(
        select(OrderAttribution).where(
            OrderAttribution.order_id == order.id, OrderAttribution.model_version == attr.PARSER_VERSION
        )
    ).scalar_one_or_none()
    if row is None:
        row = OrderAttribution(
            order_id=order.id,
            model_version=attr.PARSER_VERSION,
            level="UNKNOWN",
            method="",
            confidence_class="LOW",
            parser_version=attr.PARSER_VERSION,
        )
        session.add(row)
    row.source_account_id = account.id if account else None
    row.campaign_id, row.adset_id, row.ad_id = result.campaign_id, result.adset_id, result.ad_id
    row.level, row.method, row.confidence_class = result.level, result.method, result.confidence
    row.parsed_utm, row.evidence, row.parser_version = parsed.as_dict(), result.evidence, attr.PARSER_VERSION


def _upsert_costs(session: Session, order: Order, eo: Any, day: date) -> None:
    state = order.status_class if order.status_class in FINAL_STATES else "DELIVERED"
    detail = eo.by_state.get(state) or {}
    existing = {
        c.cost_type: c
        for c in session.execute(
            select(OrderCost).where(OrderCost.order_id == order.id, OrderCost.order_item_id.is_(None))
        ).scalars()
    }
    for ct, amt in (detail.get("costs") or {}).items():
        row = existing.get(ct)
        if row is None:
            row = OrderCost(
                order_id=order.id,
                cost_type=ct,
                amount=Decimal(amt),
                currency=order.currency,
                recognition_date=day,
            )
            session.add(row)
        row.amount = Decimal(amt)
        row.is_actual = order.status_class in FINAL_STATES
        row.recognition_date = day


# ------------------------------------------------------------------------------ reads & windows


def latest_metric_rows(
    session: Session,
    *,
    scope: str,
    key: str,
    metric: str,
    start: date,
    end: date,
    as_of: datetime | None = None,
) -> dict[date, DailyMetric]:
    q = select(DailyMetric).where(
        DailyMetric.scope == scope,
        DailyMetric.entity_key == key,
        DailyMetric.metric == metric,
        DailyMetric.business_date >= start,
        DailyMetric.business_date <= end,
    )
    if as_of is not None:
        q = q.where(DailyMetric.as_of <= as_of)
    out: dict[date, DailyMetric] = {}
    for row in session.execute(q.order_by(DailyMetric.business_date, DailyMetric.as_of)).scalars():
        out[row.business_date] = row  # later as_of overrides
    return out


def series(
    session: Session, *, scope: str, key: str, metric: str, dates: list[date], as_of: datetime | None = None
) -> list[Decimal | None]:
    if not dates:
        return []
    rows = latest_metric_rows(
        session, scope=scope, key=key, metric=metric, start=min(dates), end=max(dates), as_of=as_of
    )
    return [rows[d].value if d in rows else None for d in dates]


def window_ratio(
    session: Session,
    *,
    scope: str,
    key: str,
    metric: str,
    start: date,
    end: date,
    as_of: datetime | None = None,
) -> MetricValue:
    """Ratio-of-sums over a window using stored numerators/denominators (never average of daily ratios)."""
    rows = latest_metric_rows(session, scope=scope, key=key, metric=metric, start=start, end=end, as_of=as_of)
    if not rows:
        return MetricValue(metric=metric, reason="NO_DATA", window=f"{start}..{end}")
    nums = [r.numerator for r in rows.values() if r.numerator is not None]
    dens = [r.denominator for r in rows.values() if r.denominator is not None]
    if dens:
        return safe_ratio(metric, sum(nums, start=D0), sum(dens, start=D0), window=f"{start}..{end}")
    vals = [r.value for r in rows.values() if r.value is not None]
    if not vals:
        return MetricValue(
            metric=metric,
            reason=next((r.reason for r in rows.values() if r.reason), "NO_DATA"),
            window=f"{start}..{end}",
        )
    return MetricValue(metric=metric, value=sum(vals, start=D0), window=f"{start}..{end}", flags=["SUM"])


def compute_windows(
    session: Session,
    *,
    scope: str,
    key: str,
    day: date,
    as_of: datetime,
    metrics: tuple[str, ...],
    windows: tuple[int, ...] = WINDOWS,
) -> dict[str, MetricValue]:
    out: dict[str, MetricValue] = {}
    _clear_same_as_of(session, scopes_keys=[(scope, key)], day=day, as_of=as_of, only_windows=True)
    for w in windows:
        start, end = day - timedelta(days=w), day - timedelta(days=1)
        for m in metrics:
            mv = window_ratio(session, scope=scope, key=key, metric=m, start=start, end=end, as_of=as_of)
            mv = mv.model_copy(update={"metric": f"{m}_w{w}"})
            _write_metric(session, scope=scope, key=key, day=day, mv=mv, as_of=as_of)
            out[mv.metric] = mv
    return out


def scope_keys(session: Session, shop: Shop) -> dict[str, list[str]]:
    account = _meta_account(session, shop)
    if account is None:
        return {"ad": [], "adset": [], "campaign": []}
    return {
        "ad": [
            a.external_id
            for a in session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars()
        ],
        "adset": [
            a.external_id
            for a in session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars()
        ],
        "campaign": [
            c.external_id
            for c in session.execute(
                select(Campaign).where(Campaign.source_account_id == account.id)
            ).scalars()
        ],
    }


def spend_since(
    session: Session, *, ad_external_id: str, start: date, end: date, as_of: datetime | None = None
) -> tuple[Decimal, int]:
    q = (
        select(func.coalesce(func.sum(AdInsight.spend), 0), func.coalesce(func.sum(AdInsight.purchases), 0))
        .join(Ad, Ad.id == AdInsight.ad_id)
        .where(
            Ad.external_id == ad_external_id,
            AdInsight.business_date >= start,
            AdInsight.business_date <= end,
            AdInsight.hour == -1,
            AdInsight.breakdown_key == "none",
        )
    )
    if as_of is not None:
        q = q.where(and_(AdInsight.as_of <= as_of))
    s, p = session.execute(q).one()
    return Decimal(s or 0), int(p or 0)
