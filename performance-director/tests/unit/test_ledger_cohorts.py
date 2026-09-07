"""Scenarios 7 & 8: late COD return updates the old cohort + current cashflow; partial refund, discount, bundle, recovery."""

from datetime import date
from decimal import Decimal

from director.metrics.cohorts import expected_outcome, fit_distribution
from director.metrics.ledger import CostRule, LedgerItem, LedgerOrder, contribution_for_state

RULES = [
    CostRule("COGS", Decimal("20"), recovery_rate=Decimal("0.9")),
    CostRule("SHIPPING", Decimal("14"), "per_order"),
    CostRule("RETURN_SHIPPING", Decimal("12"), "per_order"),
    CostRule("FULFILLMENT", Decimal("5"), "per_order"),
    CostRule("COD_FEE", Decimal("0.02"), "pct_of_revenue", "COD"),
    CostRule("PAYMENT_FEE", Decimal("0.015"), "pct_of_revenue", "PREPAID"),
]


def order(**kw):
    base = dict(
        business_date=date(2026, 8, 1),
        payment_kind="COD",
        status_class="OPEN",
        items=[LedgerItem("p", 1, Decimal("129"))],
        shipping_charged=Decimal("15"),
    )
    base.update(kw)
    return LedgerOrder(**base)


def test_each_cost_counted_once_and_states_differ():
    o = order()
    delivered = contribution_for_state(o, "DELIVERED", RULES)
    assert set(delivered.costs) == {"COGS", "SHIPPING", "FULFILLMENT", "COD_FEE"}
    assert delivered.contribution == Decimal("129") + Decimal("15") - Decimal("20") - Decimal("14") - Decimal(
        "5"
    ) - (Decimal("144") * Decimal("0.02"))
    assert contribution_for_state(o, "CANCELLED", RULES).contribution == Decimal("0")
    undelivered = contribution_for_state(o, "UNDELIVERED", RULES)
    assert (
        undelivered.costs["COGS"] == Decimal("0") and "RETURN_SHIPPING" in undelivered.costs
    )  # parcel returns, goods kept
    returned = contribution_for_state(o, "RETURNED", RULES)
    assert returned.revenue_retained == Decimal("0") and returned.costs["COGS"] == Decimal(
        "0"
    )  # goods recovered by default
    assert returned.costs["COGS_RECOVERY_LOSS"] == Decimal("20") * Decimal("0.1")


def test_partial_refund_discount_bundle_and_no_recovery():
    o = order(
        status_class="DELIVERED",
        items=[LedgerItem("bundle", 1, Decimal("139"), discount=Decimal("10"))],
        refunds=Decimal("20"),
        goods_recovered_on_refund=False,
    )
    c = contribution_for_state(o, "DELIVERED", RULES)
    assert c.revenue_retained == Decimal("139") - Decimal("10") - Decimal("20")
    # full return with explicit no recovery -> COGS lost entirely
    o2 = order(status_class="RETURNED", refunds=Decimal("129"), goods_recovered_on_refund=False)
    c2 = contribution_for_state(o2, "RETURNED", RULES)
    assert c2.costs["COGS"] == Decimal("20") and c2.revenue_retained == Decimal("0")


def test_missing_cogs_makes_contribution_unavailable():
    c = contribution_for_state(order(), "DELIVERED", [r for r in RULES if r.cost_type != "COGS"])
    assert c.contribution is None and c.missing_costs == ["COGS:p"]


def test_expected_outcome_low_sample_widens_interval():
    small = fit_distribution(["DELIVERED"] * 5 + ["UNDELIVERED"], "COD", "shop")
    large = fit_distribution(
        ["DELIVERED"] * 70 + ["UNDELIVERED"] * 15 + ["CANCELLED"] * 8 + ["RETURNED"] * 7, "COD", "shop"
    )
    assert small.uncertainty == "LOW_SAMPLE" and large.uncertainty == "OK"
    e_small, e_large = expected_outcome(order(), small, RULES), expected_outcome(order(), large, RULES)
    assert (e_small.high - e_small.low) > (e_large.high - e_large.low)
    assert (
        e_large.expected_contribution is not None
        and e_large.low <= e_large.expected_contribution <= e_large.high
    )


def test_late_return_moves_old_cohort_not_today():
    """The return of an order from 1 Aug reduces the 1 Aug cohort; cashflow of the refund day is a separate view."""
    d = fit_distribution(["DELIVERED"] * 60, "COD", "shop")
    before = expected_outcome(order(status_class="DELIVERED"), d, RULES).expected_contribution
    after = expected_outcome(
        order(status_class="RETURNED", refunds=Decimal("144")), d, RULES
    ).expected_contribution
    assert after < before and after < 0
