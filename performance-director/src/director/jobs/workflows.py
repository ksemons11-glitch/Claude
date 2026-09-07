"""Job name -> handler registry used by the worker."""

from __future__ import annotations

import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select

from director import pipeline
from director.contracts.envelope import SourceKind
from director.db.models import Shop
from director.ingestion import sync as syncmod
from director.jobs.worker import JobContext, PermanentError
from director.metrics.calendar import business_date_of


def _svc(ctx: JobContext):
    return ctx.services


def h_sync_orders(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    day = business_date_of(svc.now(), svc.tz)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        shops = (
            [c.shop_key for c in svc.config.shops.shops if c.active]
            if ctx.job.scope == "global"
            else [ctx.job.scope]
        )
        out = {
            k: syncmod.sync_orders(
                s, svc, k, date_from=day - timedelta(days=svc.settings.lookback_days), date_to=day
            )
            for k in shops
        }
        for k in shops:
            out[f"{k}:refresh_open"] = syncmod.refresh_open_orders(s, svc, k, older_than_days=1)
        s.commit()
    return {"records": sum(v.get("records", 0) for v in out.values() if isinstance(v, dict)), "detail": out}


def h_sync_meta_intraday(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    day = business_date_of(svc.now(), svc.tz)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        accounts = (
            [c.meta_account_id for c in svc.config.shops.shops if c.meta_account_id]
            if ctx.job.scope == "global"
            else [ctx.job.scope]
        )
        out = {
            a: syncmod.sync_meta_insights(s, svc, a, date_from=day - timedelta(days=2), date_to=day)
            for a in accounts
        }
        s.commit()
    return {"records": sum(v.get("records", 0) for v in out.values()), "detail": out}


def h_sync_structure(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        accounts = (
            [c.meta_account_id for c in svc.config.shops.shops if c.meta_account_id]
            if ctx.job.scope == "global"
            else [ctx.job.scope]
        )
        out = {a: syncmod.sync_meta_structure(s, svc, a) for a in accounts}
        s.commit()
    return {"records": sum(v.get("records", 0) for v in out.values()), "detail": out}


def h_check_store_health(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        shops = (
            [c.shop_key for c in svc.config.shops.shops if c.active]
            if ctx.job.scope == "global"
            else [ctx.job.scope]
        )
        out = {k: [r for r in syncmod.check_store_health(s, svc, k).records] for k in shops}
        s.commit()
    return {"records": sum(len(v) for v in out.values()), "detail": out}


def h_detect_intraday(ctx: JobContext) -> dict[str, Any]:
    return {"records": 0, "detail": pipeline.run_intraday(_svc(ctx))}


def h_reconcile_daily(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    day = pipeline.yesterday(svc)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        pipeline.sync_all(s, svc, day=day, lookback_days=7)
        for shop in s.execute(select(Shop).where(Shop.active.is_(True))).scalars():
            for i in range(8):
                syncmod.reconcile_shop_day  # noqa: B018 - keep import referenced
                from director.ingestion.reconciliation import reconcile_shop_day

                reconcile_shop_day(
                    s,
                    shop=shop,
                    meta_account=syncmod.account_for(s, shop, SourceKind.META),
                    base_account=syncmod.account_for(s, shop, SourceKind.BASELINKER),
                    day=day - timedelta(days=i),
                    now=svc.now(),
                    freshness_minutes=svc.config.policies.thresholds.source_freshness_minutes,
                )
        s.commit()
    return {"records": 0, "day": day.isoformat()}


def h_report_daily(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    day = (
        date.fromisoformat(ctx.job.params["date"]) if ctx.job.params.get("date") else pipeline.yesterday(svc)
    )
    rid = pipeline.run_daily(svc, day, correlation_id=ctx.correlation_id)
    return {"records": 1, "report_id": str(rid), "day": day.isoformat()}


def h_retry_daily(ctx: JobContext) -> dict[str, Any]:
    """Re-run only if the morning report was PARTIAL; a new revision is written only if conclusions could change."""
    svc = _svc(ctx)
    day = pipeline.yesterday(svc)
    with svc.session_factory() as s:
        rep = pipeline.latest_report(s, "daily", day)
        if rep is not None and rep.completeness == "COMPLETE":
            return {"records": 0, "skipped": "report already COMPLETE"}
    rid = pipeline.run_daily(svc, day, correlation_id=ctx.correlation_id)
    return {"records": 1, "report_id": str(rid)}


def h_review_decisions(ctx: JobContext) -> dict[str, Any]:
    return {"records": 0, **pipeline.review_decisions(_svc(ctx))}


def h_market_scan(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        out = syncmod.sync_market(s, svc, observed_on=business_date_of(svc.now(), svc.tz))
        s.commit()
    return {"records": out.get("records", 0), "detail": out}


def h_weekly_report(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    rid = pipeline.run_weekly(svc, pipeline.yesterday(svc))
    return {"records": 1, "report_id": str(rid)}


def h_weekly_creative_plan(ctx: JobContext) -> dict[str, Any]:
    return h_weekly_report(ctx)


def h_backfill_recent(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    day = pipeline.yesterday(svc)
    with svc.session_factory() as s:
        shops = [x for x in pipeline.bootstrap(s, svc).values() if x.active]
        pipeline.sync_all(s, svc, day=day, lookback_days=28)
        n = pipeline.compute_metrics_range(
            s, svc, shops=shops, start=day - timedelta(days=28), end=day, as_of=svc.now(), only_missing=False
        )
        s.commit()
    return {"records": n}


def h_audit_old_orders(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    with svc.session_factory() as s:
        pipeline.bootstrap(s, svc)
        out = {
            c.shop_key: syncmod.refresh_open_orders(s, svc, c.shop_key, older_than_days=28, limit=1000)
            for c in svc.config.shops.shops
            if c.active
        }
        s.commit()
    return {"records": sum(v.get("records", 0) for v in out.values()), "detail": out}


def h_backup(ctx: JobContext) -> dict[str, Any]:
    svc = _svc(ctx)
    pg_dump = shutil.which("pg_dump")
    if not pg_dump:
        raise PermanentError(
            "pg_dump not available in this container - configure backups on the host (see docs/RUNBOOK.md)"
        )
    out_dir = Path(svc.settings.config_dir).parent / "var" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"director-{svc.now().strftime('%Y%m%dT%H%M%S')}.dump"
    url = svc.settings.database_url.replace("+psycopg", "")
    proc = subprocess.run(
        [pg_dump, "--format=custom", "--file", str(target), url], capture_output=True, text=True, timeout=1800
    )
    if proc.returncode != 0:
        raise PermanentError(f"pg_dump failed: {proc.stderr[:500]}")
    return {
        "records": 1,
        "file": str(target),
        "bytes": target.stat().st_size,
        "note": "encrypt at rest on the host; test restore in a separate database",
    }


HANDLERS = {
    "sync_orders": h_sync_orders,
    "sync_meta_intraday": h_sync_meta_intraday,
    "sync_structure": h_sync_structure,
    "check_store_health": h_check_store_health,
    "detect_intraday": h_detect_intraday,
    "reconcile_daily": h_reconcile_daily,
    "report_daily": h_report_daily,
    "retry_daily": h_retry_daily,
    "review_decisions": h_review_decisions,
    "market_scan": h_market_scan,
    "weekly_report": h_weekly_report,
    "weekly_creative_plan": h_weekly_creative_plan,
    "backfill_recent": h_backfill_recent,
    "audit_old_orders": h_audit_old_orders,
    "backup": h_backup,
}
