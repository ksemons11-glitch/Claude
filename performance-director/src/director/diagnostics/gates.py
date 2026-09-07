"""Blocking gates for spend-change recommendations (§11). Every gate is explicit and versioned."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from director.config import ThresholdsPolicy
from director.contracts.rules import Gate

GATES_VERSION = "1"


@dataclass
class GateContext:
    sources_fresh: bool
    pagination_complete: bool
    windows_compatible: bool
    economics_known: bool
    attribution_coverage: Decimal | None
    days_since_last_change: int | None  # None = no change known
    spend_window: Decimal | None
    be_cpa: Decimal | None
    purchases_window: int
    conflicting_experiment: bool
    unexplained_failure: bool
    test_loss_cap_set: bool
    product_available: bool | None  # None = unknown stock
    extra: dict[str, Any] = field(default_factory=dict)


def evaluate_gates(ctx: GateContext, th: ThresholdsPolicy) -> list[Gate]:
    gates: list[Gate] = [
        Gate(
            code="SOURCES_FRESH",
            passed=ctx.sources_fresh,
            detail="wszystkie źródła świeże i kompletne"
            if ctx.sources_fresh
            else "źródło nieaktualne lub brak synchronizacji",
        ),
        Gate(
            code="PAGINATION_COMPLETE",
            passed=ctx.pagination_complete,
            detail="" if ctx.pagination_complete else "niekompletna paginacja w ostatnich partiach",
        ),
        Gate(
            code="WINDOWS_COMPATIBLE",
            passed=ctx.windows_compatible,
            detail="" if ctx.windows_compatible else "różne strefy/waluty/atrybucja - okna nieporównywalne",
        ),
        Gate(
            code="ECONOMICS_KNOWN",
            passed=ctx.economics_known,
            detail="" if ctx.economics_known else "brak kosztów produktu - BE/profit niedostępne",
        ),
    ]
    cov_ok = ctx.attribution_coverage is not None and ctx.attribution_coverage >= th.attribution_coverage_min
    gates.append(
        Gate(
            code="ATTRIBUTION_COVERAGE",
            passed=cov_ok,
            detail=f"pokrycie {ctx.attribution_coverage if ctx.attribution_coverage is not None else 'n/a'} vs próg {th.attribution_coverage_min}",
        )
    )
    change_ok = (
        ctx.days_since_last_change is None or ctx.days_since_last_change >= th.min_full_days_since_change
    )
    gates.append(
        Gate(
            code="POST_CHANGE_WINDOW",
            passed=change_ok,
            detail=""
            if change_ok
            else f"{ctx.days_since_last_change} pełnych dni od zmiany (< {th.min_full_days_since_change})",
        )
    )
    exposure_ok = (
        ctx.spend_window is not None
        and ctx.be_cpa is not None
        and ctx.be_cpa > 0
        and ctx.spend_window >= ctx.be_cpa * th.spend_multiple_of_target_cpa_alert
        and ctx.purchases_window >= th.min_purchases_for_cpa_compare
    )
    gates.append(
        Gate(
            code="EXPOSURE_SUFFICIENT",
            passed=exposure_ok,
            detail=f"spend={ctx.spend_window} be_cpa={ctx.be_cpa} purchases={ctx.purchases_window} (min {th.min_purchases_for_cpa_compare})",
        )
    )
    gates.append(Gate(code="NO_CONFLICTING_EXPERIMENT", passed=not ctx.conflicting_experiment))
    gates.append(Gate(code="NO_UNEXPLAINED_FAILURE", passed=not ctx.unexplained_failure))
    gates.append(
        Gate(
            code="TEST_LOSS_CAP_SET",
            passed=ctx.test_loss_cap_set,
            detail=""
            if ctx.test_loss_cap_set
            else "brak jawnego test_loss_cap - brak automatycznego wykonania",
        )
    )
    gates.append(
        Gate(
            code="PRODUCT_AVAILABLE",
            passed=ctx.product_available is True,
            detail="stan magazynu nieznany" if ctx.product_available is None else "",
        )
    )
    return gates


# Which gates block which candidate action. Informational actions never block; a pause after an explicit
# loss cap needs fresh, complete data and the cap itself - not stock or exposure.
REQUIRED_BY_ACTION: dict[str, set[str]] = {
    "PROPOSE_BUDGET_INCREASE": {
        "SOURCES_FRESH",
        "PAGINATION_COMPLETE",
        "WINDOWS_COMPATIBLE",
        "ECONOMICS_KNOWN",
        "ATTRIBUTION_COVERAGE",
        "POST_CHANGE_WINDOW",
        "EXPOSURE_SUFFICIENT",
        "NO_CONFLICTING_EXPERIMENT",
        "NO_UNEXPLAINED_FAILURE",
        "TEST_LOSS_CAP_SET",
        "PRODUCT_AVAILABLE",
    },
    "PROPOSE_BUDGET_DECREASE": {
        "SOURCES_FRESH",
        "PAGINATION_COMPLETE",
        "WINDOWS_COMPATIBLE",
        "ECONOMICS_KNOWN",
        "ATTRIBUTION_COVERAGE",
        "POST_CHANGE_WINDOW",
        "EXPOSURE_SUFFICIENT",
        "NO_CONFLICTING_EXPERIMENT",
        "NO_UNEXPLAINED_FAILURE",
    },
    "PAUSE_TEST": {"SOURCES_FRESH", "PAGINATION_COMPLETE", "TEST_LOSS_CAP_SET", "NO_UNEXPLAINED_FAILURE"},
}


def blocking(gates: list[Gate], action: str | None = None) -> list[str]:
    required = REQUIRED_BY_ACTION.get(action or "", set()) if action is not None else {g.code for g in gates}
    return [g.code for g in gates if not g.passed and g.code in required]
