"""Deterministic offline demo: writes raw API-shaped fixtures for every source and seeds costs +
historical observations. Numbers are synthetic and encode the acceptance scenarios (§20):
  veluskin - profitable winner with ONE weak day (1) and 74% concentration (17), >=250 orders with shared timestamps (10)
  eloria   - five-day decline with CTR down / CPM stable (2), legacy utm_content=ad.name orders (9)
  czesio   - zero-purchase test above explicit loss cap (6), CBO budget change yesterday (5), duplicate asset in two ad sets (9)
  talio    - Meta purchases understated vs ledger (3), no COGS configured -> BE/profit unavailable (18)
  all      - late COD return updating an old cohort (7), partial refund + bundle (8), unexpanded UTM macros
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from director.db.models import HistoricalObservation, Shop
from director.metrics.calendar import business_day_bounds

SEED = 20260907
DAYS = 45
STATUS_NAMES = {
    "1": "Nowe",
    "2": "Potwierdzone",
    "3": "Wysłane",
    "4": "Dostarczone",
    "5": "Anulowane",
    "6": "Nieodebrane - zwrot do nadawcy",
    "7": "Zwrot od klienta",
}
STATUS_BY_CLASS = {"OPEN": "3", "DELIVERED": "4", "CANCELLED": "5", "UNDELIVERED": "6", "RETURNED": "7"}


@dataclass
class ProductSpec:
    sku: str
    name: str
    price: Decimal


@dataclass
class AdSpec:
    ext_id: str
    name: str
    adset_ext: str
    campaign_ext: str
    daily_spend: Decimal
    cpm: Decimal
    ctr: Decimal
    cvr: Decimal
    video_id: str
    post_id: str
    utm_template: str = "id_based"  # id_based | legacy | broken
    start_offset: int = 0  # days from the start of the horizon when the ad started
    story: str = ""


@dataclass
class ShopSpec:
    shop_key: str
    meta_account: str
    base_shop_id: str
    products: list[ProductSpec]
    cod_share: Decimal
    organic_share: Decimal
    ads: list[AdSpec] = field(default_factory=list)
    campaigns: list[dict[str, Any]] = field(default_factory=list)
    adsets: list[dict[str, Any]] = field(default_factory=list)
    meta_understate: Decimal = Decimal("0")  # share of orders NOT reported by pixel


def _shops() -> list[ShopSpec]:
    v = ShopSpec(
        "veluskin",
        "act_1022565782878410",
        "5018371",
        [
            ProductSpec("VELUSKIN-SERUM", "VeluSkin Serum 30ml", Decimal("129.00")),
            ProductSpec("VELUSKIN-SET", "VeluSkin Zestaw", Decimal("199.00")),
        ],
        Decimal("0.68"),
        Decimal("0.15"),
    )
    v.campaigns = [
        {
            "id": "120210000000000101",
            "name": "VS | ABO Testy",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "buying_type": "AUCTION",
        },
        {
            "id": "120210000000000102",
            "name": "VS | Skalowanie",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "40000",
            "buying_type": "AUCTION",
        },
    ]
    v.adsets = [
        {
            "id": "120210000000000201",
            "campaign_id": "120210000000000101",
            "name": "VS Broad PL",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "15000",
            "targeting": {"geo_locations": {"countries": ["PL"]}, "age_min": 25},
        },
        {
            "id": "120210000000000202",
            "campaign_id": "120210000000000102",
            "name": "VS Winner Scale",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "targeting": {"geo_locations": {"countries": ["PL"]}},
        },
    ]
    v.ads = [
        AdSpec(
            "120210000000000301",
            "VS Hook Dermatolog UGC v3",
            "120210000000000202",
            "120210000000000102",
            Decimal("400"),
            Decimal("38"),
            Decimal("0.018"),
            Decimal("0.052"),
            "vid_vs_win",
            "1020_vswin",
            story="winner_one_weak_day",
        ),
        AdSpec(
            "120210000000000302",
            "VS Before/After statyczna",
            "120210000000000201",
            "120210000000000101",
            Decimal("75"),
            Decimal("41"),
            Decimal("0.011"),
            Decimal("0.030"),
            "img_vs_ba",
            "1020_vsba",
        ),
        AdSpec(
            "120210000000000303",
            "VS Recenzja klientki",
            "120210000000000201",
            "120210000000000101",
            Decimal("75"),
            Decimal("36"),
            Decimal("0.013"),
            Decimal("0.034"),
            "vid_vs_rev",
            "1020_vsrev",
            start_offset=30,
        ),
    ]
    e = ShopSpec(
        "eloria",
        "act_709788145411398",
        "5018378",
        [ProductSpec("ELORIA-CREAM", "Eloria Krem 50ml", Decimal("99.00"))],
        Decimal("0.60"),
        Decimal("0.18"),
    )
    e.campaigns = [
        {
            "id": "120210000000000111",
            "name": "EL | Cosmetics",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "buying_type": "AUCTION",
        }
    ]
    e.adsets = [
        {
            "id": "120210000000000211",
            "campaign_id": "120210000000000111",
            "name": "Cosmetics",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "5000",
            "targeting": {"interests": ["Cosmetics"]},
        },
        {
            "id": "120210000000000212",
            "campaign_id": "120210000000000111",
            "name": "Krem",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "5000",
            "targeting": {"interests": ["Krem"]},
        },
        {
            "id": "120210000000000213",
            "campaign_id": "120210000000000111",
            "name": "Beauty salons",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "5000",
            "targeting": {"interests": ["Beauty salons"]},
        },
    ]
    e.ads = [
        AdSpec(
            "120210000000000311",
            "Eloria Poranna rutyna",
            "120210000000000211",
            "120210000000000111",
            Decimal("60"),
            Decimal("30"),
            Decimal("0.022"),
            Decimal("0.060"),
            "vid_el_rut",
            "1021_elrut",
            utm_template="legacy",
            story="five_day_decline",
        ),
        AdSpec(
            "120210000000000312",
            "Eloria Poranna rutyna",
            "120210000000000212",
            "120210000000000111",
            Decimal("60"),
            Decimal("30"),
            Decimal("0.021"),
            Decimal("0.058"),
            "vid_el_rut",
            "1021_elrut",
            utm_template="legacy",
            story="five_day_decline",
        ),
        AdSpec(
            "120210000000000313",
            "Eloria Skóra 40+",
            "120210000000000213",
            "120210000000000111",
            Decimal("60"),
            Decimal("31"),
            Decimal("0.020"),
            Decimal("0.055"),
            "vid_el_40",
            "1021_el40",
        ),
    ]
    c = ShopSpec(
        "czesio",
        "act_1030601799759290",
        "5019058",
        [
            ProductSpec("CZESIO-BRUSH", "Czesio Szczotka", Decimal("79.00")),
            ProductSpec("CZESIO-BUNDLE", "Czesio Zestaw 2+1", Decimal("139.00")),
        ],
        Decimal("0.70"),
        Decimal("0.12"),
    )
    c.campaigns = [
        {
            "id": "120210000000000121",
            "name": "CZ | ABO",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "buying_type": "AUCTION",
        },
        {
            "id": "120210000000000122",
            "name": "CZ | CBO Winnery",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "26000",
            "buying_type": "AUCTION",
        },
    ]
    c.adsets = [
        {
            "id": "120210000000000221",
            "campaign_id": "120210000000000121",
            "name": "CZ Broad",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "17000",
            "targeting": {"geo_locations": {"countries": ["PL"]}},
        },
        {
            "id": "120210000000000222",
            "campaign_id": "120210000000000122",
            "name": "CZ Mamy 25-44",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "targeting": {"age_min": 25, "age_max": 44},
        },
        {
            "id": "120210000000000223",
            "campaign_id": "120210000000000122",
            "name": "CZ Lookalike",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "targeting": {"custom_audiences": ["lal_1pct"]},
        },
    ]
    c.ads = [
        AdSpec(
            "120210000000000321",
            "CZ Poranek bez płaczu",
            "120210000000000222",
            "120210000000000122",
            Decimal("130"),
            Decimal("29"),
            Decimal("0.021"),
            Decimal("0.045"),
            "vid_cz_por",
            "1022_czpor",
        ),
        AdSpec(
            "120210000000000322",
            "CZ Poranek bez płaczu (LAL)",
            "120210000000000223",
            "120210000000000122",
            Decimal("130"),
            Decimal("31"),
            Decimal("0.019"),
            Decimal("0.041"),
            "vid_cz_por",
            "1022_czpor",
            story="duplicate_asset",
        ),
        AdSpec(
            "120210000000000323",
            "CZ Test Kolory v1",
            "120210000000000221",
            "120210000000000121",
            Decimal("70"),
            Decimal("34"),
            Decimal("0.009"),
            Decimal("0.0"),
            "vid_cz_kol",
            "1022_czkol",
            start_offset=DAYS - 4,
            story="zero_purchases_over_cap",
        ),
        AdSpec(
            "120210000000000324",
            "CZ Tata testuje",
            "120210000000000221",
            "120210000000000121",
            Decimal("100"),
            Decimal("30"),
            Decimal("0.017"),
            Decimal("0.039"),
            "vid_cz_tata",
            "1022_cztata",
        ),
    ]
    t = ShopSpec(
        "talio",
        "act_1055331276764292",
        "5021998",
        [ProductSpec("TALIO-PILLOW", "Talio Poduszka", Decimal("149.00"))],
        Decimal("0.62"),
        Decimal("0.14"),
        meta_understate=Decimal("0.35"),
    )
    t.campaigns = [
        {
            "id": "120210000000000131",
            "name": "TL | CBO Konsolidacja",
            "objective": "OUTCOME_SALES",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "daily_budget": "35000",
            "buying_type": "AUCTION",
        }
    ]
    t.adsets = [
        {
            "id": "120210000000000231",
            "campaign_id": "120210000000000131",
            "name": "TL Broad",
            "status": "ACTIVE",
            "effective_status": "ACTIVE",
            "targeting": {"geo_locations": {"countries": ["PL"]}},
        }
    ]
    t.ads = [
        AdSpec(
            "120210000000000331",
            "TL Sen bez bólu szyi",
            "120210000000000231",
            "120210000000000131",
            Decimal("200"),
            Decimal("27"),
            Decimal("0.02"),
            Decimal("0.043"),
            "vid_tl_sen",
            "1023_tlsen",
        ),
        AdSpec(
            "120210000000000332",
            "TL Fizjoterapeuta poleca",
            "120210000000000231",
            "120210000000000131",
            Decimal("150"),
            Decimal("28"),
            Decimal("0.018"),
            Decimal("0.040"),
            "vid_tl_fiz",
            "1023_tlfiz",
        ),
    ]
    return [v, e, c, t]


def _url_tags(ad: AdSpec, campaign_name: str) -> str:
    if ad.utm_template == "legacy":
        return "utm_source=fb&utm_medium=cpc&utm_campaign={{campaign.name}}&utm_content={{ad.name}}"
    return "utm_source=fb&utm_campaign={{campaign.name}}&utm_id={{campaign.id}}&utm_term={{adset.id}}&utm_content={{ad.id}}"


def _utm_for_order(rng: random.Random, ad: AdSpec, campaign_name: str) -> dict[str, str]:
    r = rng.random()
    if r < 0.03:
        return {
            "utm_source": "fb",
            "utm_campaign": campaign_name,
            "utm_id": "{{campaign.id}}",
            "utm_term": "{{adset.id}}",
            "utm_content": "{{ad.id}}",
        }
    if r < 0.05:
        return {
            "utm_source": "fb",
            "utm_campaign": campaign_name,
            "utm_id": ad.campaign_ext,
            "utm_term": ad.adset_ext,
            "utm_content": "120209999999999999",
        }  # stale copied id
    if ad.utm_template == "legacy":
        return {
            "utm_source": "fb",
            "utm_medium": "cpc",
            "utm_campaign": campaign_name,
            "utm_content": ad.name,
        }
    return {
        "utm_source": "fb",
        "utm_campaign": campaign_name,
        "utm_id": ad.campaign_ext,
        "utm_term": ad.adset_ext,
        "utm_content": ad.ext_id,
    }


def _final_state(rng: random.Random, payment_kind: str) -> str:
    r = rng.random()
    if payment_kind == "COD":
        return (
            "DELIVERED"
            if r < 0.72
            else "CANCELLED"
            if r < 0.80
            else "UNDELIVERED"
            if r < 0.95
            else "RETURNED"
        )
    return "DELIVERED" if r < 0.93 else "CANCELLED" if r < 0.96 else "UNDELIVERED" if r < 0.97 else "RETURNED"


def generate(fixture_dir: Path, *, end_day: date, tz_name: str = "Europe/Warsaw") -> dict[str, Any]:
    rng = random.Random(SEED)
    start_day = end_day - timedelta(days=DAYS - 1)
    snapshot_at = datetime.combine(end_day + timedelta(days=1), datetime.min.time(), tzinfo=UTC) + timedelta(
        hours=5
    )
    summary: dict[str, Any] = {
        "end_day": end_day.isoformat(),
        "start_day": start_day.isoformat(),
        "shops": {},
    }
    market_rows: list[dict[str, Any]] = []
    for shop in _shops():
        camp_names = {c["id"]: c["name"] for c in shop.campaigns}
        # ---------------- Meta structure (current + previous snapshot) -------------------------
        ads_raw = []
        for ad in shop.ads:
            ads_raw.append(
                {
                    "id": ad.ext_id,
                    "name": ad.name,
                    "adset_id": ad.adset_ext,
                    "campaign_id": ad.campaign_ext,
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                    "updated_time": snapshot_at.isoformat(),
                    "creative": {
                        "id": f"cr_{ad.ext_id[-3:]}",
                        "effective_object_story_id": f"10{ad.post_id}",
                        "video_id": ad.video_id,
                        "url_tags": _url_tags(ad, camp_names[ad.campaign_ext]),
                    },
                }
            )
        structure = {"campaigns": shop.campaigns, "adsets": shop.adsets, "ads": ads_raw}
        prev = json.loads(json.dumps(structure))
        if shop.shop_key == "czesio":  # budget change yesterday: CBO 200 -> 260
            for c in prev["campaigns"]:
                if c["id"] == "120210000000000122":
                    c["daily_budget"] = "20000"
        _write(
            fixture_dir / "meta" / shop.meta_account / "structure.prev.json",
            {
                "meta": {
                    "timezone": tz_name,
                    "currency": "PLN",
                    "source_updated_at": (snapshot_at - timedelta(days=1, hours=8)).isoformat(),
                },
                "pages": [prev],
            },
        )
        _write(
            fixture_dir / "meta" / shop.meta_account / "structure.json",
            {
                "meta": {
                    "timezone": tz_name,
                    "currency": "PLN",
                    "source_updated_at": snapshot_at.isoformat(),
                },
                "pages": [structure],
            },
        )
        _write(
            fixture_dir / "meta" / shop.meta_account / "account.json",
            {
                "meta": {"timezone": tz_name, "currency": "PLN"},
                "pages": [
                    {
                        "records": [
                            {
                                "external_id": shop.meta_account,
                                "name": shop.shop_key,
                                "currency": "PLN",
                                "timezone": tz_name,
                                "account_status": 1,
                            }
                        ]
                    }
                ],
            },
        )

        # ---------------- insights + orders day by day ----------------------------------------
        insight_rows: list[dict[str, Any]] = []
        orders: list[dict[str, Any]] = []
        returns: list[dict[str, Any]] = []
        panel_rows: list[dict[str, Any]] = []
        order_seq = int(shop.base_shop_id) * 1000
        for i in range(DAYS):
            day = start_day + timedelta(days=i)
            day_start_utc, _ = business_day_bounds(day, tz_name)
            day_orders_count = 0
            day_revenue = Decimal("0")
            day_spend = Decimal("0")
            day_meta_purchases = 0
            for ad in shop.ads:
                if i < ad.start_offset:
                    continue
                spend = ad.daily_spend * Decimal(str(round(rng.uniform(0.9, 1.1), 3)))
                cpm, ctr, cvr = ad.cpm, ad.ctr, ad.cvr
                if ad.story == "winner_one_weak_day" and i == DAYS - 1:
                    cvr = cvr * Decimal("0.45")  # one weak day
                if ad.story == "five_day_decline" and i >= DAYS - 6:
                    k = (
                        i - (DAYS - 6) + 1
                    )  # decline starts 6 days back so the last 5 report days are all clearly depressed
                    ctr = ctr * (Decimal(1) - Decimal("0.12") * k)  # CTR erodes, CPM stable
                    cvr = cvr * (Decimal(1) - Decimal("0.10") * k)
                impressions = int(spend / cpm * 1000)
                link_clicks = int(impressions * ctr * Decimal(str(round(rng.uniform(0.92, 1.08), 3))))
                expected_orders = float(link_clicks) * float(cvr)
                real_orders = _poisson(rng, expected_orders)
                meta_purchases = (
                    _poisson(rng, expected_orders * float(Decimal(1) - shop.meta_understate))
                    if real_orders
                    else 0
                )
                meta_purchases = min(meta_purchases, real_orders)
                if ad.story == "zero_purchases_over_cap":
                    real_orders = meta_purchases = 0
                purchase_value = Decimal(meta_purchases) * shop.products[0].price
                insight_rows.append(
                    {
                        "ad_id": ad.ext_id,
                        "ad_name": ad.name,
                        "adset_id": ad.adset_ext,
                        "campaign_id": ad.campaign_ext,
                        "date_start": day.isoformat(),
                        "date_stop": day.isoformat(),
                        "spend": f"{spend:.2f}",
                        "impressions": str(impressions),
                        "reach": str(int(impressions * 0.8)),
                        "frequency": "1.25",
                        "clicks": str(int(link_clicks * 1.4)),
                        "inline_link_clicks": str(link_clicks),
                        "outbound_clicks": [
                            {"action_type": "outbound_click", "value": str(int(link_clicks * 0.93))}
                        ],
                        "actions": [
                            {"action_type": "purchase", "value": str(meta_purchases)},
                            {"action_type": "landing_page_view", "value": str(int(link_clicks * 0.7))},
                            {"action_type": "add_to_cart", "value": str(int(real_orders * 2.2))},
                            {"action_type": "initiate_checkout", "value": str(int(real_orders * 1.5))},
                        ],
                        "action_values": [{"action_type": "purchase", "value": f"{purchase_value:.2f}"}],
                    }
                )
                day_spend += spend
                day_meta_purchases += meta_purchases
                # orders attributed to this ad
                for _ in range(real_orders):
                    order_seq += 1
                    o, rev = _order(
                        rng,
                        shop,
                        order_seq,
                        day_start_utc,
                        ad,
                        camp_names[ad.campaign_ext],
                        age_days=DAYS - 1 - i,
                    )
                    orders.append(o)
                    if o["_class"] != "CANCELLED":
                        day_orders_count += 1
                        day_revenue += rev
            # organic orders (no UTM)
            organic = _poisson(
                rng,
                float(day_orders_count)
                * float(shop.organic_share)
                / max(1e-6, 1 - float(shop.organic_share)),
            )
            for _ in range(organic):
                order_seq += 1
                o, rev = _order(rng, shop, order_seq, day_start_utc, None, None, age_days=DAYS - 1 - i)
                orders.append(o)
                if o["_class"] != "CANCELLED":
                    day_orders_count += 1
                    day_revenue += rev
            panel_rows.append(
                {
                    "date": day.isoformat(),
                    "shop": shop.shop_key,
                    "orders": day_orders_count,
                    "revenue": f"{day_revenue:.2f}",
                    "ad_spend": f"{day_spend:.2f}",
                    "meta_purchases": day_meta_purchases,
                    "profit": f"{(day_revenue * Decimal('0.42') - day_spend):.2f}",
                    "real_roas": f"{(day_revenue / day_spend) if day_spend else 0:.3f}",
                }
            )
        # returns: for RETURNED/UNDELIVERED orders; one late return today for an old cohort; one partial refund on a bundle
        ret_id = 900000
        for o in orders:
            cls = o["_class"]
            if cls in ("RETURNED", "UNDELIVERED"):
                ret_id += 1
                returns.append(
                    {
                        "return_id": str(ret_id),
                        "order_id": o["order_id"],
                        "date_add": o["date_in_status"],
                        "refund_type": "UNDELIVERED" if cls == "UNDELIVERED" else "FULL",
                        "goods_recovered": True,
                        "currency": "PLN",
                        "products": o["products"],
                        "return_shipping_cost": "12.00",
                    }
                )
        old = [o for o in orders if o["_class"] == "DELIVERED" and o["_age"] >= 30]
        if old:
            late = old[0]
            late["order_status_id"] = "7"
            late["_class"] = "RETURNED"
            late["date_in_status"] = int(
                (datetime.combine(end_day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)).timestamp()
            )
            ret_id += 1
            returns.append(
                {
                    "return_id": str(ret_id),
                    "order_id": late["order_id"],
                    "date_add": late["date_in_status"],
                    "refund_type": "FULL",
                    "goods_recovered": True,
                    "currency": "PLN",
                    "products": late["products"],
                    "return_shipping_cost": "12.00",
                    "_note": "late return of an old cohort",
                }
            )
        bundles = [
            o for o in orders if o["_class"] == "DELIVERED" and any(p.get("bundle_id") for p in o["products"])
        ]
        if bundles:
            b = bundles[0]
            ret_id += 1
            returns.append(
                {
                    "return_id": str(ret_id),
                    "order_id": b["order_id"],
                    "date_add": b["date_in_status"],
                    "refund_type": "PARTIAL",
                    "refund_amount": "20.00",
                    "goods_recovered": False,
                    "currency": "PLN",
                    "products": [],
                    "_note": "partial refund (damaged item in bundle)",
                }
            )
        for o in orders:
            for k in ("_class", "_age"):
                o.pop(k, None)
        pages = [{"status": "SUCCESS", "orders": orders[k : k + 100]} for k in range(0, len(orders), 100)]
        base_meta = {"timezone": tz_name, "currency": "PLN", "source_updated_at": snapshot_at.isoformat()}
        _write(
            fixture_dir / "baselinker" / shop.base_shop_id / "orders.json",
            {"meta": base_meta, "pages": pages},
        )
        _write(
            fixture_dir / "baselinker" / shop.base_shop_id / "open_orders.json",
            {"meta": base_meta, "pages": pages},
        )
        _write(
            fixture_dir / "baselinker" / shop.base_shop_id / "returns.json",
            {"meta": base_meta, "pages": [{"status": "SUCCESS", "returns": returns}]},
        )
        _write(
            fixture_dir / "baselinker" / shop.base_shop_id / "statuses.json",
            {
                "meta": base_meta,
                "pages": [
                    {
                        "status": "SUCCESS",
                        "statuses": [
                            {"id": k, "name": v, "name_for_customer": v} for k, v in STATUS_NAMES.items()
                        ],
                    }
                ],
            },
        )
        _write(
            fixture_dir / "meta" / shop.meta_account / "insights_daily.json",
            {
                "meta": {
                    "timezone": tz_name,
                    "currency": "PLN",
                    "source_updated_at": snapshot_at.isoformat(),
                },
                "pages": [
                    {"data": insight_rows[k : k + 500], "paging": {}}
                    for k in range(0, len(insight_rows), 500)
                ],
            },
        )
        _write(
            fixture_dir / "nailuks" / shop.shop_key / "panel_summary.json",
            {
                "meta": {
                    "timezone": tz_name,
                    "currency": "PLN",
                    "source_updated_at": snapshot_at.isoformat(),
                    "warnings": ["panel 'profit' = revenue*0.42 - ad_spend (panel definition, not ours)"],
                },
                "pages": [{"rows": panel_rows}],
            },
        )
        _write(
            fixture_dir / "store_health" / shop.shop_key / "health.json",
            {
                "meta": {},
                "pages": [
                    {
                        "records": [
                            {
                                "url": f"https://{shop.shop_key}.example/",
                                "status_code": 200,
                                "latency_ms": 310.0,
                                "ok": True,
                                "content_ok": True,
                                "error": None,
                            }
                        ]
                    }
                ],
            },
        )
        summary["shops"][shop.shop_key] = {
            "orders": len(orders),
            "insight_rows": len(insight_rows),
            "returns": len(returns),
            "pages": len(pages),
        }

    # ---------------- market ads: 14 ads from 3 concepts, 6 brands -----------------------------
    concepts = ["morning-routine-speed", "dermatologist-proof", "kids-no-tears"]
    brands = ["BrandA", "BrandB", "BrandC", "BrandD", "BrandE", "BrandF"]
    for n in range(14):
        concept = concepts[n % 3] if n < 12 else concepts[0]
        first = end_day - timedelta(days=rng.randint(5, 60))
        market_rows.append(
            {
                "id": f"mk_{n:03d}",
                "brand": brands[n % 6],
                "media_url": f"https://cdn.example/{'dup' if n in (12, 13) else n}.mp4",
                "first_seen": first.isoformat(),
                "last_seen": (end_day - timedelta(days=rng.randint(0, 3))).isoformat(),
                "countries": "PL,DE" if n % 4 == 0 else "PL",
                "hook": f"Hook {n}",
                "format": "ugc" if n % 2 else "static",
                "concept_hint": concept,
                "problem": concept.split("-")[0],
                "mechanism": "demo",
            }
        )
    _write(
        fixture_dir / "gethooked" / "global" / "market_ads.json",
        {"meta": {"source_updated_at": snapshot_at.isoformat()}, "pages": [{"ads": market_rows}]},
    )
    summary["market_ads"] = len(market_rows)
    (fixture_dir / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    l_exp, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= l_exp:
            return k - 1


def _order(
    rng: random.Random,
    shop: ShopSpec,
    seq: int,
    day_start_utc: datetime,
    ad: AdSpec | None,
    campaign_name: str | None,
    *,
    age_days: int,
) -> tuple[dict[str, Any], Decimal]:
    # shared timestamps on purpose: batches confirmed at the same second (scenario 10)
    hour = rng.choice([8, 9, 11, 13, 15, 18, 20, 21])
    minute = rng.choice([0, 15, 30, 45])
    ts = int((day_start_utc + timedelta(hours=hour, minutes=minute)).timestamp())
    prod = rng.choice(shop.products) if len(shop.products) > 1 and rng.random() < 0.35 else shop.products[0]
    qty = 2 if rng.random() < 0.1 else 1
    is_bundle = "BUNDLE" in prod.sku or "SET" in prod.sku
    payment_kind = "COD" if rng.random() < float(shop.cod_share) else "PREPAID"
    shipping = Decimal("0.00") if prod.price * qty >= Decimal("150") else Decimal("14.99")
    if age_days >= 14:
        cls = _final_state(rng, payment_kind)
    elif age_days >= 5:
        cls = "DELIVERED" if rng.random() < 0.55 else ("CANCELLED" if rng.random() < 0.1 else "OPEN")
    else:
        cls = "OPEN" if rng.random() < 0.9 else "CANCELLED"
    status_id = STATUS_BY_CLASS[cls]
    email_hash = hashlib.sha256(f"customer{seq % 900}".encode()).hexdigest()[:12]
    order = {
        "order_id": str(seq),
        "shop_order_id": str(seq - 1000),
        "order_source": "shop",
        "order_source_id": shop.base_shop_id,
        "order_status_id": status_id,
        "confirmed": True,
        "date_add": ts,
        "date_confirmed": ts,
        "date_in_status": ts + (86400 * min(age_days, 6) if cls != "OPEN" else 3600),
        "currency": "PLN",
        "payment_method": "Płatność za pobraniem" if payment_kind == "COD" else "Przelewy24",
        "payment_method_cod": "1" if payment_kind == "COD" else "0",
        "payment_done": "0" if payment_kind == "COD" else f"{prod.price * qty + shipping:.2f}",
        "delivery_method": "InPost Paczkomat",
        "delivery_price": f"{shipping:.2f}",
        "email": f"{email_hash}@example.invalid",
        "phone": "+48000000000",
        "delivery_fullname": "TEST",
        "custom_extra_fields": {},
        "products": [
            {
                "storage": "db",
                "order_product_id": str(seq * 10 + 1),
                "product_id": f"P-{prod.sku}",
                "sku": prod.sku,
                "name": prod.name,
                "price_brutto": f"{prod.price:.2f}",
                "tax_rate": 23,
                "quantity": qty,
                "bundle_id": "1" if is_bundle else 0,
            }
        ],
        "_class": cls,
        "_age": age_days,
    }
    if ad is not None:
        order["custom_extra_fields"] = _utm_for_order(rng, ad, campaign_name or "")
    return order, prod.price * qty + shipping


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def seed_historical_observations(session: Session, shops: dict[str, Shop]) -> int:
    """§3: historical notes 30.08-07.09 imported as observations/plans, never as current snapshots."""
    items = [
        (
            "veluskin",
            date(2026, 9, 6),
            "OBSERVATION",
            "Test ABO 06.09: 8 × 50 PLN/dzień; ponowne włączenie „brak targetu 5”; konsolidacja odłożona.",
        ),
        (
            "czesio",
            date(2026, 9, 7),
            "OBSERVATION",
            "ABO 240 PLN: 1 broad, 6 winnerów; CBO 200 PLN: 4 zestawy × 4 reklamy.",
        ),
        ("talio", date(2026, 9, 7), "OBSERVATION", "Konsolidacja CBO 350 PLN."),
        (
            "talio",
            date(2026, 9, 7),
            "PLAN",
            "Podwyżka do 450 PLN planowana po co najmniej 3 dniach i odpowiednim wyniku - nie potwierdzona zmiana.",
        ),
        ("eloria", date(2026, 9, 7), "OBSERVATION", "3 × 50 PLN: Cosmetics / Krem / Beauty salons."),
        (
            "eloria",
            date(2026, 9, 7),
            "PLAN",
            "Nowe kreacje po 40 PLN i duplikat Cosmetics - plan, nie zmiana.",
        ),
        (
            None,
            date(2026, 9, 7),
            "HYPOTHESIS",
            "Pixel niedoszacowuje COD o 25-40% - hipoteza pomiarowa; NIE mnożymy wyników Meta przez 1,25-1,40.",
        ),
        (
            None,
            date(2026, 9, 7),
            "HYPOTHESIS",
            "Historyczne progi ROAS i ceny nie są aktywnymi progami; wyliczyć z aktualnej ekonomiki i zatwierdzonej konfiguracji.",
        ),
    ]
    n = 0
    for shop_key, observed, kind, text in items:
        session.add(
            HistoricalObservation(
                shop_id=shops[shop_key].id if shop_key else None,
                observed_at=observed,
                source_ref="00_WIEDZA_SESJE_2026-08-30_do_09-07.md",
                kind=kind,
                text=text,
            )
        )
        n += 1
    return n
