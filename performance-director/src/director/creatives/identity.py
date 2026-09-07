"""Creative identity: an ad_id is a placement, not the material. creative_key derives from the asset hash,
then the Post ID, then (last resort) the ad's own external id."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import Ad, Creative, CreativePlacement, Shop, SourceAccount


def creative_key_for(ad: Ad) -> str:
    if ad.asset_hash:
        return f"asset:{ad.asset_hash[:16]}"
    if ad.post_id:
        return f"post:{ad.post_id}"
    return f"ad:{ad.external_id}"


def sync_creatives(session: Session, *, shop: Shop, account: SourceAccount, now: datetime) -> dict[str, int]:
    """Ensure a Creative + open CreativePlacement for each ad; several ads may share one creative."""
    ads = session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars().all()
    creatives = {
        c.creative_key: c
        for c in session.execute(select(Creative).where(Creative.shop_id == shop.id)).scalars()
    }
    created = placements = 0
    for ad in ads:
        key = creative_key_for(ad)
        cr = creatives.get(key)
        if cr is None:
            cr = Creative(
                creative_key=key,
                shop_id=shop.id,
                name=ad.name,
                post_id=ad.post_id,
                asset_hash=ad.asset_hash,
                status="TEST",
                status_changed_at=now,
            )
            session.add(cr)
            session.flush()
            creatives[key] = cr
            created += 1
        pl = session.execute(
            select(CreativePlacement).where(
                CreativePlacement.creative_id == cr.id,
                CreativePlacement.ad_id == ad.id,
                CreativePlacement.valid_to.is_(None),
            )
        ).scalar_one_or_none()
        if pl is None:
            session.add(CreativePlacement(creative_id=cr.id, ad_id=ad.id, post_id=ad.post_id, valid_from=now))
            placements += 1
    return {"creatives_created": created, "placements_created": placements, "ads": len(ads)}


def creative_map(session: Session, account: SourceAccount) -> dict[str, str]:
    """ad external id -> creative_key"""
    return {
        ad.external_id: creative_key_for(ad)
        for ad in session.execute(select(Ad).where(Ad.source_account_id == account.id)).scalars()
    }


def concentration(values_by_ad: dict[str, Decimal], ad_to_creative: dict[str, str]) -> dict[str, Any]:
    """Share of attributed revenue (or spend) on the top creative. Placement duplicates collapse into one creative,
    so the same video in two ad sets is counted once."""
    by_creative: dict[str, Decimal] = defaultdict(Decimal)
    for ad_ext, v in values_by_ad.items():
        by_creative[ad_to_creative.get(ad_ext, f"ad:{ad_ext}")] += v
    total = sum(by_creative.values(), start=Decimal(0))
    if total <= 0:
        return {"top_creative": None, "top_share": None, "creatives": 0, "reason": "NO_ATTRIBUTED_VALUE"}
    top, top_v = max(by_creative.items(), key=lambda kv: kv[1])
    ranked = sorted(by_creative.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "top_creative": top,
        "top_share": top_v / total,
        "creatives": len(by_creative),
        "second_share": (ranked[1][1] / total) if len(ranked) > 1 else Decimal(0),
        "total": total,
        "note": "share of ATTRIBUTED value only, not of total sales",
    }


def placements_for(session: Session, creative_id: uuid.UUID) -> list[CreativePlacement]:
    return list(
        session.execute(
            select(CreativePlacement).where(CreativePlacement.creative_id == creative_id)
        ).scalars()
    )
