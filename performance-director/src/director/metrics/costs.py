"""Cost versions: YAML -> cost_versions table; table -> CostRule list for the ledger."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import CostVersion, Product, Shop
from director.metrics.ledger import CostRule


def import_costs_yaml(session: Session, path: Path) -> int:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    n = 0
    for row in doc.get("costs", []):
        shop = session.execute(select(Shop).where(Shop.shop_key == row["shop_key"])).scalar_one()
        product = None
        if row.get("product_key"):
            product = ensure_product(
                session, shop, row["product_key"], row.get("product_name") or row["product_key"]
            )
        vf = (
            row["valid_from"]
            if isinstance(row["valid_from"], date)
            else date.fromisoformat(str(row["valid_from"]))
        )
        existing = session.execute(
            select(CostVersion).where(
                CostVersion.shop_id == shop.id,
                CostVersion.cost_type == row["cost_type"],
                CostVersion.valid_from == vf,
                CostVersion.product_id == (product.id if product else None),
                CostVersion.payment_kind == row.get("payment_kind"),
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = CostVersion(
                shop_id=shop.id,
                product_id=product.id if product else None,
                cost_type=row["cost_type"],
                amount=Decimal(str(row["amount"])),
                valid_from=vf,
            )
            session.add(existing)
            n += 1
        existing.amount = Decimal(str(row["amount"]))
        existing.basis = row.get("basis", "per_unit")
        existing.payment_kind = row.get("payment_kind")
        existing.valid_to = row.get("valid_to")
        existing.tax_basis = row.get("tax_basis", "gross")
        existing.recovery_rate = (
            Decimal(str(row["recovery_rate"])) if row.get("recovery_rate") is not None else None
        )
        existing.provenance = row.get("provenance", f"yaml:{path.name}")
    session.flush()
    return n


def ensure_product(session: Session, shop: Shop, product_key: str, name: str) -> Product:
    p = session.execute(
        select(Product).where(Product.shop_id == shop.id, Product.product_key == product_key)
    ).scalar_one_or_none()
    if p is None:
        p = Product(shop_id=shop.id, product_key=product_key, name=name)
        session.add(p)
        session.flush()
    return p


def cost_rules_for_shop(session: Session, shop: Shop) -> list[CostRule]:
    rows = session.execute(
        select(CostVersion, Product.product_key)
        .outerjoin(Product, Product.id == CostVersion.product_id)
        .where(CostVersion.shop_id == shop.id)
        .order_by(CostVersion.valid_from)
    ).all()
    return [
        CostRule(
            cost_type=cv.cost_type,
            amount=cv.amount,
            basis=cv.basis,
            payment_kind=cv.payment_kind,
            product_key=pk,
            valid_from=cv.valid_from,
            valid_to=cv.valid_to,
            recovery_rate=cv.recovery_rate,
            version_id=cv.id,
        )
        for cv, pk in rows
    ]


def product_key_for_sku(sku: str | None, name: str | None = None) -> str | None:
    if sku:
        return sku.strip().lower()
    if name:
        return "name:" + "".join(ch if ch.isalnum() else "-" for ch in name.lower()).strip("-")[:60]
    return None


def summarize_rules(rules: list[CostRule]) -> dict[str, Any]:
    return {
        "count": len(rules),
        "types": sorted({r.cost_type for r in rules}),
        "products_with_cogs": sorted(
            {r.product_key for r in rules if r.cost_type == "COGS" and r.product_key}
        ),
    }
