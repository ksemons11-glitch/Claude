"""Scenario 19: state change after approval and write timeout -> no blind retry. OBSERVE mode has no write path."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from director.config import ExecutionLimits, Mode, Settings
from director.db.models import Decision
from director.execution import executor as ex

pytestmark = pytest.mark.db
NOW = datetime(2026, 9, 7, 6, 0, tzinfo=UTC)


def make_decision(session):
    d = Decision(
        entity_ref="campaign:1",
        action_type="PROPOSE_BUDGET_INCREASE",
        reason="t",
        data_as_of=NOW,
        proposed_at=NOW,
        status="APPROVED",
    )
    session.add(d)
    session.flush()
    return d


def settings(**kw):
    return Settings(
        app_auth_secret="x",
        mode=Mode.APPROVAL_REQUIRED,
        execution_enabled=True,
        database_url="postgresql+psycopg://x",
        **kw,
    )


def test_observe_mode_blocks_execution(session):
    d = make_decision(session)
    w = ex.MockWriter(states={"1": {"daily_budget": "200"}})
    ar = ex.preview(
        session,
        decision=d,
        target={"id": "1", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w,
        after={"daily_budget": "220"},
        settings=Settings(app_auth_secret="x", database_url="postgresql+psycopg://x"),
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    assert any(c["code"] == "EXECUTION_ENABLED" and not c["passed"] for c in ar.policy_checks)
    with pytest.raises(ValueError):
        ex.approve(session, ar, actor="owner", now=NOW, ttl_minutes=60, correlation_id="c")
    assert w.applied == []


def test_precondition_change_expires_request(session):
    d = make_decision(session)
    w = ex.MockWriter(states={"1": {"daily_budget": "200"}})
    s = settings()
    ar = ex.preview(
        session,
        decision=d,
        target={"id": "1", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w,
        after={"daily_budget": "220"},
        settings=s,
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    assert all(c["passed"] for c in ar.policy_checks), ar.policy_checks
    ex.approve(session, ar, actor="owner", now=NOW, ttl_minutes=60, correlation_id="c")
    w.states["1"] = {"daily_budget": "260"}  # someone changed it manually after approval
    ex.execute(
        session, ar, writer=w, settings=s, now=NOW + timedelta(minutes=5), actor="t", correlation_id="c"
    )
    assert ar.status == "EXPIRED" and w.applied == []


def test_timeout_never_retries_blindly(session):
    d = make_decision(session)
    s = settings()
    w = ex.MockWriter(
        states={"1": {"daily_budget": "200"}}, fail_with_timeout=True, apply_before_timeout=True
    )
    ar = ex.preview(
        session,
        decision=d,
        target={"id": "1", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w,
        after={"daily_budget": "220"},
        settings=s,
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    ex.approve(session, ar, actor="owner", now=NOW, ttl_minutes=60, correlation_id="c")
    ex.execute(session, ar, writer=w, settings=s, now=NOW, actor="t", correlation_id="c")
    assert ar.status == "VERIFIED" and len(w.applied) == 1  # control read confirmed the write
    d2 = make_decision(session)
    w2 = ex.MockWriter(
        states={"2": {"daily_budget": "200"}}, fail_with_timeout=True, apply_before_timeout=False
    )
    ar2 = ex.preview(
        session,
        decision=d2,
        target={"id": "2", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w2,
        after={"daily_budget": "220"},
        settings=s,
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    ex.approve(session, ar2, actor="owner", now=NOW, ttl_minutes=60, correlation_id="c")
    ex.execute(session, ar2, writer=w2, settings=s, now=NOW, actor="t", correlation_id="c")
    assert ar2.status == "UNKNOWN" and w2.applied == []


def test_kill_switch_and_ttl_and_limits(session):
    d = make_decision(session)
    s = settings()
    w = ex.MockWriter(states={"1": {"daily_budget": "200"}})
    ar = ex.preview(
        session,
        decision=d,
        target={"id": "1", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w,
        after={"daily_budget": "300"},
        settings=s,
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    assert any(c["code"] == "PER_OPERATION_LIMIT" and not c["passed"] for c in ar.policy_checks)  # +50% > 15%
    ar2 = ex.preview(
        session,
        decision=d,
        target={"id": "1", "account_id": "act_1"},
        operation="set_daily_budget",
        writer=w,
        after={"daily_budget": "220"},
        settings=s,
        limits=ExecutionLimits(allowed_accounts=["act_1"]),
        now=NOW,
        actor="t",
        correlation_id="c",
    )
    ex.approve(session, ar2, actor="owner", now=NOW, ttl_minutes=30, correlation_id="c")
    ex.execute(
        session, ar2, writer=w, settings=settings(kill_switch=True), now=NOW, actor="t", correlation_id="c"
    )
    assert ar2.status == "BLOCKED"
    ar2.status = "APPROVED"
    ex.execute(
        session, ar2, writer=w, settings=s, now=NOW + timedelta(hours=2), actor="t", correlation_id="c"
    )
    assert ar2.status == "EXPIRED" and w.applied == []
    assert Decimal(w.states["1"]["daily_budget"]) == Decimal("200")
