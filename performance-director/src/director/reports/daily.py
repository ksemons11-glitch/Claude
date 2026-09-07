"""Daily report assembly: numbers come from daily_metrics (DB), interpretation optionally from the LLM.
Max N actions; 'no change' is a valid outcome; PARTIAL when any source is not ready."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.config import PoliciesConfig, Settings
from director.contracts.common import MetricValue, present
from director.contracts.reasoning import ActionType, EvidenceBundle, LLMResponse, ReportStatus
from director.contracts.rules import RuleResult
from director.db.models import CohortMetric, Recommendation, Report, Shop
from director.decisions.policy import execution_allowed
from director.diagnostics.rules import ShopContext, prioritize
from director.reports.render import markdown_to_html, render_markdown
from director.reports.schemas import ActionItem, DailyReportBody, ShopRow

SEVERITY_TO_STATUS = {
    "CRITICAL": ReportStatus.ACTION_REQUIRED,
    "WATCH": ReportStatus.WATCH,
    "INFO": ReportStatus.NORMAL,
}


def _p(mv: MetricValue | None) -> str | None:
    if mv is None or mv.value is None:
        return None
    return str(present(mv.value))


def _count(mv: MetricValue | None) -> str | None:
    if mv is None or mv.value is None:
        return None
    return str(int(mv.value))


def _ratio(mv: MetricValue | None) -> str | None:
    if mv is None or mv.value is None:
        return None
    return f"{mv.value:.2f}"


def _pct(mv: MetricValue | None) -> str | None:
    if mv is None or mv.value is None:
        return None
    return f"{mv.value * 100:.0f}%"


def shop_row(
    session: Session, shop: Shop, ctx: ShopContext, rules: list[RuleResult], as_of: datetime
) -> ShopRow:
    m = ctx.metrics
    cohort = session.execute(
        select(CohortMetric)
        .where(
            CohortMetric.scope == "shop",
            CohortMetric.entity_key == shop.shop_key,
            CohortMetric.cohort_date == ctx.day,
            CohortMetric.as_of <= as_of,
        )
        .order_by(CohortMetric.as_of.desc())
        .limit(1)
    ).scalar_one_or_none()
    worst = max(
        (r.severity.value for r in rules),
        key=lambda s: ["INFO", "WATCH", "CRITICAL"].index(s),
        default="INFO",
    )
    status = (
        "DATA_ISSUE"
        if ctx.dq_critical
        else {"CRITICAL": "ACTION_REQUIRED", "WATCH": "WATCH", "INFO": "NORMAL"}[worst]
    )
    missing = [
        mv.reason for k, mv in m.items() if mv.reason and k in ("expected_contribution", "spend", "be_cpa")
    ] + [f"dq:{c}" for c in ctx.dq_critical]
    mer = m.get("mer_ordered")
    return ShopRow(
        shop_key=shop.shop_key,
        name=shop.name,
        orders=_count(m.get("orders")),
        revenue_ordered=_p(m.get("revenue_ordered")),
        spend=_p(m.get("spend")),
        expected_result_after_ads=_p(m.get("expected_result_after_ads")),
        expected_low=_p(m.get("expected_result_low")),
        expected_high=_p(m.get("expected_result_high")),
        mer_ordered=_ratio(mer),
        mer_label="MER względem Meta" if mer and "MER_VS_META_ONLY" in mer.flags else "MER",
        roas_meta=_ratio(m.get("roas_meta")),
        cpa_attributed=_p(m.get("cpa_attributed")),
        coverage_ad_orders=_pct(m.get("attribution_coverage_ad_orders")),
        uncertainty=cohort.uncertainty if cohort else "n/a",
        status=status,
        missing=sorted(set(missing)),
        evidence={
            k: f"metric:{k}:shop:{shop.shop_key}:{ctx.day.isoformat()}"
            for k in ("orders", "revenue_ordered", "spend", "expected_result_after_ads", "mer_ordered")
        },
    )


def build_bundle(
    day: date,
    as_of: datetime,
    contexts: list[ShopContext],
    rules: list[RuleResult],
    *,
    definitions_version: str,
    max_items: int,
) -> EvidenceBundle:
    metric_refs: dict[str, dict[str, Any]] = {}
    for ctx in contexts:
        for k, mv in ctx.metrics.items():
            if "_w" in k and k not in ("spend_w7", "purchases_meta_w7", "attributed_orders_w7"):
                continue
            metric_refs[f"metric:{k}:shop:{ctx.shop_key}:{day.isoformat()}"] = {
                "value": str(mv.value) if mv.value is not None else None,
                "reason": mv.reason,
                "unit": mv.unit,
                "flags": mv.flags,
            }
    refs = dict(list(metric_refs.items())[:max_items])
    quality = {
        ctx.shop_key: {"critical": ctx.dq_critical, "watch": ctx.dq_watch, "sources_fresh": ctx.sources_fresh}
        for ctx in contexts
    }
    changes = [c for ctx in contexts for c in ctx.recent_changes[:3]]
    exps = [e for ctx in contexts for e in ctx.active_experiments]
    allowed = sorted({r.entity_ref for r in rules} | {f"shop:{c.shop_key}" for c in contexts})
    return EvidenceBundle(
        business_date=day,
        as_of=as_of,
        scope="global",
        definitions_version=definitions_version,
        quality=quality,
        metric_refs=refs,
        rule_results=rules,
        recent_changes=changes,
        active_experiments=exps,
        constraints={"max_actions": 5},
        allowed_entity_refs=allowed,
    )


def assemble(
    session: Session,
    *,
    settings: Settings,
    policies: PoliciesConfig,
    day: date,
    as_of: datetime,
    shops: list[Shop],
    contexts: dict[str, ShopContext],
    rules: dict[str, list[RuleResult]],
    completeness: str,
    missing: list[str],
    llm: LLMResponse | None,
    llm_meta: dict[str, Any],
    revision: int = 1,
    revision_reason: str | None = None,
) -> tuple[DailyReportBody, list[Recommendation]]:
    all_rules = prioritize([r for rs in rules.values() for r in rs])
    max_actions = policies.thresholds.max_actions_per_report
    rows = [shop_row(session, s, contexts[s.shop_key], rules.get(s.shop_key, []), as_of) for s in shops]
    # headline: sums over shops, from DB values
    excluded: dict[str, list[str]] = {}

    def total(metric: str) -> Decimal | None:
        vals = []
        for s in shops:
            mv = contexts[s.shop_key].metrics.get(metric)
            if mv is None or mv.value is None:
                excluded.setdefault(metric, []).append(s.shop_key)
            else:
                vals.append(mv.value)
        return sum(vals, start=Decimal(0)) if vals else None

    headline = {
        k: (str(present(v)) if (v := total(k)) is not None else None)
        for k in (
            "expected_result_after_ads",
            "revenue_ordered",
            "spend",
            "expected_result_low",
            "expected_result_high",
        )
    }
    headline["orders"] = str(int(v)) if (v := total("orders")) is not None else None
    headline["excluded"] = {k: v for k, v in excluded.items() if v}
    headline["expected_low"], headline["expected_high"] = (
        headline.pop("expected_result_low"),
        headline.pop("expected_result_high"),
    )
    cashflow = {
        "settlement_inflow": str(present(total("settlement_inflow") or Decimal(0))),
        "refund_outflow": str(present(total("refund_outflow") or Decimal(0))),
    }
    any_critical_dq = any(ctx.dq_critical for ctx in contexts.values())
    if completeness == "FAILED":
        status = ReportStatus.FAILED
    elif any_critical_dq:
        status = ReportStatus.DATA_ISSUE
    else:
        status = max(
            (SEVERITY_TO_STATUS[r.severity.value] for r in all_rules),
            key=lambda s: ["NORMAL", "WATCH", "ACTION_REQUIRED"].index(s.value),
            default=ReportStatus.NORMAL,
        )
    # facts (deterministic; LLM facts must reference known refs and are appended if valid)
    facts: list[str] = []
    for row in rows:
        facts.append(
            f"{row.name}: {row.orders or 'n/a'} zam., obrót {row.revenue_ordered or 'n/a'} PLN, spend {row.spend or 'n/a'} PLN, oczekiwany wynik {row.expected_result_after_ads or 'n/a'} PLN ({row.uncertainty}), status {row.status}"
        )
    facts = facts[:5]
    if llm and llm.facts:
        facts = (llm.facts + facts)[:5]
    # actions: rule results -> recommendations (max N), execution_allowed from policy engine only
    actions: list[ActionItem] = []
    recs: list[Recommendation] = []
    llm_by_entity = {r.entity_ref: r for r in (llm.recommendations if llm else [])}
    candidates = [r for r in all_rules if r.candidate_action not in ("HOLD",) or r.severity.value != "INFO"]
    for i, r in enumerate(candidates[:max_actions], start=1):
        action = (
            ActionType(r.candidate_action)
            if r.candidate_action in ActionType.__members__
            else ActionType.WATCH
        )
        lr = llm_by_entity.get(r.entity_ref)
        hypothesis = lr.hypothesis if lr and lr.hypothesis else r.hypothesis
        allowed, _reasons = execution_allowed(settings, policies, r, action)
        rec = Recommendation(
            rule_id=r.rule_id,
            rule_version=r.rule_version,
            entity_ref=r.entity_ref,
            business_date=day,
            action_type=action.value,
            fact=r.fact,
            hypothesis=hypothesis,
            evidence_refs=r.evidence_refs,
            priority_class=r.priority_class,
            priority_rank=i,
            confidence_class=r.confidence.value,
            confidence_components=r.confidence_components,
            evidence_score=r.evidence_score,
            gates=[g.model_dump() for g in r.gates],
            blocking_gates=r.blocking_gates,
            impact=r.impact,
            urgency=r.urgency,
            effort=r.effort,
            execution_allowed=allowed,
            alternative=(lr.alternative if lr else "Bez zmian"),
            conditions=(lr.conditions if lr else []),
            next_check_at=as_of + timedelta(hours=(lr.next_check_after_hours if lr else 24)),
            expires_at=as_of + timedelta(days=3),
        )
        session.add(rec)
        session.flush()
        recs.append(rec)
        actions.append(
            ActionItem(
                rank=i,
                entity_ref=r.entity_ref,
                action_type=action.value,
                fact=r.fact,
                hypothesis=hypothesis,
                confidence=r.confidence.value,
                evidence_score=r.evidence_score,
                evidence_refs=r.evidence_refs,
                blocking_gates=r.blocking_gates,
                impact=r.impact,
                urgency=r.urgency,
                effort=r.effort,
                alternative=rec.alternative,
                conditions=rec.conditions,
                next_check_after_hours=(lr.next_check_after_hours if lr else 24),
                execution_allowed=allowed,
                recommendation_id=str(rec.id),
            )
        )
    do_not_touch = [f"{r.entity_ref}: {r.fact} (HOLD)" for r in all_rules if r.candidate_action == "HOLD"][:5]
    for ctx in contexts.values():
        if (
            ctx.concentration.get("top_creative")
            and (ctx.concentration.get("top_share") or 0) >= policies.thresholds.concentration_alert_share
        ):
            do_not_touch.append(
                f"creative:{ctx.concentration['top_creative']} ({ctx.shop_key}): winner - nie wyłączać; budować niezależne koncepty"
            )
    if llm and llm.do_not_touch:
        do_not_touch = (do_not_touch + llm.do_not_touch)[:8]
    diagnosis = [
        {
            "entity_ref": r.entity_ref,
            "fact": r.fact,
            "hypothesis": r.hypothesis,
            "confidence": r.confidence.value,
            "evidence_score": r.evidence_score,
            "candidate_action": r.candidate_action,
            "blocking_gates": r.blocking_gates,
            "evidence_refs": r.evidence_refs,
            "severity": r.severity.value,
        }
        for r in all_rules
    ]
    next_review = "Jutro 07:30 (raport D-1); decyzje oceniane po 24h/72h/7d zależnie od kompletności danych i dojrzałości kohort COD."
    body = DailyReportBody(
        business_date=day,
        as_of=as_of,
        completeness=completeness,
        status=status,
        headline=headline,
        facts=facts,
        shops=rows,
        diagnosis=diagnosis,
        actions=actions,
        do_not_touch=do_not_touch,
        next_review=next_review,
        missing=sorted(set(missing + [m for row in rows for m in row.missing])),
        cashflow=cashflow,
        definitions_version="1",
        llm={"used": bool(llm), **llm_meta},
        revision=revision,
        revision_reason=revision_reason,
    )
    return body, recs


def persist(
    session: Session,
    body: DailyReportBody,
    bundle: EvidenceBundle,
    recs: list[Recommendation],
    *,
    max_actions: int,
    scope: str = "global",
) -> Report:
    existing = session.execute(
        select(Report)
        .where(Report.kind == "daily", Report.period_start == body.business_date, Report.scope == scope)
        .order_by(Report.revision.desc())
        .limit(1)
    ).scalar_one_or_none()
    revision = (existing.revision + 1) if existing else 1
    body.revision = revision
    if existing and not body.revision_reason:
        body.revision_reason = "ponowne wykonanie / korekta danych"
    md = render_markdown("daily.md.j2", b=body, max_actions=max_actions)
    report = Report(
        kind="daily",
        scope=scope,
        period_start=body.business_date,
        period_end=body.business_date,
        revision=revision,
        revision_reason=body.revision_reason,
        as_of=body.as_of,
        completeness=body.completeness,
        status=body.status.value,
        evidence_bundle=bundle.model_dump(mode="json"),
        body=body.model_dump(mode="json"),
        rendered_markdown=md,
        rendered_html=markdown_to_html(md),
        model_name=body.llm.get("model"),
        prompt_version=body.llm.get("prompt_version"),
        llm_used=bool(body.llm.get("used")),
        llm_error=body.llm.get("error"),
        tokens_in=body.llm.get("tokens_in"),
        tokens_out=body.llm.get("tokens_out"),
        missing=body.missing,
    )
    session.add(report)
    session.flush()
    for r in recs:
        r.report_id = report.id
    return report
