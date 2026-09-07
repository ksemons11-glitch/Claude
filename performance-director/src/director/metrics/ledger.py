"""Order-level contribution ledger. Every cost counted once; cost versions chosen by date;
returned goods that are recovered do not lose the full product cost."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

D0 = Decimal("0")
FINAL_STATES = ("DELIVERED", "CANCELLED", "UNDELIVERED", "RETURNED")


@dataclass
class CostRule:
    cost_type: str  # COGS | SHIPPING | RETURN_SHIPPING | FULFILLMENT | PAYMENT_FEE | COD_FEE | OTHER_VARIABLE
    amount: Decimal
    basis: str = "per_unit"  # per_unit | per_order | pct_of_revenue
    payment_kind: str | None = None
    product_key: str | None = None
    valid_from: date = date(2000, 1, 1)
    valid_to: date | None = None
    recovery_rate: Decimal | None = None  # for COGS: share recovered when goods come back
    version_id: Any = None

    def applies(self, day: date, payment_kind: str, product_key: str | None) -> bool:
        if not (self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)):
            return False
        if self.payment_kind and self.payment_kind != payment_kind:
            return False
        if self.product_key and self.product_key != product_key:
            return False
        return True


@dataclass
class LedgerItem:
    product_key: str | None
    quantity: int
    unit_price_gross: Decimal
    discount: Decimal = D0
    returned_qty: int = 0
    recovered_qty: int = 0


@dataclass
class LedgerOrder:
    business_date: date
    payment_kind: str
    status_class: str
    items: list[LedgerItem]
    shipping_charged: Decimal = D0
    refunds: Decimal = D0
    refund_return_shipping: Decimal = D0
    goods_recovered_on_refund: bool | None = None  # None = unknown -> assume goods return on RETURNED


@dataclass
class Contribution:
    revenue_retained: Decimal
    shipping_retained: Decimal
    costs: dict[str, Decimal] = field(default_factory=dict)
    missing_costs: list[str] = field(default_factory=list)
    state: str = "OPEN"

    @property
    def total_costs(self) -> Decimal:
        return sum(self.costs.values(), start=D0)

    @property
    def contribution(self) -> Decimal | None:
        if self.missing_costs:
            return None
        return self.revenue_retained + self.shipping_retained - self.total_costs

    def as_dict(self) -> dict[str, Any]:
        return {
            "revenue_retained": str(self.revenue_retained),
            "shipping_retained": str(self.shipping_retained),
            "costs": {k: str(v) for k, v in self.costs.items()},
            "missing_costs": self.missing_costs,
            "state": self.state,
            "contribution": str(self.contribution) if self.contribution is not None else None,
        }


def _pick(
    rules: list[CostRule], cost_type: str, day: date, payment_kind: str, product_key: str | None
) -> CostRule | None:
    exact = [
        r
        for r in rules
        if r.cost_type == cost_type
        and r.applies(day, payment_kind, product_key)
        and r.product_key == product_key
    ]
    if exact:
        return exact[-1]
    generic = [
        r
        for r in rules
        if r.cost_type == cost_type and r.product_key is None and r.applies(day, payment_kind, product_key)
    ]
    return generic[-1] if generic else None


def contribution_for_state(
    order: LedgerOrder, state: str, rules: list[CostRule], *, require_cogs: bool = True
) -> Contribution:
    """Contribution of an order given a (final or assumed) state. Pure function."""
    gross_items = sum((it.unit_price_gross * it.quantity - it.discount for it in order.items), start=D0)
    c = Contribution(revenue_retained=D0, shipping_retained=D0, state=state)
    day, pk = order.business_date, order.payment_kind

    if state == "CANCELLED":
        return c  # nothing shipped, nothing earned, no variable cost
    shipped = True
    if state == "UNDELIVERED":
        c.revenue_retained = D0
        c.shipping_retained = D0
    elif state == "RETURNED":
        refund = order.refunds if order.refunds else gross_items  # unknown amount -> assume full refund
        c.revenue_retained = max(D0, gross_items - refund)
        c.shipping_retained = D0 if refund >= gross_items else order.shipping_charged
    else:  # DELIVERED / OPEN (assume delivered for the "as-ordered" view)
        c.revenue_retained = gross_items - order.refunds
        c.shipping_retained = order.shipping_charged

    for it in order.items:
        rule = _pick(rules, "COGS", day, pk, it.product_key)
        if rule is None:
            if require_cogs:
                c.missing_costs.append(f"COGS:{it.product_key}")
            continue
        qty_lost = it.quantity
        if state in ("UNDELIVERED",):
            qty_lost = 0  # parcel comes back; goods recovered (return shipping charged separately)
        elif state == "RETURNED":
            if it.recovered_qty:
                recovered = it.recovered_qty
            elif order.goods_recovered_on_refund is False:
                recovered = 0
            else:  # unknown or True: returned goods come back to stock
                recovered = it.returned_qty if it.returned_qty else it.quantity
            qty_lost = it.quantity - recovered
            if rule.recovery_rate is not None and recovered:
                # partial value loss on recovered units (repackaging/damage)
                c.costs["COGS_RECOVERY_LOSS"] = c.costs.get(
                    "COGS_RECOVERY_LOSS", D0
                ) + rule.amount * recovered * (Decimal(1) - rule.recovery_rate)
        c.costs["COGS"] = c.costs.get("COGS", D0) + rule.amount * qty_lost

    if shipped:
        for ct in ("SHIPPING", "FULFILLMENT"):
            rule = _pick(rules, ct, day, pk, None)
            if rule is not None:
                c.costs[ct] = rule.amount
        if state in ("UNDELIVERED", "RETURNED"):
            rule = _pick(rules, "RETURN_SHIPPING", day, pk, None)
            if rule is not None:
                c.costs["RETURN_SHIPPING"] = (
                    rule.amount if order.refund_return_shipping == D0 else order.refund_return_shipping
                )
        if state in ("DELIVERED", "OPEN", "RETURNED"):
            fee_type = "COD_FEE" if pk == "COD" else "PAYMENT_FEE"
            rule = _pick(rules, fee_type, day, pk, None)
            if rule is not None:
                base = (
                    (gross_items + order.shipping_charged)
                    if state == "RETURNED"
                    else (c.revenue_retained + c.shipping_retained)
                )
                c.costs[fee_type] = (base * rule.amount) if rule.basis == "pct_of_revenue" else rule.amount
        rule = _pick(rules, "OTHER_VARIABLE", day, pk, None)
        if rule is not None:
            c.costs["OTHER_VARIABLE"] = (
                (gross_items * rule.amount) if rule.basis == "pct_of_revenue" else rule.amount
            )
    return c
