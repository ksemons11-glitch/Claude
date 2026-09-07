"""Market signals: trend score 0-100 with documented, normalized components. PARTIAL when the comparison
window has no denominator. Emission length is advertiser interest, never a ROAS claim."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from director.db.models import Concept, Creative, MarketAd, MarketObservation, MarketSignal

WEIGHTS = {
    "share_growth": 0.30,
    "independent_brands": 0.25,
    "freshness": 0.20,
    "continuity": 0.15,
    "unique_variations": 0.10,
}


def _norm(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def concept_of(ad: MarketAd) -> str | None:
    return (ad.taxonomy or {}).get("concept_hint")


def compute_signals(
    session: Session, *, window_end: date, window_days: int = 14, now_day: date | None = None
) -> list[dict[str, Any]]:
    now_day = now_day or window_end
    w_start = window_end - timedelta(days=window_days - 1)
    p_start, p_end = w_start - timedelta(days=window_days), w_start - timedelta(days=1)
    ads = session.execute(select(MarketAd)).scalars().all()
    obs = (
        session.execute(
            select(MarketObservation).where(
                MarketObservation.observed_on >= p_start, MarketObservation.observed_on <= window_end
            )
        )
        .scalars()
        .all()
    )
    obs_by_ad: dict[uuid.UUID, list[MarketObservation]] = defaultdict(list)
    for o in obs:
        obs_by_ad[o.market_ad_id].append(o)
    per_concept: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "cur": set(),
            "prev": set(),
            "brands": set(),
            "media": set(),
            "last_seen": [],
            "obs_days": set(),
            "ads": [],
        }
    )
    cur_total = prev_total = 0
    for ad in ads:
        c = concept_of(ad)
        if not c:
            continue
        d = per_concept[c]
        d["ads"].append(ad)
        d["brands"].add(ad.brand.lower())
        d["media"].add(ad.media_hash or ad.external_id)
        if ad.last_seen:
            d["last_seen"].append(ad.last_seen)
        active_cur = (
            ad.last_seen
            and ad.last_seen >= w_start
            and (ad.first_seen is None or ad.first_seen <= window_end)
        )
        active_prev = (
            ad.first_seen and ad.first_seen <= p_end and (ad.last_seen is None or ad.last_seen >= p_start)
        )
        if active_cur:
            d["cur"].add(ad.id)
            cur_total += 1
        if active_prev:
            d["prev"].add(ad.id)
            prev_total += 1
        for o in obs_by_ad.get(ad.id, []):
            d["obs_days"].add(o.observed_on)
    out: list[dict[str, Any]] = []
    for c, d in per_concept.items():
        coverage = "FULL" if prev_total > 0 else "PARTIAL"
        cur_share = len(d["cur"]) / cur_total if cur_total else 0.0
        prev_share = len(d["prev"]) / prev_total if prev_total else None
        growth = (cur_share - prev_share) if prev_share is not None else None
        comps = {
            "share_growth": _norm(growth, -0.2, 0.2) if growth is not None else None,
            "independent_brands": _norm(len(d["brands"]), 1, 6),
            "freshness": _norm(
                (max(d["last_seen"]) - (now_day - timedelta(days=30))).days if d["last_seen"] else 0, 0, 30
            ),
            "continuity": _norm(len(d["obs_days"]), 1, 6),
            "unique_variations": _norm(len(d["media"]), 1, 10),
        }
        weights = {k: v for k, v in WEIGHTS.items() if comps[k] is not None}
        score = None
        if weights:
            total_w = sum(weights.values())
            score = int(round(100 * sum(comps[k] * weights[k] for k in weights) / total_w))
        out.append(
            {
                "concept_key": c,
                "coverage": coverage,
                "score": score,
                "components": {k: (round(v, 3) if v is not None else None) for k, v in comps.items()},
                "brands": sorted(d["brands"]),
                "unique_media": len(d["media"]),
                "ads": len(d["ads"]),
                "note": "trend = zainteresowanie reklamodawców; brak dowodu rentowności"
                + ("; wzrost udziału nieznany (brak próby porównawczej)" if growth is None else ""),
            }
        )
    return sorted(out, key=lambda x: (x["score"] is None, -(x["score"] or 0)))


def persist_signals(
    session: Session, signals: list[dict[str, Any]], *, window_end: date, window_days: int = 14
) -> int:
    n = 0
    start = window_end - timedelta(days=window_days - 1)
    for s in signals:
        concept = session.execute(
            select(Concept).where(Concept.concept_key == s["concept_key"])
        ).scalar_one_or_none()
        if concept is None:
            concept = Concept(
                concept_key=s["concept_key"],
                problem_desire=s["concept_key"],
                mechanism="(z market scan; do klasyfikacji)",
                narrative="",
                status="MARKET_ONLY",
            )
            session.add(concept)
            session.flush()
        row = session.execute(
            select(MarketSignal).where(
                MarketSignal.concept_id == concept.id,
                MarketSignal.window_start == start,
                MarketSignal.window_end == window_end,
            )
        ).scalar_one_or_none()
        if row is None:
            row = MarketSignal(
                concept_id=concept.id,
                window_start=start,
                window_end=window_end,
                coverage=s["coverage"],
                components=s["components"],
            )
            session.add(row)
        row.coverage, row.components, row.trend_score = s["coverage"], s["components"], s["score"]
        n += 1
    return n


def creative_gap(session: Session, shop_id: uuid.UUID, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Concepts seen in the market but absent from our creatives. Says nothing about whether they 'work'."""
    ours = {
        c.concept_key
        for c in session.execute(
            select(Concept)
            .join(Creative, Creative.concept_id == Concept.id)
            .where(Creative.shop_id == shop_id)
        ).scalars()
    }
    return [
        {
            "concept_key": s["concept_key"],
            "trend_score": s["score"],
            "coverage": s["coverage"],
            "our_coverage": "none",
            "note": "obserwowany na rynku; brak naszych wyników - hipoteza do testu, nie dowód działania",
        }
        for s in signals
        if s["concept_key"] not in ours
    ]


def concept_counts(session: Session, shop_id: uuid.UUID) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for cr in session.execute(select(Creative).where(Creative.shop_id == shop_id)).scalars():
        key = str(cr.concept_id) if cr.concept_id else "unclassified"
        counts[key] += 1
    return dict(counts)


def market_concept_counts(session: Session) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for ad in session.execute(select(MarketAd)).scalars():
        counts[concept_of(ad) or "unclassified"] += 1
    return dict(counts)


def as_decimal(x: float | None) -> Decimal | None:
    return None if x is None else Decimal(str(round(x, 4)))
