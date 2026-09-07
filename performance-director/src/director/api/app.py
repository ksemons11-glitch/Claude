"""FastAPI application: JSON API (§19) + a minimal Jinja/HTMX panel. Read-mostly; every mutation is authenticated,
CSRF-protected for cookie sessions, audited and rate-limited. OBSERVE mode is visible in the header at all times."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from director import pipeline
from director.api.auth import SESSION_COOKIE, Auth
from director.config import Settings, get_settings
from director.db.models import (
    ActionRequest,
    Ad,
    AdSet,
    AuditEvent,
    Campaign,
    Creative,
    DailyMetric,
    DataQualityIssue,
    Decision,
    Experiment,
    JobRun,
    MarketSignal,
    NotificationOutbox,
    Offer,
    OfferVersion,
    PolicySnapshot,
    Recommendation,
    Report,
    Shop,
    SourceAccount,
    SyncCheckpoint,
)
from director.decisions import journal
from director.jobs import queue
from director.services import Services, build_services

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    svc = services or build_services(settings)
    auth = Auth(settings)
    app = FastAPI(
        title="AI E-commerce Performance Director",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.services = svc
    app.state.auth = auth

    def user(request: Request) -> dict:
        return auth.current_user(request)

    def ctx(request: Request, u: dict | None, **extra: Any) -> dict[str, Any]:
        last_sync = None
        with svc.session_factory() as s:
            last_sync = s.execute(select(func.max(SyncCheckpoint.last_success_at))).scalar()
            unread = s.execute(
                select(func.count())
                .select_from(NotificationOutbox)
                .where(NotificationOutbox.channel == "in_app", NotificationOutbox.read_at.is_(None))
            ).scalar()
        return {
            "request": request,
            "user": u,
            "mode": settings.mode.value,
            "execution_enabled": settings.execution_enabled,
            "kill_switch": settings.kill_switch,
            "last_sync": last_sync,
            "adapters_mode": svc.adapters.mode,
            "unread": unread,
            "csrf": (u or {}).get("csrf"),
            **extra,
        }

    # ------------------------------------------------------------------ health
    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        detail: dict[str, Any] = {"db": "ok", "connectors": {}}
        code = 200
        try:
            with svc.session_factory() as s:
                s.execute(select(func.count()).select_from(Shop)).scalar()
        except Exception as exc:  # noqa: BLE001
            detail["db"] = f"error: {exc}"[:200]
            code = 503
        for name in ("meta", "baselinker", "nailuks", "gethooked"):
            try:
                h = getattr(svc.adapters, name).healthcheck()
                detail["connectors"][name] = h.status.value
            except Exception as exc:  # noqa: BLE001
                detail["connectors"][name] = f"error: {exc}"[:120]
        detail["degraded"] = [k for k, v in detail["connectors"].items() if v != "OK"]
        return JSONResponse(detail, status_code=code)

    # ------------------------------------------------------------------ auth
    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return TEMPLATES.TemplateResponse(
            "login.html", ctx(request, None, error=None, login_enabled=bool(settings.app_admin_password))
        )

    @app.post("/login")
    def login(request: Request, username: str = Form(...), password: str = Form(...)):
        auth.rate_limit(f"login:{request.client.host if request.client else 'x'}", limit=5, window=60)
        if not auth.check_password(username, password):
            return TEMPLATES.TemplateResponse(
                "login.html",
                ctx(
                    request,
                    None,
                    error="Nieprawidłowe dane logowania",
                    login_enabled=bool(settings.app_admin_password),
                ),
                status_code=401,
            )
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(
            SESSION_COOKIE,
            auth.issue_session(username),
            httponly=True,
            samesite="lax",
            secure=settings.app_base_url.startswith("https"),
        )
        return resp

    @app.post("/logout")
    def logout():
        resp = RedirectResponse("/login", status_code=303)
        resp.delete_cookie(SESSION_COOKIE)
        return resp

    # ------------------------------------------------------------------ panel pages
    @app.get("/", response_class=HTMLResponse)
    def overview(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            rep = pipeline.latest_report(s, "daily")
            alerts = (
                s.execute(
                    select(__import__("director.db.models", fromlist=["Alert"]).Alert).where(
                        __import__("director.db.models", fromlist=["Alert"]).Alert.status == "ACTIVE"
                    )
                )
                .scalars()
                .all()
            )
            dq = s.execute(
                select(func.count())
                .select_from(DataQualityIssue)
                .where(DataQualityIssue.resolved_at.is_(None), DataQualityIssue.severity == "CRITICAL")
            ).scalar()
            body = rep.body if rep else None
        return TEMPLATES.TemplateResponse(
            "overview.html", ctx(request, u, report=rep, body=body, alerts=alerts, dq_critical=dq)
        )

    @app.get("/reports", response_class=HTMLResponse)
    def reports_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            rows = (
                s.execute(
                    select(Report).order_by(Report.period_start.desc(), Report.revision.desc()).limit(60)
                )
                .scalars()
                .all()
            )
        return TEMPLATES.TemplateResponse("reports.html", ctx(request, u, reports=rows))

    @app.get("/reports/{report_id}", response_class=HTMLResponse)
    def report_page(request: Request, report_id: uuid.UUID, u: dict = Depends(user)):
        with svc.session_factory() as s:
            rep = s.get(Report, report_id)
            if rep is None:
                raise HTTPException(404)
        return TEMPLATES.TemplateResponse("report.html", ctx(request, u, report=rep))

    @app.get("/stores", response_class=HTMLResponse)
    def stores_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            shops = s.execute(select(Shop).order_by(Shop.shop_key)).scalars().all()
            latest_day = s.execute(
                select(func.max(DailyMetric.business_date)).where(DailyMetric.scope == "shop")
            ).scalar()
            rows = []
            for sh in shops:
                metrics = _latest_metrics(s, "shop", sh.shop_key, latest_day) if latest_day else {}
                rows.append({"shop": sh, "metrics": metrics})
        return TEMPLATES.TemplateResponse("stores.html", ctx(request, u, rows=rows, day=latest_day))

    @app.get("/structure", response_class=HTMLResponse)
    def structure_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            latest_day = s.execute(
                select(func.max(DailyMetric.business_date)).where(DailyMetric.scope == "ad")
            ).scalar()
            tree: list[dict[str, Any]] = []
            for acct in s.execute(select(SourceAccount).where(SourceAccount.source == "meta")).scalars():
                camps = []
                for c in s.execute(
                    select(Campaign).where(Campaign.source_account_id == acct.id).order_by(Campaign.name)
                ).scalars():
                    adsets = []
                    for a in s.execute(
                        select(AdSet).where(AdSet.campaign_id == c.id).order_by(AdSet.name)
                    ).scalars():
                        ads = [
                            {
                                "ad": ad,
                                "metrics": _latest_metrics(s, "ad", ad.external_id, latest_day)
                                if latest_day
                                else {},
                            }
                            for ad in s.execute(
                                select(Ad).where(Ad.adset_id == a.id).order_by(Ad.name)
                            ).scalars()
                        ]
                        adsets.append({"adset": a, "ads": ads})
                    camps.append({"campaign": c, "adsets": adsets})
                tree.append({"account": acct, "campaigns": camps})
        return TEMPLATES.TemplateResponse("structure.html", ctx(request, u, tree=tree, day=latest_day))

    @app.get("/creatives", response_class=HTMLResponse)
    def creatives_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            rows = s.execute(
                select(Creative, Shop.shop_key)
                .join(Shop, Shop.id == Creative.shop_id)
                .order_by(Shop.shop_key, Creative.name)
            ).all()
        return TEMPLATES.TemplateResponse("creatives.html", ctx(request, u, rows=rows))

    @app.get("/decisions", response_class=HTMLResponse)
    def decisions_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            decisions = (
                s.execute(select(Decision).order_by(Decision.proposed_at.desc()).limit(100)).scalars().all()
            )
            experiments = (
                s.execute(select(Experiment).order_by(Experiment.created_at.desc()).limit(50)).scalars().all()
            )
            requests_ = (
                s.execute(select(ActionRequest).order_by(ActionRequest.created_at.desc()).limit(50))
                .scalars()
                .all()
            )
        return TEMPLATES.TemplateResponse(
            "decisions.html",
            ctx(request, u, decisions=decisions, experiments=experiments, action_requests=requests_),
        )

    @app.get("/market", response_class=HTMLResponse)
    def market_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            signals = (
                s.execute(
                    select(MarketSignal)
                    .order_by(MarketSignal.window_end.desc(), MarketSignal.trend_score.desc().nullslast())
                    .limit(50)
                )
                .scalars()
                .all()
            )
            concepts = {
                c.id: c
                for c in s.execute(
                    select(__import__("director.db.models", fromlist=["Concept"]).Concept)
                ).scalars()
            }
            health = svc.adapters.gethooked.healthcheck()
        return TEMPLATES.TemplateResponse(
            "market.html",
            ctx(
                request,
                u,
                signals=signals,
                concepts=concepts,
                source_status=health.status.value,
                source_detail=health.detail,
            ),
        )

    @app.get("/promotions", response_class=HTMLResponse)
    def promotions_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            offers = s.execute(select(Offer).order_by(Offer.created_at.desc())).scalars().all()
            versions = (
                s.execute(select(OfferVersion).order_by(OfferVersion.created_at.desc())).scalars().all()
            )
        return TEMPLATES.TemplateResponse(
            "promotions.html", ctx(request, u, offers=offers, versions=versions)
        )

    @app.get("/data-health", response_class=HTMLResponse)
    def data_health_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            issues = (
                s.execute(
                    select(DataQualityIssue)
                    .where(DataQualityIssue.resolved_at.is_(None))
                    .order_by(DataQualityIssue.severity.desc(), DataQualityIssue.detected_at.desc())
                    .limit(200)
                )
                .scalars()
                .all()
            )
            checkpoints = s.execute(
                select(SyncCheckpoint, SourceAccount)
                .join(SourceAccount, SourceAccount.id == SyncCheckpoint.source_account_id)
                .order_by(SourceAccount.source)
            ).all()
            jobs = s.execute(select(JobRun).order_by(JobRun.scheduled_for.desc()).limit(40)).scalars().all()
            stats = queue.queue_stats(s)
        return TEMPLATES.TemplateResponse(
            "data_health.html",
            ctx(
                request,
                u,
                issues=issues,
                checkpoints=checkpoints,
                jobs=jobs,
                stats=stats,
                now=datetime.now(UTC),
            ),
        )

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            snapshots = (
                s.execute(select(PolicySnapshot).order_by(PolicySnapshot.created_at.desc()).limit(20))
                .scalars()
                .all()
            )
        redacted = {
            k: ("***" if any(x in k for x in ("token", "key", "secret", "password", "url")) and v else v)
            for k, v in settings.model_dump().items()
        }
        return TEMPLATES.TemplateResponse(
            "settings.html",
            ctx(
                request,
                u,
                policies=svc.config.policies.model_dump(mode="json"),
                hashes=svc.config.hashes,
                snapshots=snapshots,
                env=redacted,
            ),
        )

    @app.get("/notifications", response_class=HTMLResponse)
    def notifications_page(request: Request, u: dict = Depends(user)):
        with svc.session_factory() as s:
            items = (
                s.execute(
                    select(NotificationOutbox).order_by(NotificationOutbox.created_at.desc()).limit(100)
                )
                .scalars()
                .all()
            )
            for it in items:
                if it.channel == "in_app" and it.read_at is None:
                    it.read_at = datetime.now(UTC)
            s.commit()
        return TEMPLATES.TemplateResponse("notifications.html", ctx(request, u, items=items))

    # ------------------------------------------------------------------ JSON API
    @app.get("/api/reports")
    def api_reports(u: dict = Depends(user), kind: str = "daily", limit: int = 30):
        with svc.session_factory() as s:
            rows = (
                s.execute(
                    select(Report)
                    .where(Report.kind == kind)
                    .order_by(Report.period_start.desc(), Report.revision.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                {
                    "id": str(r.id),
                    "kind": r.kind,
                    "period_start": r.period_start.isoformat(),
                    "revision": r.revision,
                    "status": r.status,
                    "completeness": r.completeness,
                    "as_of": r.as_of.isoformat(),
                }
                for r in rows
            ]

    @app.get("/api/reports/{report_id}")
    def api_report(report_id: uuid.UUID, u: dict = Depends(user)):
        with svc.session_factory() as s:
            r = s.get(Report, report_id)
            if r is None:
                raise HTTPException(404)
            return {
                "id": str(r.id),
                "kind": r.kind,
                "period_start": r.period_start.isoformat(),
                "revision": r.revision,
                "status": r.status,
                "completeness": r.completeness,
                "body": r.body,
                "markdown": r.rendered_markdown,
            }

    @app.get("/api/shops/{shop_key}/metrics")
    def api_shop_metrics(shop_key: str, u: dict = Depends(user), day: date | None = None):
        with svc.session_factory() as s:
            latest_day = (
                day
                or s.execute(
                    select(func.max(DailyMetric.business_date)).where(
                        DailyMetric.scope == "shop", DailyMetric.entity_key == shop_key
                    )
                ).scalar()
            )
            if latest_day is None:
                raise HTTPException(404, "no metrics")
            return {
                "shop_key": shop_key,
                "business_date": latest_day.isoformat(),
                "metrics": _latest_metrics(s, "shop", shop_key, latest_day),
            }

    @app.get("/api/structure")
    def api_structure(u: dict = Depends(user)):
        with svc.session_factory() as s:
            return [
                {
                    "campaign": c.external_id,
                    "name": c.name,
                    "status": c.effective_status,
                    "daily_budget": str(c.daily_budget) if c.daily_budget else None,
                    "budget_type": c.budget_type,
                    "adsets": [
                        {
                            "adset": a.external_id,
                            "name": a.name,
                            "daily_budget": str(a.daily_budget) if a.daily_budget else None,
                            "ads": [
                                {
                                    "ad": ad.external_id,
                                    "name": ad.name,
                                    "status": ad.effective_status,
                                    "post_id": ad.post_id,
                                }
                                for ad in s.execute(select(Ad).where(Ad.adset_id == a.id)).scalars()
                            ],
                        }
                        for a in s.execute(select(AdSet).where(AdSet.campaign_id == c.id)).scalars()
                    ],
                }
                for c in s.execute(select(Campaign)).scalars()
            ]

    @app.get("/api/creatives")
    def api_creatives(u: dict = Depends(user)):
        with svc.session_factory() as s:
            return [
                {
                    "creative_key": c.creative_key,
                    "name": c.name,
                    "status": c.status,
                    "post_id": c.post_id,
                    "concept_id": str(c.concept_id) if c.concept_id else None,
                }
                for c in s.execute(select(Creative)).scalars()
            ]

    @app.get("/api/decisions")
    def api_decisions(u: dict = Depends(user), status: str | None = None):
        with svc.session_factory() as s:
            q = select(Decision).order_by(Decision.proposed_at.desc()).limit(200)
            if status:
                q = q.where(Decision.status == status)
            return [
                {
                    "id": str(d.id),
                    "status": d.status,
                    "entity_ref": d.entity_ref,
                    "action_type": d.action_type,
                    "reason": d.reason,
                    "proposed_at": d.proposed_at.isoformat(),
                    "outcome": d.outcome,
                }
                for d in s.execute(q).scalars()
            ]

    @app.get("/api/data-quality")
    def api_dq(u: dict = Depends(user)):
        with svc.session_factory() as s:
            return [
                {
                    "scope": i.scope,
                    "check": i.check_name,
                    "severity": i.severity,
                    "message": i.message,
                    "business_date": i.business_date.isoformat() if i.business_date else None,
                }
                for i in s.execute(
                    select(DataQualityIssue).where(DataQualityIssue.resolved_at.is_(None))
                ).scalars()
            ]

    @app.post("/api/jobs/run")
    def api_run_job(request: Request, payload: dict[str, Any], u: dict = Depends(user)):
        auth.require_csrf(request, u, request.headers.get("x-csrf-token"))
        auth.rate_limit(f"jobs:{u['u']}", limit=10, window=60)
        job = payload.get("job")
        from director.jobs.workflows import HANDLERS

        if job not in HANDLERS:
            raise HTTPException(400, f"unknown job {job}")
        with svc.session_factory() as s:
            jid = queue.enqueue(
                s,
                job,
                datetime.now(UTC),
                scope=str(payload.get("scope", "global")),
                params=dict(payload.get("params", {})),
                max_attempts=1,
            )
            s.add(
                AuditEvent(
                    actor=u["u"],
                    operation="job.enqueue",
                    object_type="job_run",
                    object_id=str(jid),
                    occurred_at=datetime.now(UTC),
                    correlation_id=uuid.uuid4().hex,
                    details={"job": job},
                )
            )
            s.commit()
        return {"job_run_id": str(jid), "status": "PENDING" if jid else "DUPLICATE"}

    @app.post("/api/recommendations/{rec_id}/accept")
    def api_accept(request: Request, rec_id: uuid.UUID, u: dict = Depends(user)):
        auth.require_csrf(request, u, request.headers.get("x-csrf-token"))
        with svc.session_factory() as s:
            rec = s.get(Recommendation, rec_id)
            if rec is None:
                raise HTTPException(404)
            d = s.execute(select(Decision).where(Decision.recommendation_id == rec.id)).scalar_one_or_none()
            if d is None:
                d = journal.propose(s, rec, now=datetime.now(UTC), data_as_of=datetime.now(UTC))
            journal.approve(s, d, actor=u["u"], now=datetime.now(UTC), correlation_id=uuid.uuid4().hex)
            rec.status = "ACCEPTED"
            s.commit()
            return {
                "decision_id": str(d.id),
                "status": d.status,
                "note": "OBSERVE mode: no external change is made; execution requires a separately approved action request",
            }

    @app.post("/api/action-requests/{ar_id}/approve")
    def api_approve_ar(request: Request, ar_id: uuid.UUID, u: dict = Depends(user)):
        auth.require_csrf(request, u, request.headers.get("x-csrf-token"))
        from director.execution.executor import approve as approve_ar

        with svc.session_factory() as s:
            ar = s.get(ActionRequest, ar_id)
            if ar is None:
                raise HTTPException(404)
            try:
                approve_ar(
                    s,
                    ar,
                    actor=u["u"],
                    now=datetime.now(UTC),
                    ttl_minutes=svc.config.policies.execution.approval_ttl_minutes,
                    correlation_id=uuid.uuid4().hex,
                )
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            s.commit()
            return {
                "id": str(ar.id),
                "status": ar.status,
                "approval_expires_at": ar.approval_expires_at.isoformat(),
                "execution_enabled": settings.execution_enabled,
                "mode": settings.mode.value,
            }

    @app.post("/api/settings/policies")
    def api_policies(request: Request, payload: dict[str, Any], u: dict = Depends(user)):
        """Policies are versioned YAML; the API only records a proposed change for the owner to apply and commit."""
        auth.require_csrf(request, u, request.headers.get("x-csrf-token"))
        from director.config import PoliciesConfig

        try:
            PoliciesConfig.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, str(exc)[:500]) from exc
        with svc.session_factory() as s:
            s.add(
                AuditEvent(
                    actor=u["u"],
                    operation="policies.proposed",
                    object_type="policies",
                    object_id="proposal",
                    occurred_at=datetime.now(UTC),
                    correlation_id=uuid.uuid4().hex,
                    details=payload,
                )
            )
            s.commit()
        return {
            "status": "recorded",
            "note": "apply by editing config/policies.yaml and restarting; snapshot is taken at next run",
        }

    return app


def _latest_metrics(s, scope: str, key: str, day: date) -> dict[str, Any]:
    rows = s.execute(
        select(DailyMetric)
        .where(DailyMetric.scope == scope, DailyMetric.entity_key == key, DailyMetric.business_date == day)
        .order_by(DailyMetric.as_of)
    ).scalars()
    out: dict[str, Any] = {}
    for r in rows:
        out[r.metric] = {
            "value": str(r.value.quantize(__import__("decimal").Decimal("0.01")))
            if r.value is not None
            else None,
            "reason": r.reason,
            "evidence_id": r.evidence_id,
        }
    return out
