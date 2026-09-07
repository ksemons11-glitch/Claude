"""UTM parsing and order->ad attribution.

Two UTM templates are supported:
  legacy   : utm_content = ad.name           (historical Nailuks mapping - name is NOT a unique identity)
  id_based : utm_id={{campaign.id}}&utm_term={{adset.id}}&utm_content={{ad.id}}
Match order: verified ad ID in the correct account -> campaign/adset ID with an unambiguous historical
ad-name alias -> campaign-level -> UNKNOWN. Unknown orders are never spread proportionally to spend.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

PARSER_VERSION = "2"
UNEXPANDED = re.compile(r"\{\{.*?\}\}")
NUMERIC_ID = re.compile(r"^\d{8,25}$")


@dataclass
class ParsedUTM:
    template: str  # id_based | legacy | none | malformed
    campaign_id: str | None = None
    adset_id: str | None = None
    ad_id: str | None = None
    ad_name: str | None = None
    campaign_name: str | None = None
    source: str | None = None
    flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "template": self.template,
            "campaign_id": self.campaign_id,
            "adset_id": self.adset_id,
            "ad_id": self.ad_id,
            "ad_name": self.ad_name,
            "campaign_name": self.campaign_name,
            "source": self.source,
            "flags": self.flags,
            "parser_version": PARSER_VERSION,
        }


def _clean(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        from urllib.parse import unquote

        s2 = unquote(s)
        if s2 != s and "%" in s:
            s = s2
    except Exception:  # pragma: no cover
        pass
    return s


def parse_utm(utm: dict[str, Any] | None) -> ParsedUTM:
    if not utm:
        return ParsedUTM(template="none", flags=["NO_UTM"])
    src = _clean(utm.get("utm_source"))
    content = _clean(utm.get("utm_content"))
    term = _clean(utm.get("utm_term"))
    uid = _clean(utm.get("utm_id"))
    camp = _clean(utm.get("utm_campaign"))
    flags: list[str] = []
    for v in (content, term, uid, camp):
        if v and UNEXPANDED.search(v):
            flags.append("UNEXPANDED_MACRO")
    if "UNEXPANDED_MACRO" in flags:
        return ParsedUTM(template="malformed", source=src, campaign_name=camp, flags=flags)
    if src and src.lower() not in ("fb", "facebook", "ig", "instagram", "meta", "an"):
        flags.append("NON_META_SOURCE")
    if content and NUMERIC_ID.match(content):
        p = ParsedUTM(template="id_based", ad_id=content, source=src, campaign_name=camp, flags=flags)
        if term and NUMERIC_ID.match(term):
            p.adset_id = term
        elif term:
            p.flags.append("ADSET_TERM_NOT_ID")
        if uid and NUMERIC_ID.match(uid):
            p.campaign_id = uid
        elif uid:
            p.flags.append("CAMPAIGN_UTM_ID_NOT_ID")
        return p
    if content:
        p = ParsedUTM(template="legacy", ad_name=content, source=src, campaign_name=camp, flags=flags)
        if uid and NUMERIC_ID.match(uid):
            p.campaign_id = uid
        return p
    if uid and NUMERIC_ID.match(uid):
        return ParsedUTM(
            template="id_based",
            campaign_id=uid,
            source=src,
            campaign_name=camp,
            flags=flags + ["CAMPAIGN_ONLY"],
        )
    return ParsedUTM(template="none", source=src, campaign_name=camp, flags=flags + ["NO_AD_IDENTIFIER"])


@dataclass
class AdIndex:
    """Lookup tables for one shop's ad account(s)."""

    ads_by_external: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )  # ad ext id -> {id, adset_id, campaign_id, name}
    adsets_by_external: dict[str, dict[str, Any]] = field(default_factory=dict)
    campaigns_by_external: dict[str, dict[str, Any]] = field(default_factory=dict)
    campaigns_by_name: dict[str, list[str]] = field(default_factory=dict)  # name -> [campaign ext ids]
    ads_by_name: dict[str, list[str]] = field(default_factory=dict)  # name -> [ad ext ids]
    aliases_by_name: dict[str, str] = field(default_factory=dict)  # unambiguous historical alias -> ad ext id
    source_account_id: uuid.UUID | None = None


@dataclass
class AttributionResult:
    level: str  # AD | ADSET | CAMPAIGN | UNKNOWN
    method: str
    confidence: str
    campaign_id: uuid.UUID | None = None
    adset_id: uuid.UUID | None = None
    ad_id: uuid.UUID | None = None
    evidence: dict[str, Any] = field(default_factory=dict)


def attribute(parsed: ParsedUTM, index: AdIndex) -> AttributionResult:
    ev: dict[str, Any] = {"template": parsed.template, "flags": parsed.flags}
    if parsed.template == "id_based" and parsed.ad_id:
        ad = index.ads_by_external.get(parsed.ad_id)
        if ad is not None:
            ev["matched"] = "ad_id"
            return AttributionResult(
                "AD", "utm_ad_id", "HIGH", ad["campaign_id"], ad["adset_id"], ad["id"], ev
            )
        ev["unknown_ad_id"] = parsed.ad_id  # copied stale ID from another account?
        ev["flags"] = parsed.flags + ["AD_ID_NOT_IN_ACCOUNT"]
    if parsed.template == "legacy" and parsed.ad_name:
        alias = index.aliases_by_name.get(parsed.ad_name)
        if alias and alias in index.ads_by_external:
            ad = index.ads_by_external[alias]
            ev["matched"] = "historical_alias"
            return AttributionResult(
                "AD", "legacy_alias", "MEDIUM", ad["campaign_id"], ad["adset_id"], ad["id"], ev
            )
        candidates = index.ads_by_name.get(parsed.ad_name, [])
        if len(candidates) == 1:
            ad = index.ads_by_external[candidates[0]]
            ev["matched"] = "unique_ad_name"
            return AttributionResult(
                "AD", "legacy_unique_name", "MEDIUM", ad["campaign_id"], ad["adset_id"], ad["id"], ev
            )
        if len(candidates) > 1:
            ev["ambiguous_ad_name"] = len(candidates)
            camps = {index.ads_by_external[c]["campaign_id"] for c in candidates}
            adsets = {index.ads_by_external[c]["adset_id"] for c in candidates}
            if len(adsets) == 1:
                ad = index.ads_by_external[candidates[0]]
                return AttributionResult(
                    "ADSET",
                    "legacy_ambiguous_same_adset",
                    "MEDIUM",
                    ad["campaign_id"],
                    ad["adset_id"],
                    None,
                    ev,
                )
            if len(camps) == 1:
                ad = index.ads_by_external[candidates[0]]
                return AttributionResult(
                    "CAMPAIGN", "legacy_ambiguous_same_campaign", "LOW", ad["campaign_id"], None, None, ev
                )
    if parsed.adset_id and parsed.adset_id in index.adsets_by_external:
        a = index.adsets_by_external[parsed.adset_id]
        return AttributionResult("ADSET", "utm_adset_id", "MEDIUM", a["campaign_id"], a["id"], None, ev)
    if parsed.campaign_id and parsed.campaign_id in index.campaigns_by_external:
        c = index.campaigns_by_external[parsed.campaign_id]
        return AttributionResult("CAMPAIGN", "utm_campaign_id", "LOW", c["id"], None, None, ev)
    if parsed.campaign_name:
        camps = index.campaigns_by_name.get(parsed.campaign_name, [])
        if len(camps) == 1:
            c = index.campaigns_by_external[camps[0]]
            return AttributionResult("CAMPAIGN", "utm_campaign_name", "LOW", c["id"], None, None, ev)
    return AttributionResult("UNKNOWN", "unmatched", "LOW", evidence=ev)


def coverage(results: list[tuple[AttributionResult, Any]], level: str) -> dict[str, Any]:
    """Share of orders AND revenue matched at least at `level` (AD > ADSET > CAMPAIGN)."""
    rank = {"AD": 3, "ADSET": 2, "CAMPAIGN": 1, "UNKNOWN": 0}
    need = rank[level]
    n = len(results)
    rev_total = sum((amt for _, amt in results), start=0)
    matched = [(r, amt) for r, amt in results if rank[r.level] >= need]
    rev_matched = sum((amt for _, amt in matched), start=0)
    return {
        "level": level,
        "orders_total": n,
        "orders_matched": len(matched),
        "orders_share": (len(matched) / n) if n else None,
        "revenue_total": str(rev_total),
        "revenue_matched": str(rev_matched),
        "revenue_share": (rev_matched / rev_total) if rev_total else None,
    }
