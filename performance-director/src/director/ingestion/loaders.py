"""Idempotent upserts from normalized records into the ledger / structure tables."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from director.config import ShopConfig
from director.db.models import (
    Ad,
    AdInsight,
    AdSet,
    Campaign,
    DailyMetric,
    EntitySnapshot,
    IngestionBatch,
    MarketAd,
    MarketObservation,
    Order,
    OrderItem,
    OrderStatusEvent,
    Refund,
    Shop,
    SourceAccount,
    StructureChange,
)
from director.ingestion.structure_diff import attributes_hash, diff_attributes
from director.metrics.calendar import business_date_of

STATUS_CLASSES = ("OPEN", "DELIVERED", "CANCELLED", "UNDELIVERED", "RETURNED")


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def classify_status(status_id: str, status_name: str | None, shop: ShopConfig) -> str:
    if status_id in shop.cancelled_statuses:
        return "CANCELLED"
    if status_id in shop.returned_statuses:
        return "RETURNED"
    if status_id in shop.delivered_statuses:
        return "DELIVERED"
    name = (status_name or status_id or "").lower()
    if any(k in name for k in ("anulow", "cancel")):
        return "CANCELLED"
    if any(k in name for k in ("zwrot", "zwróc", "return", "refund")):
        return "RETURNED"
    if any(k in name for k in ("nieodebr", "niedoręcz", "niedorecz", "undeliver", "odmowa")):
        return "UNDELIVERED"
    if any(k in name for k in ("dostarcz", "deliver", "zrealiz", "complete")):
        return "DELIVERED"
    return "OPEN"


def upsert_orders(
    session: Session,
    *,
    shop: Shop,
    shop_cfg: ShopConfig,
    account: SourceAccount,
    records: list[dict[str, Any]],
    observed_at: datetime,
    status_names: dict[str, str] | None = None,
) -> dict[str, int]:
    status_names = status_names or {}
    created = updated = events = 0
    existing = (
        {
            o.external_order_id: o
            for o in session.execute(
                select(Order).where(
                    Order.source_account_id == account.id,
                    Order.external_order_id.in_([r["external_order_id"] for r in records]),
                )
            ).scalars()
        }
        if records
        else {}
    )
    for r in records:
        created_at = _dt(r["created_at"])
        confirmed_at = _dt(r.get("confirmed_at"))
        basis_dt = (confirmed_at or created_at) if shop_cfg.order_date_basis == "confirmed" else created_at
        biz_date = business_date_of(basis_dt, shop_cfg.timezone)
        status_id = str(r["status_id"])
        status_class = classify_status(
            status_id, status_names.get(status_id) or r.get("status_name"), shop_cfg
        )
        is_valid = status_class != "CANCELLED" and not r.get("is_test", False)
        order = existing.get(r["external_order_id"])
        status_changed_at = _dt(r.get("status_changed_at")) or observed_at
        if order is None:
            order = Order(
                source_account_id=account.id,
                shop_id=shop.id,
                external_order_id=r["external_order_id"],
                created_at_source=created_at,
                confirmed_at_source=confirmed_at,
                paid_at_source=_dt(r.get("paid_at")),
                business_date=biz_date,
                payment_kind=r.get("payment_kind", "UNKNOWN"),
                payment_method=r.get("payment_method"),
                current_status=status_id,
                status_class=status_class,
                currency=r["currency"],
                gross_amount=Decimal(r["gross_amount"]),
                products_amount=Decimal(r.get("products_amount", "0")),
                shipping_amount=Decimal(r.get("shipping_amount", "0")),
                discount_amount=Decimal(r.get("discount_amount", "0")),
                is_valid=is_valid,
                is_test=bool(r.get("is_test", False)),
                original_utm=r.get("utm") or {},
                customer_hash=r.get("customer_hash"),
                source_payload_hash=r.get("payload_hash"),
                last_synced_at=observed_at,
            )
            session.add(order)
            session.flush()
            existing[order.external_order_id] = order
            created += 1
            session.add(
                OrderStatusEvent(
                    order_id=order.id,
                    source_event_hash=_event_hash(
                        order.external_order_id, None, status_id, status_changed_at
                    ),
                    event_at=status_changed_at,
                    observed_at=observed_at,
                    before_status=None,
                    after_status=status_id,
                    after_class=status_class,
                )
            )
            events += 1
        else:
            changed = order.source_payload_hash != r.get("payload_hash")
            if order.current_status != status_id:
                session.add(
                    OrderStatusEvent(
                        order_id=order.id,
                        source_event_hash=_event_hash(
                            order.external_order_id, order.current_status, status_id, status_changed_at
                        ),
                        event_at=status_changed_at,
                        observed_at=observed_at,
                        before_status=order.current_status,
                        after_status=status_id,
                        after_class=status_class,
                    )
                )
                events += 1
                order.current_status = status_id
                order.status_class = status_class
                order.is_valid = is_valid
                changed = True
            if changed:
                order.confirmed_at_source = confirmed_at
                order.paid_at_source = _dt(r.get("paid_at"))
                order.business_date = biz_date
                order.gross_amount = Decimal(r["gross_amount"])
                order.products_amount = Decimal(r.get("products_amount", "0"))
                order.shipping_amount = Decimal(r.get("shipping_amount", "0"))
                order.discount_amount = Decimal(r.get("discount_amount", "0"))
                order.original_utm = r.get("utm") or order.original_utm
                order.source_payload_hash = r.get("payload_hash")
                updated += 1
            order.last_synced_at = observed_at
        _upsert_items(session, order, r.get("items", []))
    return {"created": created, "updated": updated, "status_events": events}


def _event_hash(ext_id: str, before: str | None, after: str, at: datetime) -> str:
    return hashlib.sha256(f"{ext_id}|{before}|{after}|{at.isoformat()}".encode()).hexdigest()


def _upsert_items(session: Session, order: Order, items: list[dict[str, Any]]) -> None:
    current = {i.source_line_id: i for i in order.items}
    for it in items:
        line = str(it["line_id"])
        row = current.get(line)
        if row is None:
            row = OrderItem(
                order_id=order.id,
                source_line_id=line,
                quantity=int(it["quantity"]),
                unit_price_gross=Decimal(it["unit_price_gross"]),
            )
            order.items.append(row)
        row.external_product_id = it.get("external_product_id")
        row.sku = it.get("sku")
        row.name = it.get("name")
        row.quantity = int(it["quantity"])
        row.unit_price_gross = Decimal(it["unit_price_gross"])
        row.tax_rate = Decimal(it["tax_rate"]) if it.get("tax_rate") else None
        row.discount_amount = Decimal(it.get("discount_amount", "0"))
        row.bundle_key = it.get("bundle_key")
        if it.get("returned_qty") is not None:
            row.returned_qty = int(it["returned_qty"])
        if it.get("recovered_qty") is not None:
            row.recovered_qty = int(it["recovered_qty"])


def upsert_refunds(
    session: Session, *, account: SourceAccount, records: list[dict[str, Any]], observed_at: datetime
) -> int:
    n = 0
    for r in records:
        order = session.execute(
            select(Order).where(
                Order.source_account_id == account.id, Order.external_order_id == str(r["external_order_id"])
            )
        ).scalar_one_or_none()
        if order is None:
            continue
        existing = session.execute(
            select(Refund).where(Refund.source == account.source, Refund.external_id == str(r["external_id"]))
        ).scalar_one_or_none()
        if existing:
            continue
        session.add(
            Refund(
                source=account.source,
                external_id=str(r["external_id"]),
                order_id=order.id,
                occurred_at=_dt(r["occurred_at"]),
                observed_at=observed_at,
                amount=Decimal(r["amount"]),
                currency=r.get("currency", order.currency),
                refund_type=r.get("refund_type", "FULL"),
                goods_recovered=bool(r.get("goods_recovered", False)),
                return_shipping_cost=Decimal(r["return_shipping_cost"])
                if r.get("return_shipping_cost")
                else None,
            )
        )
        rt = r.get("refund_type", "FULL")
        if rt in ("FULL", "UNDELIVERED") and order.status_class in ("OPEN", "DELIVERED"):
            new_class = "UNDELIVERED" if rt == "UNDELIVERED" else "RETURNED"
            session.add(
                OrderStatusEvent(
                    order_id=order.id,
                    source_event_hash=_event_hash(
                        order.external_order_id,
                        order.current_status,
                        f"refund:{r['external_id']}",
                        _dt(r["occurred_at"]),
                    ),
                    event_at=_dt(r["occurred_at"]),
                    observed_at=observed_at,
                    before_status=order.current_status,
                    after_status=f"refund:{rt}",
                    after_class=new_class,
                )
            )
            order.status_class = new_class
        n += 1
    return n


# ------------------------------------------------------------------------------- structure


def _snapshot(
    session: Session,
    entity_type: str,
    entity_id: uuid.UUID,
    attrs: dict[str, Any],
    observed_at: datetime,
    batch: IngestionBatch | None,
) -> None:
    h = attributes_hash(attrs)
    last = session.execute(
        select(EntitySnapshot)
        .where(EntitySnapshot.entity_type == entity_type, EntitySnapshot.entity_id == entity_id)
        .order_by(EntitySnapshot.valid_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last is not None and last.attributes_hash == h:
        last.observed_at = observed_at
        return
    for field, before, after in diff_attributes(last.attributes if last else None, attrs):
        session.add(
            StructureChange(
                entity_type=entity_type,
                entity_id=entity_id,
                field=field,
                before=before,
                after=after,
                observed_from=last.observed_at if last else observed_at,
                observed_to=observed_at,
                batch_id=batch.id if batch else None,
            )
        )
    session.add(
        EntitySnapshot(
            entity_type=entity_type,
            entity_id=entity_id,
            valid_at=observed_at,
            observed_at=observed_at,
            attributes=attrs,
            attributes_hash=h,
            batch_id=batch.id if batch else None,
        )
    )


def upsert_structure(
    session: Session,
    *,
    account: SourceAccount,
    records: list[dict[str, Any]],
    observed_at: datetime,
    batch: IngestionBatch | None = None,
) -> dict[str, int]:
    counts = {"campaign": 0, "adset": 0, "ad": 0}
    campaigns = {
        c.external_id: c
        for c in session.execute(select(Campaign).where(Campaign.source_account_id == account.id)).scalars()
    }
    adsets = {
        a.external_id: a
        for a in session.execute(select(AdSet).where(AdSet.source_account_id == account.id)).scalars()
    }
    ads = {
        a.external_id: a
        for a in session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars()
    }
    dec = lambda v: Decimal(v) if v not in (None, "") else None  # noqa: E731
    for r in [x for x in records if x["kind"] == "campaign"]:
        c = campaigns.get(r["external_id"])
        if c is None:
            c = Campaign(source_account_id=account.id, external_id=r["external_id"], name=r["name"])
            session.add(c)
            campaigns[c.external_id] = c
        c.name, c.objective = r["name"], r.get("objective")
        c.configured_status, c.effective_status = r.get("configured_status"), r.get("effective_status")
        c.daily_budget, c.lifetime_budget, c.budget_type = (
            dec(r.get("daily_budget")),
            dec(r.get("lifetime_budget")),
            r.get("budget_type"),
        )
        c.metadata_, c.last_seen_at = r.get("metadata") or {}, observed_at
        session.flush()
        _snapshot(
            session,
            "campaign",
            c.id,
            {
                k: r.get(k)
                for k in (
                    "name",
                    "configured_status",
                    "effective_status",
                    "daily_budget",
                    "lifetime_budget",
                    "budget_type",
                )
            },
            observed_at,
            batch,
        )
        counts["campaign"] += 1
    for r in [x for x in records if x["kind"] == "adset"]:
        parent = campaigns.get(r["campaign_external_id"])
        if parent is None:
            parent = Campaign(
                source_account_id=account.id,
                external_id=r["campaign_external_id"],
                name=f"(unknown campaign {r['campaign_external_id']})",
            )
            session.add(parent)
            session.flush()
            campaigns[parent.external_id] = parent
        a = adsets.get(r["external_id"])
        if a is None:
            a = AdSet(
                source_account_id=account.id,
                campaign_id=parent.id,
                external_id=r["external_id"],
                name=r["name"],
            )
            session.add(a)
            adsets[a.external_id] = a
        a.campaign_id, a.name = parent.id, r["name"]
        a.configured_status, a.effective_status = r.get("configured_status"), r.get("effective_status")
        a.daily_budget, a.lifetime_budget = dec(r.get("daily_budget")), dec(r.get("lifetime_budget"))
        a.targeting, a.metadata_, a.last_seen_at = (
            r.get("targeting") or {},
            r.get("metadata") or {},
            observed_at,
        )
        session.flush()
        _snapshot(
            session,
            "adset",
            a.id,
            {
                k: r.get(k)
                for k in (
                    "name",
                    "configured_status",
                    "effective_status",
                    "daily_budget",
                    "lifetime_budget",
                    "targeting",
                )
            },
            observed_at,
            batch,
        )
        counts["adset"] += 1
    for r in [x for x in records if x["kind"] == "ad"]:
        parent = adsets.get(r["adset_external_id"])
        if parent is None:
            camp = campaigns.get(r.get("campaign_external_id") or "")
            if camp is None:
                camp = Campaign(
                    source_account_id=account.id,
                    external_id=r.get("campaign_external_id") or f"unknown-{r['adset_external_id']}",
                    name="(unknown campaign)",
                )
                session.add(camp)
                session.flush()
                campaigns[camp.external_id] = camp
            parent = AdSet(
                source_account_id=account.id,
                campaign_id=camp.id,
                external_id=r["adset_external_id"],
                name=f"(unknown adset {r['adset_external_id']})",
            )
            session.add(parent)
            session.flush()
            adsets[parent.external_id] = parent
        ad = ads.get(r["external_id"])
        if ad is None:
            ad = Ad(
                source_account_id=account.id, adset_id=parent.id, external_id=r["external_id"], name=r["name"]
            )
            session.add(ad)
            ads[ad.external_id] = ad
        ad.adset_id, ad.name = parent.id, r["name"]
        ad.configured_status, ad.effective_status = r.get("configured_status"), r.get("effective_status")
        ad.post_id, ad.asset_ids, ad.asset_hash = (
            r.get("post_id"),
            r.get("asset_ids") or [],
            r.get("asset_hash"),
        )
        ad.destination_url, ad.url_tags, ad.metadata_, ad.last_seen_at = (
            r.get("destination_url"),
            r.get("url_tags"),
            r.get("metadata") or {},
            observed_at,
        )
        session.flush()
        _snapshot(
            session,
            "ad",
            ad.id,
            {
                k: r.get(k)
                for k in (
                    "name",
                    "configured_status",
                    "effective_status",
                    "post_id",
                    "url_tags",
                    "destination_url",
                )
            },
            observed_at,
            batch,
        )
        counts["ad"] += 1
    return counts


def upsert_insights(
    session: Session,
    *,
    account: SourceAccount,
    records: list[dict[str, Any]],
    as_of: datetime,
    batch: IngestionBatch | None = None,
    currency: str = "PLN",
) -> int:
    ads = {
        a.external_id: a
        for a in session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars()
    }
    n = 0
    for r in records:
        ad = ads.get(r["ad_external_id"])
        if (
            ad is None
        ):  # insights for an ad missing from structure (deleted/archived) -> placeholder hierarchy
            placeholder = [
                {
                    "kind": "campaign",
                    "external_id": r.get("campaign_external_id") or "unknown",
                    "name": "(from insights)",
                },
                {
                    "kind": "adset",
                    "external_id": r.get("adset_external_id") or "unknown",
                    "campaign_external_id": r.get("campaign_external_id") or "unknown",
                    "name": "(from insights)",
                },
                {
                    "kind": "ad",
                    "external_id": r["ad_external_id"],
                    "adset_external_id": r.get("adset_external_id") or "unknown",
                    "campaign_external_id": r.get("campaign_external_id") or "unknown",
                    "name": r.get("ad_name") or "(from insights)",
                },
            ]
            upsert_structure(session, account=account, records=placeholder, observed_at=as_of, batch=batch)
            ad = session.execute(
                select(Ad).where(Ad.source_account_id == account.id, Ad.external_id == r["ad_external_id"])
            ).scalar_one()
            ads[ad.external_id] = ad
        biz_date = date.fromisoformat(r["date"])
        hour = int(r.get("hour", -1))
        breakdown = "window" if r.get("window") else "none"
        row = session.execute(
            select(AdInsight).where(
                AdInsight.ad_id == ad.id,
                AdInsight.business_date == biz_date,
                AdInsight.hour == hour,
                AdInsight.breakdown_key == breakdown,
                AdInsight.attribution_key == r["attribution_key"],
            )
        ).scalar_one_or_none()
        if row is None:
            row = AdInsight(
                ad_id=ad.id,
                business_date=biz_date,
                hour=hour,
                breakdown_key=breakdown,
                attribution_key=r["attribution_key"],
                as_of=as_of,
            )
            session.add(row)
        row.action_report_time = r.get("action_report_time", "conversion")
        row.spend, row.currency = Decimal(r["spend"]), currency
        row.impressions, row.reach = int(r["impressions"]), r.get("reach")
        row.clicks_all, row.link_clicks, row.outbound_clicks = (
            int(r["clicks_all"]),
            int(r["link_clicks"]),
            r.get("outbound_clicks"),
        )
        row.landing_page_views, row.add_to_cart, row.initiate_checkout = (
            r.get("landing_page_views"),
            r.get("add_to_cart"),
            r.get("initiate_checkout"),
        )
        row.purchases, row.purchase_value = int(r["purchases"]), Decimal(r["purchase_value"])
        row.actions_raw, row.batch_id, row.as_of = (
            r.get("actions_raw") or [],
            batch.id if batch else None,
            as_of,
        )
        n += 1
    return n


def upsert_panel_rows(
    session: Session, *, shop_key: str, records: list[dict[str, Any]], as_of: datetime
) -> int:
    """Nailuks aggregates -> daily_metrics(scope='panel'). Only numeric fields are kept."""
    n = 0
    dates = sorted({date.fromisoformat(r["_date"]) for r in records if r.get("_date")})
    if dates:  # at-least-once safety: replace this shop's panel rows for the same as_of
        session.execute(
            delete(DailyMetric).where(
                DailyMetric.scope == "panel",
                DailyMetric.entity_key == shop_key,
                DailyMetric.as_of == as_of,
                DailyMetric.business_date.in_(dates),
            )
        )
    for r in records:
        if not r.get("_date"):
            continue
        d = date.fromisoformat(r["_date"])
        for k, v in r.items():
            if k.startswith("_") or k in ("date", "day", "shop"):
                continue
            try:
                val = Decimal(str(v))
            except Exception:
                continue
            session.add(
                DailyMetric(
                    scope="panel",
                    entity_key=shop_key,
                    business_date=d,
                    metric=f"panel_{k}",
                    as_of=as_of,
                    value=val,
                    numerator=val,
                    denominator=None,
                    quality="OK",
                    evidence_id=f"metric:panel_{k}:{shop_key}:{d.isoformat()}",
                )
            )
            n += 1
    return n


def upsert_market_ads(
    session: Session,
    *,
    records: list[dict[str, Any]],
    observed_on: date,
    batch: IngestionBatch | None,
    basket_by_brand: dict[str, str],
) -> dict[str, int]:
    created = observed = 0
    seen_media: set[str] = set()
    for r in records:
        if r.get("media_hash") and r["media_hash"] in seen_media:
            continue  # dedupe identical media within a scan
        if r.get("media_hash"):
            seen_media.add(r["media_hash"])
        ad = session.execute(
            select(MarketAd).where(
                MarketAd.source == r.get("_source", "gethooked"), MarketAd.external_id == r["external_id"]
            )
        ).scalar_one_or_none()
        if ad is None:
            ad = MarketAd(
                source=r.get("_source", "gethooked"),
                external_id=r["external_id"],
                brand=r["brand"],
                basket=basket_by_brand.get(r["brand"].lower()),
                media_hash=r.get("media_hash"),
                media_ref=r.get("media_ref"),
                countries=r.get("countries") or [],
                taxonomy=r.get("taxonomy") or {},
                transcript_available=bool(r.get("transcript")),
            )
            session.add(ad)
            session.flush()
            created += 1
        fs, ls = r.get("first_seen"), r.get("last_seen")
        if fs:
            ad.first_seen = min(filter(None, [ad.first_seen, date.fromisoformat(fs)]))
        if ls:
            ad.last_seen = max(filter(None, [ad.last_seen, date.fromisoformat(ls)]))
        obs = session.execute(
            select(MarketObservation).where(
                MarketObservation.market_ad_id == ad.id, MarketObservation.observed_on == observed_on
            )
        ).scalar_one_or_none()
        if obs is None:
            session.add(
                MarketObservation(
                    market_ad_id=ad.id,
                    observed_on=observed_on,
                    coverage=r.get("_source", "gethooked"),
                    evidence={"hook": r.get("hook"), "format": r.get("format")},
                    batch_id=batch.id if batch else None,
                )
            )
            observed += 1
    return {"created": created, "observed": observed}
