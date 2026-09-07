"""Offer calculator: expected margin and BE CPA for an offer under CVR/AOV/return scenarios (scenarios, not forecasts).
Also detects price/copy/CTA/landing inconsistencies. Never derives 'price before promotion' by dividing by a percent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from director.metrics.ledger import CostRule, LedgerItem, LedgerOrder, contribution_for_state

D0 = Decimal("0")


@dataclass
class OfferSpec:
    product_key: str
    price_gross: Decimal
    units: int = 1
    shipping_charged: Decimal = D0
    payment_kind: str = "COD"
    reference_price_gross: Decimal | None = None
    reference_price_basis: str | None = None  # e.g. "lowest price in last 30 days from price history"


@dataclass
class Scenario:
    name: str
    p_delivered: Decimal
    p_cancelled: Decimal
    p_undelivered: Decimal
    p_returned: Decimal
    cvr: Decimal | None = None
    aov_multiplier: Decimal = Decimal("1")

    def probs(self) -> dict[str, Decimal]:
        return {
            "DELIVERED": self.p_delivered,
            "CANCELLED": self.p_cancelled,
            "UNDELIVERED": self.p_undelivered,
            "RETURNED": self.p_returned,
        }


DEFAULT_SCENARIOS = [
    Scenario("base", Decimal("0.72"), Decimal("0.08"), Decimal("0.15"), Decimal("0.05")),
    Scenario("pessimistic", Decimal("0.62"), Decimal("0.10"), Decimal("0.22"), Decimal("0.06")),
    Scenario("optimistic", Decimal("0.80"), Decimal("0.06"), Decimal("0.10"), Decimal("0.04")),
]


@dataclass
class SimResult:
    scenario: str
    expected_contribution_per_order: Decimal | None
    be_cpa: Decimal | None
    be_roas: Decimal | None
    missing_costs: list[str] = field(default_factory=list)
    by_state: dict[str, Any] = field(default_factory=dict)


def simulate(
    offer: OfferSpec, rules: list[CostRule], *, day: date, scenarios: list[Scenario] | None = None
) -> list[SimResult]:
    out: list[SimResult] = []
    for sc in scenarios or DEFAULT_SCENARIOS:
        price = offer.price_gross * sc.aov_multiplier
        order = LedgerOrder(
            day,
            offer.payment_kind,
            "OPEN",
            [LedgerItem(offer.product_key, offer.units, price)],
            shipping_charged=offer.shipping_charged,
        )
        contribs = {s: contribution_for_state(order, s, rules) for s in sc.probs()}
        missing = sorted({m for c in contribs.values() for m in c.missing_costs})
        if missing:
            out.append(SimResult(sc.name, None, None, None, missing))
            continue
        exp = sum((sc.probs()[s] * (c.contribution or D0) for s, c in contribs.items()), start=D0)
        aov = price * offer.units + offer.shipping_charged
        out.append(
            SimResult(
                sc.name,
                exp,
                exp if exp > 0 else None,
                (aov / exp) if exp > 0 else None,
                [],
                {s: c.as_dict() for s, c in contribs.items()},
            )
        )
    return out


def consistency_checks(
    *,
    offer: OfferSpec,
    ad_copy_price: Decimal | None,
    landing_price: Decimal | None,
    checkout_price: Decimal | None,
    cta_text: str | None,
    landing_url: str | None,
    ad_destination_url: str | None,
) -> list[str]:
    issues: list[str] = []
    for label, p in (
        ("copy reklamy", ad_copy_price),
        ("landing", landing_price),
        ("checkout", checkout_price),
    ):
        if p is not None and p != offer.price_gross:
            issues.append(f"Cena w {label} ({p}) ≠ cena oferty ({offer.price_gross})")
    if (
        cta_text
        and any(k in cta_text.lower() for k in ("-50%", "gratis", "darmowa"))
        and offer.reference_price_gross is None
    ):
        issues.append("CTA sugeruje promocję, ale brak reference_price z podstawą źródłową")
    if landing_url and ad_destination_url and landing_url.split("?")[0] != ad_destination_url.split("?")[0]:
        issues.append("URL reklamy prowadzi na inny landing niż oferta")
    if offer.reference_price_gross is not None and not offer.reference_price_basis:
        issues.append("reference_price bez podstawy źródłowej (wymagana prawdziwa historia cen)")
    return issues
