"""Scenario 9: duplicate ad names / Post IDs and legacy UTM never produce double revenue or false matches."""

import uuid
from decimal import Decimal

from director.metrics.attribution import AdIndex, attribute, coverage, parse_utm


def index():
    idx = AdIndex()
    c1, a1, ad1, ad2, ad3 = (uuid.uuid4() for _ in range(5))
    idx.campaigns_by_external["120210000000000101"] = {"id": c1, "name": "VS"}
    idx.campaigns_by_name["VS"] = ["120210000000000101"]
    idx.adsets_by_external["120210000000000201"] = {"id": a1, "campaign_id": c1, "name": "set"}
    idx.ads_by_external["120210000000000301"] = {
        "id": ad1,
        "adset_id": a1,
        "campaign_id": c1,
        "name": "Hook A",
    }
    idx.ads_by_external["120210000000000302"] = {
        "id": ad2,
        "adset_id": a1,
        "campaign_id": c1,
        "name": "Hook A",
    }  # same name!
    idx.ads_by_external["120210000000000303"] = {
        "id": ad3,
        "adset_id": a1,
        "campaign_id": c1,
        "name": "Hook B",
    }
    idx.ads_by_name = {
        "Hook A": ["120210000000000301", "120210000000000302"],
        "Hook B": ["120210000000000303"],
    }
    return idx


def test_id_based_template_matches_ad():
    p = parse_utm(
        {
            "utm_source": "fb",
            "utm_id": "120210000000000101",
            "utm_term": "120210000000000201",
            "utm_content": "120210000000000303",
        }
    )
    assert p.template == "id_based"
    r = attribute(p, index())
    assert r.level == "AD" and r.method == "utm_ad_id" and r.confidence == "HIGH"


def test_legacy_ambiguous_name_falls_back_to_adset_not_ad():
    r = attribute(parse_utm({"utm_content": "Hook A"}), index())
    assert r.level == "ADSET" and r.ad_id is None and r.evidence["ambiguous_ad_name"] == 2


def test_legacy_unique_name_matches_medium_confidence():
    r = attribute(parse_utm({"utm_content": "Hook B"}), index())
    assert r.level == "AD" and r.confidence == "MEDIUM"


def test_unexpanded_macro_and_stale_id_are_unknown_not_guessed():
    assert parse_utm({"utm_content": "{{ad.id}}"}).template == "malformed"
    r = attribute(parse_utm({"utm_content": "{{ad.id}}"}), index())
    assert r.level == "UNKNOWN"
    r2 = attribute(parse_utm({"utm_id": "120210000000000101", "utm_content": "120209999999999999"}), index())
    assert r2.level == "CAMPAIGN" and "AD_ID_NOT_IN_ACCOUNT" in r2.evidence["flags"]


def test_coverage_reports_orders_and_revenue_and_unknown_is_not_spread():
    idx = index()
    results = [
        (attribute(parse_utm({"utm_content": "Hook B"}), idx), Decimal("100")),
        (attribute(parse_utm({}), idx), Decimal("300")),
    ]
    cov = coverage(results, "AD")
    assert cov["orders_share"] == 0.5 and cov["revenue_share"] == Decimal("0.25")
