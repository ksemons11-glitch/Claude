"""Scenarios 15, 16, 17 and portfolio/promotions logic."""

from datetime import date
from decimal import Decimal

from director.creatives.identity import concentration
from director.metrics.ledger import CostRule
from director.portfolio.allocation import Candidate, allocate, marginal_slope
from director.promotions.simulator import OfferSpec, consistency_checks, simulate


def test_concentration_collapses_duplicate_placements():
    values = {"ad1": Decimal("500"), "ad2": Decimal("240"), "ad3": Decimal("260")}
    cmap = {
        "ad1": "asset:A",
        "ad2": "asset:A",
        "ad3": "asset:B",
    }  # ad1 & ad2 are the same video in two ad sets
    c = concentration(values, cmap)
    assert c["creatives"] == 2 and c["top_share"] == Decimal("740") / Decimal("1000")
    assert "ATTRIBUTED" in c["note"]


def test_allocation_without_curve_proposes_bounded_experiment_and_respects_caps():
    thin = Candidate("shop:a", [Decimal(100)] * 4, [Decimal(50)] * 4, Decimal("400"))
    good = Candidate(
        "shop:b",
        [Decimal(100 + i * 10) for i in range(14)],
        [Decimal(80 + i * 12) for i in range(14)],
        Decimal("300"),
    )
    nocosts = Candidate("shop:c", [], [], Decimal("200"), economics_known=False)
    out = allocate(
        [thin, good, nocosts],
        amount_pln=Decimal("500"),
        total_daily_cap=Decimal("1000"),
        current_total=Decimal("900"),
        cash_reserve_ok=True,
    )
    kinds = {p.key: p.kind for p in out}
    assert (
        kinds["shop:a"] == "EXPERIMENT"
        and kinds["shop:c"] == "BLOCKED"
        and kinds["shop:b"] == "ALLOCATE"
        and kinds["portfolio"] == "BLOCKED"
    )
    alloc = next(p for p in out if p.key == "shop:b")
    assert alloc.delta_pln <= Decimal("100")  # capped by remaining cap and 15% step
    assert marginal_slope([Decimal(1)] * 3, [Decimal(1)] * 3) is None


def test_offer_simulation_scenarios_and_consistency():
    rules = [
        CostRule("COGS", Decimal("20"), product_key="p"),
        CostRule("SHIPPING", Decimal("14"), "per_order"),
        CostRule("RETURN_SHIPPING", Decimal("12"), "per_order"),
        CostRule("COD_FEE", Decimal("0.02"), "pct_of_revenue", "COD"),
    ]
    offer = OfferSpec("p", Decimal("129"), shipping_charged=Decimal("15"))
    res = simulate(offer, rules, day=date(2026, 9, 1))
    assert {r.scenario for r in res} == {"base", "pessimistic", "optimistic"}
    base = next(r for r in res if r.scenario == "base")
    assert (
        base.expected_contribution_per_order is not None
        and base.be_cpa == base.expected_contribution_per_order
        and base.be_roas > 1
    )
    missing = simulate(OfferSpec("other", Decimal("99")), rules, day=date(2026, 9, 1))
    assert all(r.missing_costs == ["COGS:other"] for r in missing)
    issues = consistency_checks(
        offer=OfferSpec("p", Decimal("129"), reference_price_gross=Decimal("199")),
        ad_copy_price=Decimal("119"),
        landing_price=Decimal("129"),
        checkout_price=Decimal("129"),
        cta_text="-50% dzisiaj",
        landing_url="https://x/a",
        ad_destination_url="https://x/b",
    )
    assert len(issues) == 3
