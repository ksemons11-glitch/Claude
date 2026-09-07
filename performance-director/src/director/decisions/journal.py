"""Decision Journal lifecycle: PROPOSED -> APPROVED/REJECTED -> EXECUTED -> EVALUATING -> SUCCESS/INCONCLUSIVE/FAILURE (EXPIRED on timeout).
Only executed decisions are evaluated, from verified_executed_at. Rejection is not a failed experiment."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import (
    AuditEvent,
    Decision,
    DecisionEvaluation,
    Experiment,
    Recommendation,
    StructureChange,
)
from director.diagnostics.baselines import robust_z
from director.metrics.aggregates import series

HORIZONS = (24, 72, 168)


def propose(
    session: Session,
    rec: Recommendation,
    *,
    now: datetime,
    data_as_of: datetime,
    expected_effect: dict[str, Any] | None = None,
    policy_version: str = "1",
) -> Decision:
    d = Decision(
        recommendation_id=rec.id,
        entity_ref=rec.entity_ref,
        action_type=rec.action_type,
        reason=rec.fact,
        rule_id=rec.rule_id,
        data_as_of=data_as_of,
        expected_effect=expected_effect or {},
        primary_metric="expected_result_after_ads",
        alternative=rec.alternative,
        status="PROPOSED",
        proposed_at=now,
        expires_at=now + timedelta(days=3),
        policy_version=policy_version,
        horizon_hours=168,
    )
    session.add(d)
    session.flush()
    return d


def approve(
    session: Session, decision: Decision, *, actor: str, now: datetime, correlation_id: str
) -> Decision:
    _require(decision, "PROPOSED")
    decision.status, decision.approved_at, decision.approved_by = "APPROVED", now, actor
    _audit(session, actor, "decision.approve", decision.id, now, correlation_id)
    return decision


def reject(
    session: Session, decision: Decision, *, actor: str, now: datetime, correlation_id: str, reason: str = ""
) -> Decision:
    _require(decision, "PROPOSED")
    decision.status, decision.rejected_at, decision.outcome = "REJECTED", now, None  # NOT a failed experiment
    _audit(session, actor, "decision.reject", decision.id, now, correlation_id, {"reason": reason})
    return decision


def mark_executed(
    session: Session,
    decision: Decision,
    *,
    now: datetime,
    kind: str,
    state_before: dict[str, Any],
    state_after: dict[str, Any],
    verified: bool,
    actor: str,
    correlation_id: str,
    structure_change_id: uuid.UUID | None = None,
) -> Decision:
    """Manual executions require a snapshot/evidence (structure change or explicit before/after) before evaluation starts."""
    _require(decision, "APPROVED")
    decision.status = "EXECUTED"
    decision.executed_at = now
    decision.execution_kind = kind
    decision.state_before, decision.state_after = state_before, state_after
    if verified or structure_change_id is not None:
        decision.verified_executed_at = now
        decision.status = "EVALUATING"
        if structure_change_id is not None:
            sc = session.get(StructureChange, structure_change_id)
            if sc is not None:
                sc.decision_id = decision.id
    _audit(
        session,
        actor,
        "decision.executed",
        decision.id,
        now,
        correlation_id,
        {"kind": kind, "verified": verified},
    )
    return decision


def expire_stale(session: Session, *, now: datetime) -> int:
    n = 0
    for d in session.execute(
        select(Decision).where(Decision.status == "PROPOSED", Decision.expires_at < now)
    ).scalars():
        d.status = "EXPIRED"
        n += 1
    return n


def due_evaluations(session: Session, *, now: datetime) -> list[tuple[Decision, int]]:
    out: list[tuple[Decision, int]] = []
    for d in session.execute(
        select(Decision).where(Decision.status == "EVALUATING", Decision.verified_executed_at.isnot(None))
    ).scalars():
        done = {
            e.horizon_hours
            for e in session.execute(
                select(DecisionEvaluation).where(DecisionEvaluation.decision_id == d.id)
            ).scalars()
        }
        for h in HORIZONS:
            if h not in done and d.verified_executed_at + timedelta(hours=h) <= now:
                out.append((d, h))
    return out


def evaluate(
    session: Session,
    decision: Decision,
    *,
    horizon_hours: int,
    now: datetime,
    shop_key: str,
    tz_name: str,
    confounders: list[str] | None = None,
    data_complete: bool = True,
    cod_mature: bool | None = None,
) -> DecisionEvaluation:
    """Observational comparison of the primary metric before vs after. Never claims causality."""
    from director.metrics.calendar import business_date_of

    exec_day = business_date_of(decision.verified_executed_at, tz_name)
    metric = decision.primary_metric
    before_dates = [exec_day - timedelta(days=i) for i in range(14, 0, -1)]
    after_days = max(1, horizon_hours // 24)
    after_dates = [exec_day + timedelta(days=i) for i in range(1, after_days + 1)]
    before = series(session, scope="shop", key=shop_key, metric=metric, dates=before_dates, as_of=now)
    after = series(session, scope="shop", key=shop_key, metric=metric, dates=after_dates, as_of=now)
    spend_before = series(session, scope="shop", key=shop_key, metric="spend", dates=before_dates, as_of=now)
    spend_after = series(session, scope="shop", key=shop_key, metric="spend", dates=after_dates, as_of=now)
    conf = list(confounders or [])
    overlapping = (
        session.execute(
            select(Experiment).where(
                Experiment.shop_id.isnot(None), Experiment.status == "RUNNING", Experiment.kind == "PRICE"
            )
        )
        .scalars()
        .all()
    )
    if overlapping:
        conf.append("PRICE_EXPERIMENT_OVERLAP")
    if cod_mature is False or horizon_hours < 168:
        conf.append("COD_COHORT_IMMATURE")
    if not data_complete:
        conf.append("DATA_INCOMPLETE")
    vals_after = [v for v in after if v is not None]
    verdict = "INCONCLUSIVE"
    z_after = None
    if vals_after and len([b for b in before if b is not None]) >= 7:
        mean_after = sum(vals_after, start=Decimal(0)) / len(vals_after)
        rz = robust_z(mean_after, before, min_n=7)
        z_after = rz.z
        if (
            rz.usable
            and rz.z is not None
            and not any(c in ("PRICE_EXPERIMENT_OVERLAP", "DATA_INCOMPLETE") for c in conf)
            and horizon_hours >= 168
        ):
            verdict = "SUCCESS" if rz.z > 1.0 else "FAILURE" if rz.z < -1.0 else "INCONCLUSIVE"
    sb = [s for s in spend_before if s is not None]
    sa = [s for s in spend_after if s is not None]
    spend_shift = (
        (sum(sa, start=Decimal(0)) / len(sa)) - (sum(sb, start=Decimal(0)) / len(sb)) if sa and sb else None
    )
    if spend_shift is not None and abs(spend_shift) > 0:
        conf.append("SPEND_CHANGED")
    ev = DecisionEvaluation(
        decision_id=decision.id,
        horizon_hours=horizon_hours,
        as_of=now,
        verdict=verdict,
        confounders=sorted(set(conf)),
        observational_result=True,
        outcomes={
            "metric": metric,
            "before": [str(v) if v is not None else None for v in before],
            "after": [str(v) if v is not None else None for v in after],
            "z_after": z_after,
            "spend_shift": str(spend_shift) if spend_shift is not None else None,
            "hypothesis": decision.expected_effect,
        },
        notes="Wynik obserwacyjny: sam wzrost po zmianie nie dowodzi przyczynowości."
        if verdict != "INCONCLUSIVE"
        else "Niedojrzałe kohorty / nakładające się zmiany.",
    )
    session.add(ev)
    if horizon_hours == max(HORIZONS):
        decision.outcome = verdict
        decision.status = verdict if verdict in ("SUCCESS", "FAILURE") else "INCONCLUSIVE"
    return ev


def similar_experiments(session: Session, *, shop_id: uuid.UUID, keys: list[str]) -> list[Experiment]:
    """Structured (SQL) lookup by product/concept/offer/audience keys before a new test."""
    rows = session.execute(select(Experiment).where(Experiment.shop_id == shop_id)).scalars().all()
    ks = set(keys)
    return [e for e in rows if ks & set(e.similarity_keys or [])]


def _require(decision: Decision, status: str) -> None:
    if decision.status != status:
        raise ValueError(f"decision {decision.id} is {decision.status}, expected {status}")


def _audit(
    session: Session,
    actor: str,
    op: str,
    obj_id: uuid.UUID,
    now: datetime,
    correlation_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            operation=op,
            object_type="decision",
            object_id=str(obj_id),
            occurred_at=now,
            correlation_id=correlation_id,
            details=details or {},
        )
    )


def as_day(dt: datetime) -> date:
    return dt.date()
