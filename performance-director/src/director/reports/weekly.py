from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.contracts.common import present
from director.db.models import Decision, Experiment, Report, Shop
from director.metrics.aggregates import window_ratio
from director.reports.render import markdown_to_html, render_markdown
from director.reports.schemas import WeeklyReportBody


def _sum(
    session: Session, shop_key: str, metric: str, start: date, end: date, as_of: datetime
) -> Decimal | None:
    mv = window_ratio(session, scope="shop", key=shop_key, metric=metric, start=start, end=end, as_of=as_of)
    if mv.value is None:
        return None
    if mv.denominator is not None and metric in (
        "expected_result_after_ads",
        "revenue_ordered",
        "spend",
        "orders",
    ):
        return mv.numerator
    return mv.value


def build_weekly(
    session: Session,
    *,
    shops: list[Shop],
    start: date,
    end: date,
    as_of: datetime,
    concentration: dict[str, Any],
    plan: list[dict[str, Any]],
    missing: list[str],
    completeness: str,
) -> tuple[WeeklyReportBody, Report]:
    rows: list[dict[str, Any]] = []
    prev_start, prev_end = start - timedelta(days=7), end - timedelta(days=7)
    for s in shops:
        cur = {
            m: _sum(session, s.shop_key, m, start, end, as_of)
            for m in ("orders", "revenue_ordered", "spend", "expected_result_after_ads")
        }
        prev = _sum(session, s.shop_key, "expected_result_after_ads", prev_start, prev_end, as_of)
        delta = None
        if cur["expected_result_after_ads"] is not None and prev not in (None, Decimal(0)):
            delta = f"{(cur['expected_result_after_ads'] - prev) / abs(prev) * 100:+.0f}%"
        age = (as_of.date() - end).days
        rows.append(
            {
                "shop_key": s.shop_key,
                "name": s.name,
                "orders": str(int(cur["orders"])) if cur["orders"] is not None else "n/a",
                "revenue": str(present(cur["revenue_ordered"]))
                if cur["revenue_ordered"] is not None
                else "n/a",
                "spend": str(present(cur["spend"])) if cur["spend"] is not None else "n/a",
                "expected_result": str(present(cur["expected_result_after_ads"]))
                if cur["expected_result_after_ads"] is not None
                else None,
                "delta_pct": delta,
                "uncertainty": "LOW_MATURITY" if age < 14 else "MEDIUM" if age < 21 else "OK",
            }
        )
    decisions = [
        {
            "status": d.status,
            "entity_ref": d.entity_ref,
            "action_type": d.action_type,
            "reason": d.reason[:140],
            "outcome": d.outcome,
        }
        for d in session.execute(
            select(Decision).where(
                Decision.proposed_at >= datetime.combine(start, datetime.min.time(), tzinfo=as_of.tzinfo),
                Decision.proposed_at <= as_of,
            )
        ).scalars()
    ]
    exps = [
        {"kind": e.kind, "status": e.status, "hypothesis": e.hypothesis[:140]}
        for e in session.execute(
            select(Experiment).where(Experiment.status.in_(("PLANNED", "RUNNING")))
        ).scalars()
    ]
    body = WeeklyReportBody(
        period_start=start,
        period_end=end,
        as_of=as_of,
        completeness=completeness,
        maturity_note=f"Kohorty COD z tego tygodnia mają {max(0, (as_of.date() - end).days)} dni; wynik oczekiwany jest estymacją i będzie korygowany.",
        shops=rows,
        concepts=concentration,
        decisions=decisions,
        experiments=exps,
        constraints=[],
        plan_7d=plan,
        missing=missing,
    )
    existing = session.execute(
        select(Report)
        .where(Report.kind == "weekly", Report.period_start == start)
        .order_by(Report.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    md = render_markdown("weekly.md.j2", b=body)
    report = Report(
        kind="weekly",
        scope="global",
        period_start=start,
        period_end=end,
        revision=(existing.revision + 1) if existing else 1,
        as_of=as_of,
        completeness=completeness,
        status="NORMAL",
        body=body.model_dump(mode="json"),
        rendered_markdown=md,
        rendered_html=markdown_to_html(md),
        missing=missing,
    )
    session.add(report)
    session.flush()
    return body, report
