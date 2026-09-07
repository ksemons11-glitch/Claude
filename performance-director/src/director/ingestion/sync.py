"""Sync orchestration: adapter -> raw batch -> loaders -> checkpoint. Each function is idempotent
and safe to re-run (at-least-once semantics)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.adapters.base import SyncRequest
from director.config import ShopConfig
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind
from director.db.models import Order, Shop, SourceAccount
from director.ingestion import loaders
from director.ingestion.checkpoints import get_checkpoint, mark_failure, mark_success
from director.ingestion.raw import store_batch
from director.services import Services


def ensure_reference_data(session: Session, svc: Services) -> dict[str, Shop]:
    """Create shops / source accounts from YAML config (idempotent)."""
    shops: dict[str, Shop] = {}
    for cfg in svc.config.shops.shops:
        shop = session.execute(select(Shop).where(Shop.shop_key == cfg.shop_key)).scalar_one_or_none()
        if shop is None:
            shop = Shop(shop_key=cfg.shop_key, name=cfg.name, domain=cfg.domain)
            session.add(shop)
        shop.name, shop.domain, shop.timezone, shop.currency, shop.active = (
            cfg.name,
            cfg.domain,
            cfg.timezone,
            cfg.currency,
            cfg.active,
        )
        shop.order_date_basis, shop.tax_basis, shop.aliases = cfg.order_date_basis, cfg.tax_basis, cfg.aliases
        session.flush()
        shops[cfg.shop_key] = shop
        for source, ext in (
            (SourceKind.META, cfg.meta_account_id),
            (SourceKind.BASELINKER, cfg.baselinker_shop_id),
            (SourceKind.NAILUKS, cfg.nailuks_shop_ref),
        ):
            if not ext:
                continue
            acct = session.execute(
                select(SourceAccount).where(
                    SourceAccount.source == source.value, SourceAccount.external_id == ext
                )
            ).scalar_one_or_none()
            if acct is None:
                acct = SourceAccount(
                    source=source.value,
                    external_id=ext,
                    shop_id=shop.id,
                    display_name=cfg.meta_account_ui_name if source == SourceKind.META else cfg.name,
                )
                session.add(acct)
            acct.shop_id = shop.id
            if source == SourceKind.META:
                acct.display_name = cfg.meta_account_ui_name
    session.flush()
    return shops


def account_for(session: Session, shop: Shop, source: SourceKind) -> SourceAccount | None:
    return session.execute(
        select(SourceAccount).where(
            SourceAccount.shop_id == shop.id,
            SourceAccount.source == source.value,
            SourceAccount.active.is_(True),
        )
    ).scalar_one_or_none()


def _record_envelope(
    session: Session, svc: Services, env: DataEnvelope, account: SourceAccount | None, stream: str
) -> Any:
    batch = store_batch(
        session,
        env,
        source_account_id=account.id if account else None,
        retention_days=svc.settings.raw_retention_days,
    )
    if account is not None:
        cp = get_checkpoint(session, account.id, stream)
        if env.usable:
            hw = env.source_updated_at or env.fetched_at_utc
            mark_success(
                cp,
                at=svc.now(),
                cursor=env.request_signature.get("next_cursor"),
                high_watermark=hw,
                records=len(env.records),
            )
        else:
            mark_failure(cp, at=svc.now(), error=f"{env.status}: {'; '.join(env.warnings)[:500]}")
    return batch


def sync_orders(
    session: Session,
    svc: Services,
    shop_key: str,
    *,
    date_from: date,
    date_to: date,
    status_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    shop = session.execute(select(Shop).where(Shop.shop_key == shop_key)).scalar_one()
    cfg: ShopConfig = svc.config.shops.by_key(shop_key)
    account = account_for(session, shop, SourceKind.BASELINKER)
    if account is None:
        return {"status": DataStatus.UNCONFIGURED, "reason": "no baselinker account for shop"}
    adapter = svc.adapters.baselinker
    if status_names is None:
        st = adapter.sync(SyncRequest(stream="statuses", account_id=account.external_id))
        status_names = {r["status_id"]: r.get("name", "") for r in st.records} if st.usable else {}
    env = adapter.sync(
        SyncRequest(stream="orders", account_id=account.external_id, date_from=date_from, date_to=date_to)
    )
    batch = _record_envelope(session, svc, env, account, "orders")
    result: dict[str, Any] = {
        "status": env.status.value,
        "records": len(env.records),
        "pagination_complete": env.pagination_complete,
        "warnings": env.warnings,
        "batch_id": str(batch.id),
    }
    if env.usable:
        result.update(
            loaders.upsert_orders(
                session,
                shop=shop,
                shop_cfg=cfg,
                account=account,
                records=env.records,
                observed_at=env.fetched_at_utc,
                status_names=status_names,
            )
        )
    ret = adapter.sync(
        SyncRequest(stream="returns", account_id=account.external_id, date_from=date_from, date_to=date_to)
    )
    _record_envelope(session, svc, ret, account, "returns")
    if ret.usable:
        result["refunds"] = loaders.upsert_refunds(
            session, account=account, records=ret.records, observed_at=ret.fetched_at_utc
        )
    else:
        result["returns_status"] = ret.status.value
    return result


def refresh_open_orders(
    session: Session, svc: Services, shop_key: str, *, older_than_days: int = 0, limit: int = 500
) -> dict[str, Any]:
    """Re-fetch OPEN (and recent) orders by ID to catch late cancellations/returns - date filters are not a change feed."""
    shop = session.execute(select(Shop).where(Shop.shop_key == shop_key)).scalar_one()
    cfg = svc.config.shops.by_key(shop_key)
    account = account_for(session, shop, SourceKind.BASELINKER)
    if account is None:
        return {"status": "UNCONFIGURED"}
    cutoff = svc.now() - timedelta(days=older_than_days)
    ids = [
        o.external_order_id
        for o in session.execute(
            select(Order)
            .where(
                Order.shop_id == shop.id,
                Order.status_class.in_(("OPEN", "DELIVERED")),
                Order.created_at_source <= cutoff,
            )
            .order_by(Order.created_at_source)
            .limit(limit)
        ).scalars()
    ]
    if not ids:
        return {"status": "OK", "records": 0}
    env = adapter_sync = svc.adapters.baselinker.sync(
        SyncRequest(stream="open_orders", account_id=account.external_id, params={"order_ids": ids})
    )
    _record_envelope(session, svc, env, account, "open_orders")
    out: dict[str, Any] = {
        "status": adapter_sync.status.value,
        "requested": len(ids),
        "records": len(env.records),
    }
    if env.usable:
        out.update(
            loaders.upsert_orders(
                session,
                shop=shop,
                shop_cfg=cfg,
                account=account,
                records=env.records,
                observed_at=env.fetched_at_utc,
            )
        )
    return out


def sync_meta_structure(session: Session, svc: Services, account_external_id: str) -> dict[str, Any]:
    account = session.execute(
        select(SourceAccount).where(
            SourceAccount.source == "meta", SourceAccount.external_id == account_external_id
        )
    ).scalar_one()
    info = svc.adapters.meta.sync(SyncRequest(stream="account", account_id=account_external_id))
    if info.usable and info.records:
        rec = info.records[0]
        account.currency, account.timezone = (
            rec.get("currency") or account.currency,
            rec.get("timezone") or account.timezone,
        )
    env = svc.adapters.meta.sync(SyncRequest(stream="structure", account_id=account_external_id))
    batch = _record_envelope(session, svc, env, account, "structure")
    out: dict[str, Any] = {"status": env.status.value, "records": len(env.records), "warnings": env.warnings}
    if env.usable:
        out.update(
            loaders.upsert_structure(
                session, account=account, records=env.records, observed_at=env.fetched_at_utc, batch=batch
            )
        )
    return out


def sync_meta_insights(
    session: Session,
    svc: Services,
    account_external_id: str,
    *,
    date_from: date,
    date_to: date,
    hourly: bool = False,
) -> dict[str, Any]:
    account = session.execute(
        select(SourceAccount).where(
            SourceAccount.source == "meta", SourceAccount.external_id == account_external_id
        )
    ).scalar_one()
    stream = "insights_hourly" if hourly else "insights_daily"
    env = svc.adapters.meta.sync(
        SyncRequest(stream=stream, account_id=account_external_id, date_from=date_from, date_to=date_to)
    )
    batch = _record_envelope(session, svc, env, account, stream)
    out: dict[str, Any] = {
        "status": env.status.value,
        "records": len(env.records),
        "pagination_complete": env.pagination_complete,
        "warnings": env.warnings,
    }
    if env.usable:
        out["rows"] = loaders.upsert_insights(
            session,
            account=account,
            records=env.records,
            as_of=env.fetched_at_utc,
            batch=batch,
            currency=account.currency or env.currency or "PLN",
        )
    return out


def sync_panel(
    session: Session, svc: Services, shop_key: str, *, date_from: date, date_to: date
) -> dict[str, Any]:
    shop = session.execute(select(Shop).where(Shop.shop_key == shop_key)).scalar_one()
    account = account_for(session, shop, SourceKind.NAILUKS)
    if account is None:
        return {"status": DataStatus.UNCONFIGURED.value}
    env = svc.adapters.nailuks.sync(
        SyncRequest(
            stream="panel_summary", account_id=account.external_id, date_from=date_from, date_to=date_to
        )
    )
    _record_envelope(session, svc, env, account, "panel_summary")
    out: dict[str, Any] = {"status": env.status.value, "records": len(env.records), "warnings": env.warnings}
    if env.usable:
        out["rows"] = loaders.upsert_panel_rows(
            session, shop_key=shop_key, records=env.records, as_of=env.fetched_at_utc
        )
    return out


def sync_market(session: Session, svc: Services, *, observed_on: date) -> dict[str, Any]:
    env = svc.adapters.gethooked.sync(SyncRequest(stream="market_ads", account_id="global"))
    batch = store_batch(session, env, source_account_id=None, retention_days=svc.settings.raw_retention_days)
    out: dict[str, Any] = {"status": env.status.value, "records": len(env.records), "warnings": env.warnings}
    if env.usable:
        basket_by_brand = {
            b.lower(): basket.basket for basket in svc.config.competitors.baskets for b in basket.brands
        }
        out.update(
            loaders.upsert_market_ads(
                session,
                records=env.records,
                observed_on=observed_on,
                batch=batch,
                basket_by_brand=basket_by_brand,
            )
        )
    return out


def check_store_health(session: Session, svc: Services, shop_key: str) -> DataEnvelope:
    env = svc.adapters.store_health.sync(SyncRequest(stream="health", account_id=shop_key))
    store_batch(session, env, source_account_id=None, retention_days=7)
    return env


def default_import_range(svc: Services, today: date) -> tuple[date, date]:
    return today - timedelta(days=svc.settings.first_import_days), today


def as_utc(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time(), tzinfo=__import__("datetime").UTC)
