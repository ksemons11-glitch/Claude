"""Execution module - DISABLED BY DEFAULT (MODE=OBSERVE, EXECUTION_ENABLED=false).

Flow: preview (exact target IDs, before/after) -> policy check -> owner approval (TTL, single change) ->
fresh state read -> precondition_hash compare -> apply -> control read -> audit. A changed state after approval
expires the request. Timeouts never trigger blind retries: state is re-read and marked UNKNOWN if undecidable.
Only a MockWriter is implemented; a real Meta writer requires separate credentials and explicit authorization."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from director.config import ExecutionLimits, Mode, Settings
from director.db.models import ActionRequest, AuditEvent, Decision


class WriteTimeout(Exception):
    pass


class Writer(Protocol):
    def read_state(self, target: dict[str, Any]) -> dict[str, Any]: ...

    def apply(
        self, target: dict[str, Any], after: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]: ...


@dataclass
class MockWriter:
    """In-memory target store for tests/demo. `fail_with_timeout` simulates a lost response."""

    states: dict[str, dict[str, Any]] = field(default_factory=dict)
    fail_with_timeout: bool = False
    apply_before_timeout: bool = True
    applied: list[str] = field(default_factory=list)

    def read_state(self, target: dict[str, Any]) -> dict[str, Any]:
        return dict(self.states.get(target["id"], {}))

    def apply(self, target: dict[str, Any], after: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        if idempotency_key in self.applied:
            return dict(self.states[target["id"]])
        if self.fail_with_timeout:
            if self.apply_before_timeout:
                self.states[target["id"]] = dict(after)
                self.applied.append(idempotency_key)
            raise WriteTimeout("no response from target")
        self.states[target["id"]] = dict(after)
        self.applied.append(idempotency_key)
        return dict(after)


def state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()


def policy_checks(
    session: Session,
    *,
    settings: Settings,
    limits: ExecutionLimits,
    target: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    now: datetime,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(code: str, passed: bool, detail: str = "") -> None:
        checks.append({"code": code, "passed": passed, "detail": detail})

    add("KILL_SWITCH_OFF", not settings.kill_switch, "kill switch aktywny" if settings.kill_switch else "")
    add(
        "EXECUTION_ENABLED",
        settings.execution_enabled and settings.mode != Mode.OBSERVE,
        f"mode={settings.mode}, execution_enabled={settings.execution_enabled}",
    )
    add(
        "ACCOUNT_ALLOWED",
        target.get("account_id") in limits.allowed_accounts,
        f"{target.get('account_id')} nie jest na liście allowed_accounts"
        if target.get("account_id") not in limits.allowed_accounts
        else "",
    )
    b, a = before.get("daily_budget"), after.get("daily_budget")
    if b is not None and a is not None:
        b, a = Decimal(str(b)), Decimal(str(a))
        pct = abs(a - b) / b if b else Decimal("1")
        add(
            "PER_OPERATION_LIMIT",
            pct <= limits.max_budget_change_pct_per_operation,
            f"zmiana {pct:.0%} vs limit {limits.max_budget_change_pct_per_operation:.0%}",
        )
        # rolling 24h: sum of absolute budget deltas already executed for this account (defeats many-small-changes)
        since = now - timedelta(hours=24)
        rows = (
            session.execute(
                select(ActionRequest).where(
                    ActionRequest.status.in_(("EXECUTED", "VERIFIED")), ActionRequest.executed_at >= since
                )
            )
            .scalars()
            .all()
        )
        rolling = sum(
            (
                abs(
                    Decimal(str(r.after_state.get("daily_budget", 0)))
                    - Decimal(str(r.before_state.get("daily_budget", 0)))
                )
                for r in rows
                if r.target.get("account_id") == target.get("account_id")
            ),
            start=Decimal(0),
        )
        add(
            "ROLLING_24H_TOTAL",
            limits.max_rolling_24h_total_change_pln <= 0
            or rolling + abs(a - b) <= limits.max_rolling_24h_total_change_pln,
            f"suma 24h {rolling + abs(a - b)} vs {limits.max_rolling_24h_total_change_pln}",
        )
        acct_pct = (rolling + abs(a - b)) / b if b else Decimal("1")
        add(
            "PER_ACCOUNT_DAILY_LIMIT",
            acct_pct <= limits.max_daily_change_pct_per_account,
            f"{acct_pct:.0%} vs {limits.max_daily_change_pct_per_account:.0%}",
        )
        if limits.portfolio_daily_cap_pln is not None:
            add(
                "PORTFOLIO_CAP",
                a <= limits.portfolio_daily_cap_pln,
                f"{a} vs cap {limits.portfolio_daily_cap_pln}",
            )
        last = session.execute(
            select(func.max(ActionRequest.executed_at)).where(
                ActionRequest.status.in_(("EXECUTED", "VERIFIED"))
            )
        ).scalar()
        cooldown_ok = (
            last is None
            or (now - last) >= timedelta(hours=limits.cooldown_hours_after_change)
            or not any(r.target.get("id") == target.get("id") for r in rows)
        )
        add("COOLDOWN", cooldown_ok, f"ostatnia zmiana {last}" if not cooldown_ok else "")
    return checks


def preview(
    session: Session,
    *,
    decision: Decision,
    target: dict[str, Any],
    operation: str,
    writer: Writer,
    after: dict[str, Any],
    settings: Settings,
    limits: ExecutionLimits,
    now: datetime,
    actor: str,
    correlation_id: str,
) -> ActionRequest:
    before = writer.read_state(target)
    idem = hashlib.sha256(
        f"{decision.id}|{target.get('id')}|{operation}|{json.dumps(after, sort_keys=True, default=str)}".encode()
    ).hexdigest()[:48]
    existing = session.execute(
        select(ActionRequest).where(ActionRequest.idempotency_key == idem)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    ar = ActionRequest(
        decision_id=decision.id,
        target=target,
        operation=operation,
        before_state=before,
        after_state=after,
        precondition_hash=state_hash(before),
        idempotency_key=idem,
        status="PREVIEW",
        policy_checks=policy_checks(
            session, settings=settings, limits=limits, target=target, before=before, after=after, now=now
        ),
    )
    session.add(ar)
    session.flush()
    _audit(
        session,
        actor,
        "action_request.preview",
        ar.id,
        now,
        correlation_id,
        {"target": target, "operation": operation},
    )
    return ar


def approve(
    session: Session, ar: ActionRequest, *, actor: str, now: datetime, ttl_minutes: int, correlation_id: str
) -> ActionRequest:
    if ar.status != "PREVIEW":
        raise ValueError(f"cannot approve request in status {ar.status}")
    failed = [c["code"] for c in ar.policy_checks if not c["passed"]]
    if failed:
        raise ValueError(f"policy checks failed: {failed}")
    ar.status, ar.approved_by, ar.approved_at, ar.approval_expires_at = (
        "APPROVED",
        actor,
        now,
        now + timedelta(minutes=ttl_minutes),
    )
    _audit(session, actor, "action_request.approve", ar.id, now, correlation_id)
    return ar


def execute(
    session: Session,
    ar: ActionRequest,
    *,
    writer: Writer,
    settings: Settings,
    now: datetime,
    actor: str,
    correlation_id: str,
) -> ActionRequest:
    if settings.kill_switch:
        ar.status, ar.error = "BLOCKED", "kill switch active"
        return ar
    if settings.mode == Mode.OBSERVE or not settings.execution_enabled:
        ar.status, ar.error = "BLOCKED", "execution disabled (MODE=OBSERVE)"
        return ar
    if ar.status != "APPROVED":
        raise ValueError(f"cannot execute request in status {ar.status}")
    if ar.approval_expires_at and now > ar.approval_expires_at:
        ar.status, ar.error = "EXPIRED", "approval TTL exceeded"
        return ar
    fresh = writer.read_state(ar.target)
    if state_hash(fresh) != ar.precondition_hash:
        ar.status, ar.error = "EXPIRED", "target state changed after approval (precondition hash mismatch)"
        ar.verification = {"fresh_state": fresh}
        _audit(
            session, actor, "action_request.expired", ar.id, now, correlation_id, {"reason": "precondition"}
        )
        return ar
    try:
        result = writer.apply(ar.target, ar.after_state, ar.idempotency_key)
        ar.executed_at = now
        ar.status = "EXECUTED"
    except WriteTimeout as exc:
        # never retry blindly: re-read and decide
        control = writer.read_state(ar.target)
        ar.executed_at = now
        if state_hash(control) == state_hash(ar.after_state):
            ar.status, ar.error = "EXECUTED", f"timeout but control read matches target: {exc}"
            result = control
        else:
            ar.status, ar.error, ar.verification = (
                "UNKNOWN",
                f"timeout; control read does not match: {exc}",
                {"control_state": control},
            )
            _audit(session, actor, "action_request.unknown", ar.id, now, correlation_id)
            return ar
    control = writer.read_state(ar.target)
    ar.verification = {"control_state": control, "result": result}
    ar.verified_at = now
    if state_hash(control) == state_hash(ar.after_state):
        ar.status = "VERIFIED"
    else:
        ar.status, ar.error = "UNKNOWN", "control read differs from requested state"
    _audit(session, actor, "action_request.execute", ar.id, now, correlation_id, {"status": ar.status})
    return ar


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
            object_type="action_request",
            object_id=str(obj_id),
            occurred_at=now,
            correlation_id=correlation_id,
            details=details or {},
        )
    )
