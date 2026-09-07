"""Deterministic metric definitions (§8). Decimal only. Zero denominators return null + reason.
Period ratios are ratio-of-sums, never averages of daily ratios."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from director.contracts.common import MetricValue

DEFINITIONS_VERSION = "1"
D0 = Decimal("0")


def _d(v: Decimal | int | str | None) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def safe_ratio(
    metric: str,
    num: Decimal | int | None,
    den: Decimal | int | None,
    *,
    scale: Decimal = Decimal("1"),
    unit: str = "",
    window: str = "",
    flags: list[str] | None = None,
) -> MetricValue:
    n, d = _d(num), _d(den)
    flags = list(flags or [])
    if n is None or d is None:
        return MetricValue(
            metric=metric, numerator=n, denominator=d, reason="NO_DATA", unit=unit, window=window, flags=flags
        )
    if d == 0:
        reason = "ZERO_DENOMINATOR"
        if metric.startswith("cpa") and n > 0:
            reason = "ZERO_PURCHASES_WITH_SPEND"
        return MetricValue(
            metric=metric, numerator=n, denominator=d, reason=reason, unit=unit, window=window, flags=flags
        )
    return MetricValue(
        metric=metric,
        value=(n / d) * scale,
        numerator=n,
        denominator=d,
        unit=unit,
        window=window,
        flags=flags,
    )


def pct_change(current: Decimal | None, baseline: Decimal | None) -> MetricValue:
    c, b = _d(current), _d(baseline)
    if c is None or b is None:
        return MetricValue(metric="pct_change", reason="NO_DATA")
    if b == 0:
        return MetricValue(
            metric="pct_change",
            numerator=c,
            denominator=b,
            reason="ZERO_BASELINE",
            flags=["NEW_OR_ZERO_BASE"],
        )
    return MetricValue(metric="pct_change", value=(c - b) / abs(b), numerator=c, denominator=b)


@dataclass(frozen=True)
class AdTotals:
    spend: Decimal = D0
    impressions: int = 0
    link_clicks: int = 0
    clicks_all: int = 0
    purchases: int = 0
    purchase_value: Decimal = D0

    def __add__(self, other: AdTotals) -> AdTotals:
        return AdTotals(
            self.spend + other.spend,
            self.impressions + other.impressions,
            self.link_clicks + other.link_clicks,
            self.clicks_all + other.clicks_all,
            self.purchases + other.purchases,
            self.purchase_value + other.purchase_value,
        )


@dataclass(frozen=True)
class OrderTotals:
    orders: int = 0
    revenue: Decimal = D0  # ordered revenue (gross, after discounts)
    attributed_orders: int = 0
    attributed_revenue: Decimal = D0
    expected_contribution: Decimal | None = None
    realized_contribution: Decimal | None = None
    contribution_before_ads_per_order: Decimal | None = None  # BE CPA input

    def __add__(self, other: OrderTotals) -> OrderTotals:
        def add_opt(a: Decimal | None, b: Decimal | None) -> Decimal | None:
            return None if a is None or b is None else a + b

        return OrderTotals(
            self.orders + other.orders,
            self.revenue + other.revenue,
            self.attributed_orders + other.attributed_orders,
            self.attributed_revenue + other.attributed_revenue,
            add_opt(self.expected_contribution, other.expected_contribution),
            add_opt(self.realized_contribution, other.realized_contribution),
            None,
        )


def media_metrics(t: AdTotals, window: str = "") -> dict[str, MetricValue]:
    return {
        "ctr_link": safe_ratio("ctr_link", t.link_clicks, t.impressions, unit="ratio", window=window),
        "cpc_link": safe_ratio("cpc_link", t.spend, t.link_clicks, unit="PLN", window=window),
        "cpm": safe_ratio("cpm", t.spend, t.impressions, scale=Decimal(1000), unit="PLN", window=window),
        "cpa_meta": safe_ratio("cpa_meta", t.spend, t.purchases, unit="PLN", window=window),
        "roas_meta": safe_ratio("roas_meta", t.purchase_value, t.spend, unit="ratio", window=window),
        "spend": MetricValue(metric="spend", value=t.spend, unit="PLN", window=window),
        "purchases_meta": MetricValue(
            metric="purchases_meta", value=Decimal(t.purchases), unit="count", window=window
        ),
    }


def business_metrics(
    o: OrderTotals, spend: Decimal | None, *, only_meta_costs: bool = True, window: str = ""
) -> dict[str, MetricValue]:
    mer_flags = ["MER_VS_META_ONLY"] if only_meta_costs else []
    out = {
        "orders": MetricValue(metric="orders", value=Decimal(o.orders), unit="count", window=window),
        "revenue_ordered": MetricValue(metric="revenue_ordered", value=o.revenue, unit="PLN", window=window),
        "aov": safe_ratio("aov", o.revenue, o.orders, unit="PLN", window=window),
        "mer_ordered": safe_ratio(
            "mer_ordered", o.revenue, spend, unit="ratio", window=window, flags=mer_flags
        ),
        "roas_attributed_ordered": safe_ratio(
            "roas_attributed_ordered", o.attributed_revenue, spend, unit="ratio", window=window
        ),
        "cpa_attributed": safe_ratio(
            "cpa_attributed",
            spend,
            o.attributed_orders,
            unit="PLN",
            window=window,
            flags=["NOT_NEW_CUSTOMER_CAC"],
        ),
    }
    if o.expected_contribution is not None:
        out["expected_contribution"] = MetricValue(
            metric="expected_contribution",
            value=o.expected_contribution,
            unit="PLN",
            window=window,
            flags=["ESTIMATED"],
        )
        if spend is not None:
            out["expected_result_after_ads"] = MetricValue(
                metric="expected_result_after_ads",
                value=o.expected_contribution - spend,
                unit="PLN",
                window=window,
                flags=["ESTIMATED"],
            )
    else:
        out["expected_contribution"] = MetricValue(
            metric="expected_contribution", reason="MISSING_COSTS", window=window
        )
    if o.realized_contribution is not None:
        out["realized_contribution"] = MetricValue(
            metric="realized_contribution", value=o.realized_contribution, unit="PLN", window=window
        )
    return out


def breakeven(
    contribution_before_ads_per_order: Decimal | None, aov: Decimal | None, window: str = ""
) -> dict[str, MetricValue]:
    if contribution_before_ads_per_order is None:
        return {
            "be_cpa": MetricValue(metric="be_cpa", reason="MISSING_COSTS", window=window),
            "be_roas": MetricValue(metric="be_roas", reason="MISSING_COSTS", window=window),
        }
    be_cpa = MetricValue(metric="be_cpa", value=contribution_before_ads_per_order, unit="PLN", window=window)
    if contribution_before_ads_per_order <= 0:
        return {
            "be_cpa": be_cpa,
            "be_roas": MetricValue(metric="be_roas", reason="NON_POSITIVE_BE_CPA", window=window),
        }
    return {
        "be_cpa": be_cpa,
        "be_roas": safe_ratio("be_roas", aov, contribution_before_ads_per_order, unit="ratio", window=window),
    }


def spend_as_multiple_of_target(spend: Decimal, target_cpa: Decimal | None) -> MetricValue:
    return safe_ratio("spend_x_target_cpa", spend, target_cpa, unit="x")
