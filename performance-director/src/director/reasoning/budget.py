"""Token / cost accounting per job and a hard daily budget (PLN). Over budget -> deterministic fallback."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from director.db.models import Report

# indicative list prices per 1M tokens (USD) - override via env if needed; used only for the daily cap.
USD_PER_MTOK = {
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-sonnet-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
    "claude-fable-5-1": (Decimal("10.00"), Decimal("50.00")),
}
USD_PLN = Decimal("4.00")  # configurable approximation for budgeting, not accounting


def estimate_cost_pln(model: str, tokens_in: int, tokens_out: int) -> Decimal:
    pin, pout = USD_PER_MTOK.get(model, (Decimal("5.00"), Decimal("25.00")))
    usd = (Decimal(tokens_in) / Decimal(1_000_000)) * pin + (Decimal(tokens_out) / Decimal(1_000_000)) * pout
    return (usd * USD_PLN).quantize(Decimal("0.0001"))


def spent_today_pln(session: Session, day: date) -> Decimal:
    total = session.execute(
        select(func.coalesce(func.sum(Report.cost_pln), 0)).where(func.date(Report.as_of) == day)
    ).scalar()
    return Decimal(total or 0)


def within_budget(session: Session, *, daily_budget_pln: Decimal, now: datetime) -> tuple[bool, Decimal]:
    if daily_budget_pln <= 0:
        return False, Decimal(0)  # budget 0 => LLM disabled by policy
    spent = spent_today_pln(session, now.date())
    return spent < daily_budget_pln, spent
