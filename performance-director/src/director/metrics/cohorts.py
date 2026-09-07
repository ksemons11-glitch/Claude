"""Expected-outcome model for COD cohorts.

Estimate the final-state distribution (DELIVERED / CANCELLED / UNDELIVERED / RETURNED) from *mature*
cohorts of the same shop/payment_kind/product (fallback: shop/payment_kind, then shop), accounting for
right-censoring: open orders younger than the maturity horizon are excluded from the denominator.
Expected contribution = sum over states p(state) * contribution(state). Small samples produce a wide
interval and status LOW_SAMPLE instead of false point certainty."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from director.metrics.ledger import FINAL_STATES, Contribution, CostRule, LedgerOrder, contribution_for_state

D0 = Decimal("0")
MODEL_VERSION = "1"
DEFAULT_MATURITY_DAYS = {"COD": 21, "PREPAID": 14, "UNKNOWN": 21}
PRIOR = {
    "COD": {"DELIVERED": 0.72, "CANCELLED": 0.08, "UNDELIVERED": 0.15, "RETURNED": 0.05},
    "PREPAID": {"DELIVERED": 0.93, "CANCELLED": 0.03, "UNDELIVERED": 0.01, "RETURNED": 0.03},
}
PRIOR_WEIGHT = 8  # pseudo-observations; keeps small samples honest without dominating them
MIN_SAMPLE_OK = 60
MIN_SAMPLE_MEDIUM = 25


@dataclass
class StateDistribution:
    probs: dict[str, float]
    sample_size: int
    level: str  # product | payment | shop | prior
    uncertainty: str  # OK | MEDIUM | LOW_SAMPLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "probs": {k: round(v, 4) for k, v in self.probs.items()},
            "sample_size": self.sample_size,
            "level": self.level,
            "uncertainty": self.uncertainty,
        }


def fit_distribution(final_states: list[str], payment_kind: str, level: str) -> StateDistribution:
    prior = PRIOR.get(payment_kind, PRIOR["COD"])
    counts = {s: 0 for s in FINAL_STATES}
    for s in final_states:
        if s in counts:
            counts[s] += 1
    n = sum(counts.values())
    probs = {s: (counts[s] + PRIOR_WEIGHT * prior[s]) / (n + PRIOR_WEIGHT) for s in FINAL_STATES}
    unc = "OK" if n >= MIN_SAMPLE_OK else ("MEDIUM" if n >= MIN_SAMPLE_MEDIUM else "LOW_SAMPLE")
    return StateDistribution(probs, n, level if n else "prior", unc)


@dataclass
class ExpectedOutcome:
    expected_revenue: Decimal | None
    expected_costs: Decimal | None
    expected_contribution: Decimal | None
    low: Decimal | None
    high: Decimal | None
    distribution: StateDistribution
    missing_costs: list[str] = field(default_factory=list)
    by_state: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        f = lambda v: str(v) if v is not None else None  # noqa: E731
        return {
            "expected_revenue": f(self.expected_revenue),
            "expected_costs": f(self.expected_costs),
            "expected_contribution": f(self.expected_contribution),
            "low": f(self.low),
            "high": f(self.high),
            "distribution": self.distribution.as_dict(),
            "missing_costs": self.missing_costs,
            "model_version": MODEL_VERSION,
        }


def _interval_halfwidth(dist: StateDistribution, spread: Decimal) -> Decimal:
    """Wilson-style widening of the delivered-probability by sample size, applied to the contribution spread."""
    n = max(dist.sample_size, 1)
    p = dist.probs.get("DELIVERED", 0.7)
    z = 1.96
    half = z * math.sqrt(max(p * (1 - p), 1e-6) / n)
    if dist.uncertainty == "LOW_SAMPLE":
        half = max(half, 0.25)
    return spread * Decimal(str(round(min(half, 0.5), 6)))


def expected_outcome(order: LedgerOrder, dist: StateDistribution, rules: list[CostRule]) -> ExpectedOutcome:
    if order.status_class in FINAL_STATES:  # realised: no estimate needed
        c = contribution_for_state(order, order.status_class, rules)
        val = c.contribution
        return ExpectedOutcome(
            c.revenue_retained + c.shipping_retained,
            c.total_costs if val is not None else None,
            val,
            val,
            val,
            StateDistribution({order.status_class: 1.0}, dist.sample_size, "realized", "OK"),
            c.missing_costs,
            {order.status_class: c.as_dict()},
        )
    by_state: dict[str, Contribution] = {s: contribution_for_state(order, s, rules) for s in FINAL_STATES}
    missing = sorted({m for c in by_state.values() for m in c.missing_costs})
    if missing:
        return ExpectedOutcome(
            None, None, None, None, None, dist, missing, {s: c.as_dict() for s, c in by_state.items()}
        )
    exp_rev = sum(
        (
            Decimal(str(dist.probs[s])) * (c.revenue_retained + c.shipping_retained)
            for s, c in by_state.items()
        ),
        start=D0,
    )
    exp_cost = sum((Decimal(str(dist.probs[s])) * c.total_costs for s, c in by_state.items()), start=D0)
    exp_contrib = exp_rev - exp_cost
    contribs = [c.contribution for c in by_state.values() if c.contribution is not None]
    spread = (max(contribs) - min(contribs)) if contribs else D0
    half = _interval_halfwidth(dist, spread)
    return ExpectedOutcome(
        exp_rev,
        exp_cost,
        exp_contrib,
        exp_contrib - half,
        exp_contrib + half,
        dist,
        [],
        {s: c.as_dict() for s, c in by_state.items()},
    )


def maturity_days(payment_kind: str) -> int:
    return DEFAULT_MATURITY_DAYS.get(payment_kind, 21)
