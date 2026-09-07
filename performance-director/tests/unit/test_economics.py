from decimal import Decimal

from director.metrics.economics import (
    AdTotals,
    OrderTotals,
    breakeven,
    business_metrics,
    media_metrics,
    pct_change,
    safe_ratio,
)


def test_zero_denominator_returns_null_with_reason():
    mv = safe_ratio("cpa_meta", Decimal("50"), 0)
    assert mv.value is None and mv.reason == "ZERO_PURCHASES_WITH_SPEND"
    assert safe_ratio("ctr_link", 0, 0).reason == "ZERO_DENOMINATOR"
    assert safe_ratio("aov", None, 3).reason == "NO_DATA"


def test_pct_change_zero_base_is_not_infinity():
    mv = pct_change(Decimal("5"), Decimal("0"))
    assert mv.value is None and mv.reason == "ZERO_BASELINE"
    assert pct_change(Decimal("110"), Decimal("100")).value == Decimal("0.1")


def test_media_metrics_ratio_of_sums_not_average_of_ratios():
    d1 = AdTotals(spend=Decimal("100"), impressions=10000, link_clicks=100, purchases=1)
    d2 = AdTotals(spend=Decimal("300"), impressions=10000, link_clicks=100, purchases=3)
    period = media_metrics(d1 + d2)
    assert period["cpa_meta"].value == Decimal("100")  # 400/4, not mean(100, 100)... same here, so check cpm
    assert period["cpm"].value == Decimal("20")  # 1000*400/20000, not mean(10, 30)


def test_mer_label_when_only_meta_costs():
    o = OrderTotals(
        orders=10, revenue=Decimal("1000"), attributed_orders=8, attributed_revenue=Decimal("800")
    )
    m = business_metrics(o, Decimal("250"), only_meta_costs=True)
    assert m["mer_ordered"].value == Decimal("4") and "MER_VS_META_ONLY" in m["mer_ordered"].flags
    assert (
        m["cpa_attributed"].value == Decimal("31.25") and "NOT_NEW_CUSTOMER_CAC" in m["cpa_attributed"].flags
    )
    assert m["expected_contribution"].reason == "MISSING_COSTS"


def test_breakeven_requires_costs_and_positive_contribution():
    assert breakeven(None, Decimal("100"))["be_cpa"].reason == "MISSING_COSTS"
    assert breakeven(Decimal("-5"), Decimal("100"))["be_roas"].reason == "NON_POSITIVE_BE_CPA"
    be = breakeven(Decimal("40"), Decimal("120"))
    assert be["be_cpa"].value == Decimal("40") and be["be_roas"].value == Decimal("3")
