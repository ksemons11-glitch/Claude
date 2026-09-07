"""End-to-end workflows: daily run (sync -> reconcile -> metrics -> diagnostics -> reasoning -> report), weekly,
intraday detection, decision review. All functions are idempotent and safe to re-run (new report revision)."""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.contracts.common import DataStatus
from director.contracts.envelope import SourceKind
from director.creatives.identity import concentration, creative_map, sync_creatives
from director.creatives.market import compute_signals, creative_gap, persist_signals
from director.creatives.plan import build_briefs
from director.db.models import PolicySnapshot, Report, Shop, SourceAccount, SyncCheckpoint
from director.decisions import journal
from director.diagnostics.anomalies import intraday_reading, recover_alert, upsert_alert
from director.diagnostics.engine import WINDOW_METRICS, diagnose
from director.ingestion import sync as syncmod
from director.ingestion.reconciliation import reconcile_shop_day
from director.metrics.aggregates import compute_shop_day, compute_windows, latest_metric_rows
from director.metrics.calendar import business_date_of, week_bounds
from director.metrics.costs import import_costs_yaml
from director.notifications import outbox
from director.reasoning.anthropic_provider import build_provider
from director.reasoning.run import run_reasoning
from director.reports import daily as daily_report
from director.reports.weekly import build_weekly
from director.services import Services

log = logging.getLogger("director.pipeline")
WINDOW_SHOP_METRICS = WINDOW_METRICS + ("expected_result_after_ads", "roas_attributed_ordered")


def snapshot_policies(session: Session, svc: Services) -> None:
    for name, h in svc.config.hashes.items():
        if (
            session.execute(
                select(PolicySnapshot).where(PolicySnapshot.name == name, PolicySnapshot.config_hash == h)
            ).scalar_one_or_none()
            is None
        ):
            payload = getattr(svc.config, name).model_dump(mode="json")
            session.add(
                PolicySnapshot(
                    name=name, config_hash=h, payload=payload, version=str(payload.get("version", "1"))
                )
            )


def bootstrap(session: Session, svc: Services) -> dict[str, Shop]:
    shops = syncmod.ensure_reference_data(session, svc)
    snapshot_policies(session, svc)
    costs = svc.settings.config_dir / "costs.yaml"
    if not costs.exists():
        costs = svc.settings.config_dir / "costs.example.yaml"
    if costs.exists():
        import_costs_yaml(session, costs)
    return shops


def sync_all(
    session: Session, svc: Services, *, day: date, lookback_days: int, first_import: bool = False
) -> dict[str, Any]:
    """Pull every source for every shop. Returns per-shop status + list of missing/unusable sources."""
    out: dict[str, Any] = {"shops": {}, "missing": []}
    if (
        not first_import
        and session.execute(
            select(SyncCheckpoint).where(
                SyncCheckpoint.stream == "orders", SyncCheckpoint.last_success_at.isnot(None)
            )
        ).first()
        is None
    ):
        first_import = True  # fresh install: pull the configured import horizon
    start = day - timedelta(days=(svc.settings.first_import_days if first_import else lookback_days))
    out["range"] = [start.isoformat(), day.isoformat()]
    for cfg in svc.config.shops.shops:
        if not cfg.active:
            continue
        s: dict[str, Any] = {}
        if cfg.meta_account_id:
            if svc.adapters.mode == "fixture":
                acct = session.execute(
                    select(SourceAccount).where(
                        SourceAccount.source == "meta", SourceAccount.external_id == cfg.meta_account_id
                    )
                ).scalar_one()
                has_snapshot = session.execute(
                    select(SyncCheckpoint).where(
                        SyncCheckpoint.source_account_id == acct.id, SyncCheckpoint.stream == "structure"
                    )
                ).scalar_one_or_none()
                if (
                    has_snapshot is None
                ):  # replay the previous snapshot first so structure_changes have a diff
                    from director.adapters.base import SyncRequest

                    prev = svc.adapters.meta.sync(
                        SyncRequest(
                            stream="structure", account_id=cfg.meta_account_id, params={"variant": "prev"}
                        )
                    )
                    if prev.usable:
                        from director.ingestion import loaders

                        loaders.upsert_structure(
                            session,
                            account=acct,
                            records=prev.records,
                            observed_at=(prev.source_updated_at or svc.now() - timedelta(days=1)),
                        )
            s["structure"] = syncmod.sync_meta_structure(session, svc, cfg.meta_account_id)
            s["insights"] = syncmod.sync_meta_insights(
                session, svc, cfg.meta_account_id, date_from=start, date_to=day
            )
            for k in ("structure", "insights"):
                if s[k]["status"] not in (DataStatus.OK.value, DataStatus.PARTIAL.value):
                    out["missing"].append(f"{cfg.shop_key}:meta:{k}:{s[k]['status']}")
        else:
            out["missing"].append(f"{cfg.shop_key}:meta:UNCONFIGURED")
        if cfg.baselinker_shop_id:
            s["orders"] = syncmod.sync_orders(session, svc, cfg.shop_key, date_from=start, date_to=day)
            if s["orders"]["status"] not in (DataStatus.OK.value, DataStatus.PARTIAL.value):
                out["missing"].append(f"{cfg.shop_key}:baselinker:orders:{s['orders']['status']}")
        else:
            out["missing"].append(f"{cfg.shop_key}:baselinker:UNCONFIGURED")
        s["panel"] = syncmod.sync_panel(session, svc, cfg.shop_key, date_from=start, date_to=day)
        if s["panel"]["status"] not in (DataStatus.OK.value, DataStatus.PARTIAL.value):
            out["missing"].append(f"{cfg.shop_key}:nailuks:{s['panel']['status']}")
        out["shops"][cfg.shop_key] = s
        session.flush()
    return out


def compute_metrics_range(
    session: Session,
    svc: Services,
    *,
    shops: list[Shop],
    start: date,
    end: date,
    as_of: datetime,
    only_missing: bool = True,
) -> int:
    n = 0
    target_cpa = {
        p.shop_key: p.target_cpa_pln for p in svc.config.policies.products if p.product_key == p.shop_key
    }
    for shop in shops:
        existing = (
            latest_metric_rows(
                session, scope="shop", key=shop.shop_key, metric="orders", start=start, end=end, as_of=as_of
            )
            if only_missing
            else {}
        )
        d = start
        while d <= end:
            if d not in existing:
                compute_shop_day(session, shop=shop, day=d, as_of=as_of, target_cpa=target_cpa)
                n += 1
            d += timedelta(days=1)
        session.flush()
    return n


def run_daily(
    svc: Services, day: date, *, first_import: bool = False, correlation_id: str | None = None
) -> uuid.UUID:
    """Produce the D-1 report for `day`. Returns the report id."""
    as_of = svc.now()
    correlation_id = correlation_id or uuid.uuid4().hex
    with svc.session_factory() as session:
        shops_map = bootstrap(session, svc)
        shops = [s for s in shops_map.values() if s.active]
        sync = sync_all(
            session, svc, day=day, lookback_days=svc.settings.lookback_days, first_import=first_import
        )
        session.commit()
        missing = list(sync["missing"])
        # reconciliation for the report day and the trailing 7 days
        for shop in shops:
            meta = syncmod.account_for(session, shop, SourceKind.META)
            base = syncmod.account_for(session, shop, SourceKind.BASELINKER)
            for i in range(0, 8):
                reconcile_shop_day(
                    session,
                    shop=shop,
                    meta_account=meta,
                    base_account=base,
                    day=day - timedelta(days=i),
                    now=as_of,
                    freshness_minutes=svc.config.policies.thresholds.source_freshness_minutes,
                )
        session.commit()
        # metrics: ensure history exists (up to 45 days back) then recompute the report day and the trailing 7 days
        compute_metrics_range(
            session,
            svc,
            shops=shops,
            start=day - timedelta(days=44),
            end=day - timedelta(days=8),
            as_of=as_of,
            only_missing=True,
        )
        compute_metrics_range(
            session, svc, shops=shops, start=day - timedelta(days=7), end=day, as_of=as_of, only_missing=False
        )
        for shop in shops:
            compute_windows(
                session, scope="shop", key=shop.shop_key, day=day, as_of=as_of, metrics=WINDOW_SHOP_METRICS
            )
            meta = syncmod.account_for(session, shop, SourceKind.META)
            if meta is not None:
                sync_creatives(session, shop=shop, account=meta, now=as_of)
        session.commit()
        # diagnostics
        contexts, rules = {}, {}
        for shop in shops:
            ctx, res = diagnose(session, shop=shop, day=day, as_of=as_of, policies=svc.config.policies)
            contexts[shop.shop_key], rules[shop.shop_key] = ctx, res
        all_rules = [r for rs in rules.values() for r in rs]
        bundle = daily_report.build_bundle(
            day,
            as_of,
            list(contexts.values()),
            all_rules,
            definitions_version="1",
            max_items=svc.settings.llm_max_evidence_items,
        )
        provider = build_provider(svc.settings)
        outcome = run_reasoning(
            session, provider, bundle, daily_budget_pln=Decimal(svc.settings.llm_daily_budget_pln), now=as_of
        )
        completeness = "COMPLETE" if not missing else "PARTIAL"
        body, recs = daily_report.assemble(
            session,
            settings=svc.settings,
            policies=svc.config.policies,
            day=day,
            as_of=as_of,
            shops=shops,
            contexts=contexts,
            rules=rules,
            completeness=completeness,
            missing=missing,
            llm=outcome.response,
            llm_meta=outcome.meta(),
        )
        report = daily_report.persist(
            session, body, bundle, recs, max_actions=svc.config.policies.thresholds.max_actions_per_report
        )
        report.cost_pln = outcome.cost_pln
        for rec in recs:
            journal.propose(
                session,
                rec,
                now=as_of,
                data_as_of=as_of,
                policy_version=svc.config.hashes.get("policies", "1")[:12],
            )
        outbox.enqueue(
            session,
            dedupe_key=f"report:daily:{day.isoformat()}:r{report.revision}",
            kind="report",
            subject=f"Raport dzienny {day} [{body.status.value}/{completeness}]",
            body=report.rendered_markdown or "",
            channel=svc.settings.notification_channel,
            report_id=report.id,
        )
        outbox.deliver_pending(session, {"in_app": outbox.InAppChannel()}, now=as_of)
        session.commit()
        log.info(
            "daily report %s revision %s status %s (%s)", day, report.revision, body.status, completeness
        )
        return report.id


def run_weekly(svc: Services, week_end: date) -> uuid.UUID:
    as_of = svc.now()
    start, end = week_bounds(week_end)
    with svc.session_factory() as session:
        shops = [s for s in bootstrap(session, svc).values() if s.active]
        signals = compute_signals(session, window_end=end)
        persist_signals(session, signals, window_end=end)
        conc_items: list[str] = []
        top_conc: dict[str, Any] = {"concentration": "n/a", "lines": conc_items}
        plan: list[dict[str, Any]] = []
        for shop in shops:
            meta = syncmod.account_for(session, shop, SourceKind.META)
            if meta is None:
                continue
            cmap = creative_map(session, meta)
            values: dict[str, Decimal] = {}
            for ad_ext in cmap:
                rows = latest_metric_rows(
                    session,
                    scope="ad",
                    key=ad_ext,
                    metric="attributed_revenue",
                    start=start,
                    end=end,
                    as_of=as_of,
                )
                values[ad_ext] = sum((r.value or Decimal(0) for r in rows.values()), start=Decimal(0))
            conc = concentration(values, cmap)
            if conc.get("top_share") is not None:
                conc_items.append(
                    f"{shop.shop_key}: top kreacja {conc['top_share']:.0%} przypisanego przychodu ({conc['creatives']} kreacji)"
                )
            gaps = creative_gap(session, shop.id, signals)
            pp = svc.config.policies.product(shop.shop_key, shop.shop_key)
            plan.extend(
                build_briefs(
                    shop_key=shop.shop_key,
                    gaps=gaps,
                    concentration=conc,
                    capacity_per_week=2,
                    test_budget_pln=(pp.test_loss_cap_pln if pp else None),
                    target_cpa=(pp.target_cpa_pln if pp else None),
                )
            )
        top_conc["concentration"] = "; ".join(conc_items) or "brak przypisanego przychodu"
        missing = [] if signals else ["market scan: brak obserwacji (Get Hooked niedostępny / brak importu)"]
        _, report = build_weekly(
            session,
            shops=shops,
            start=start,
            end=end,
            as_of=as_of,
            concentration=top_conc,
            plan=[{"title": f"{b['shop_key']} · {b['concept_id']}", "detail": b["hypothesis"]} for b in plan],
            missing=missing,
            completeness="COMPLETE" if not missing else "PARTIAL",
        )
        report.body = {**report.body, "briefs": plan, "signals": signals}
        outbox.enqueue(
            session,
            dedupe_key=f"report:weekly:{start.isoformat()}:r{report.revision}",
            kind="report",
            subject=f"Raport tygodniowy {start}..{end}",
            body=report.rendered_markdown or "",
            report_id=report.id,
        )
        outbox.deliver_pending(session, {"in_app": outbox.InAppChannel()}, now=as_of)
        session.commit()
        return report.id


def run_intraday(svc: Services) -> list[dict[str, Any]]:
    now = svc.now()
    results: list[dict[str, Any]] = []
    with svc.session_factory() as session:
        shops = [s for s in bootstrap(session, svc).values() if s.active]
        for shop in shops:
            base = syncmod.account_for(session, shop, SourceKind.BASELINKER)
            lag = None
            if base is not None:
                cp = session.execute(
                    select(SyncCheckpoint).where(
                        SyncCheckpoint.source_account_id == base.id, SyncCheckpoint.stream == "orders"
                    )
                ).scalar_one_or_none()
                if cp and cp.last_success_at:
                    lag = (now - cp.last_success_at).total_seconds() / 60
            reading = intraday_reading(
                session,
                shop=shop,
                now=now,
                tz_name=shop.timezone,
                policy=svc.config.policies.intraday,
                source_lag_minutes=lag,
            )
            episode = f"{reading.day.isoformat()}"
            notified = False
            if reading.verdict == "LOW":
                _, notified = upsert_alert(
                    session,
                    scope=f"shop:{shop.shop_key}",
                    rule_id="INTRADAY_ORDERS_LOW",
                    episode_key=episode,
                    severity="WATCH",
                    message=f"{shop.shop_key}: {reading.cumulative_orders} zamówień do {reading.local_hour}:00 vs porównywalne dni {reading.comparable}",
                    evidence=reading.__dict__ | {"day": reading.day.isoformat()},
                    now=now,
                    policy=svc.config.policies.intraday,
                )
            else:
                recover_alert(
                    session,
                    scope=f"shop:{shop.shop_key}",
                    rule_id="INTRADAY_ORDERS_LOW",
                    episode_key=episode,
                    now=now,
                )
            health = syncmod.check_store_health(session, svc, shop.shop_key)
            failed = [r for r in health.records if not r.get("ok")]
            if health.usable and failed:
                _, hn = upsert_alert(
                    session,
                    scope=f"shop:{shop.shop_key}",
                    rule_id="STORE_UNAVAILABLE",
                    episode_key=reading.day.isoformat(),
                    severity="CRITICAL",
                    message=f"{shop.shop_key}: {len(failed)} URL niedostępnych (bez sygnału operatora płatności nie stwierdzamy awarii płatności)",
                    evidence={"failed": failed},
                    now=now,
                    policy=svc.config.policies.intraday,
                    immediate=True,
                )
                notified = notified or hn
            elif health.usable:
                recover_alert(
                    session,
                    scope=f"shop:{shop.shop_key}",
                    rule_id="STORE_UNAVAILABLE",
                    episode_key=reading.day.isoformat(),
                    now=now,
                )
            results.append(
                {
                    "shop": shop.shop_key,
                    "verdict": reading.verdict,
                    "cumulative": reading.cumulative_orders,
                    "comparable": reading.comparable,
                    "notified": notified,
                }
            )
        for a in [
            x
            for x in session.execute(
                select(__import__("director.db.models", fromlist=["Alert"]).Alert)
            ).scalars()
            if x.status == "ACTIVE" and x.last_notified_at == now
        ]:
            outbox.enqueue(
                session,
                dedupe_key=f"alert:{a.dedupe_key}:{now.isoformat()}",
                kind="alert",
                subject=f"[{a.severity}] {a.rule_id} {a.scope}",
                body=a.message,
                alert_id=a.id,
            )
        outbox.deliver_pending(session, {"in_app": outbox.InAppChannel()}, now=now)
        session.commit()
    return results


def review_decisions(svc: Services) -> dict[str, int]:
    now = svc.now()
    with svc.session_factory() as session:
        expired = journal.expire_stale(session, now=now)
        n = 0
        for d, h in journal.due_evaluations(session, now=now):
            shop_key = d.entity_ref.split(":", 1)[1] if d.entity_ref.startswith("shop:") else None
            if shop_key is None:
                shop_key = svc.config.shops.shops[0].shop_key
            journal.evaluate(session, d, horizon_hours=h, now=now, shop_key=shop_key, tz_name=svc.tz)
            n += 1
        session.commit()
        return {"expired": expired, "evaluated": n}


def latest_report(session: Session, kind: str = "daily", day: date | None = None) -> Report | None:
    q = select(Report).where(Report.kind == kind)
    if day is not None:
        q = q.where(Report.period_start == day)
    return session.execute(
        q.order_by(Report.period_start.desc(), Report.revision.desc()).limit(1)
    ).scalar_one_or_none()


def yesterday(svc: Services) -> date:
    return business_date_of(svc.now(), svc.tz) - timedelta(days=1)
