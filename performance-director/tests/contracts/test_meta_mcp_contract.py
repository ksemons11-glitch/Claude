from datetime import date

import httpx

from director.adapters.base import SyncRequest
from director.adapters.http import RetryingClient
from director.adapters.mcp_client import filter_arguments, schema_hash
from director.adapters.meta import MetaAdapter, normalize_insights, normalize_structure
from director.adapters.nailuks import build_arguments


def test_meta_insights_normalization_keeps_link_clicks_separate_and_attribution_key():
    rows = {
        "data": [
            {
                "ad_id": "1",
                "ad_name": "A",
                "adset_id": "2",
                "campaign_id": "3",
                "date_start": "2026-09-06",
                "date_stop": "2026-09-06",
                "spend": "12.50",
                "impressions": "1000",
                "reach": "800",
                "clicks": "40",
                "inline_link_clicks": "25",
                "outbound_clicks": [{"action_type": "outbound_click", "value": "23"}],
                "actions": [
                    {"action_type": "purchase", "value": "2"},
                    {"action_type": "landing_page_view", "value": "18"},
                ],
                "action_values": [{"action_type": "purchase", "value": "258.00"}],
            }
        ]
    }
    r = normalize_insights(rows, attribution=["7d_click", "1d_view"], action_report_time="conversion")[0]
    assert (
        r["link_clicks"] == 25
        and r["clicks_all"] == 40
        and r["outbound_clicks"] == 23
        and r["purchases"] == 2
        and r["purchase_value"] == "258.00"
    )
    assert r["attribution_key"] == "7d_click+1d_view|conversion" and r["reach"] == 800


def test_meta_structure_budgets_from_minor_units_and_cbo_detection():
    recs = normalize_structure(
        {
            "campaigns": [
                {
                    "id": "c",
                    "name": "C",
                    "daily_budget": "40000",
                    "status": "ACTIVE",
                    "effective_status": "ACTIVE",
                }
            ],
            "adsets": [{"id": "s", "campaign_id": "c", "name": "S", "daily_budget": "15000"}],
            "ads": [
                {
                    "id": "a",
                    "adset_id": "s",
                    "campaign_id": "c",
                    "name": "A",
                    "creative": {
                        "id": "cr",
                        "video_id": "v1",
                        "effective_object_story_id": "p_1",
                        "url_tags": "utm_content={{ad.id}}",
                    },
                }
            ],
        }
    )
    camp = next(r for r in recs if r["kind"] == "campaign")
    assert camp["daily_budget"] == "400.000000" and camp["budget_type"] == "CBO"
    ad = next(r for r in recs if r["kind"] == "ad")
    assert ad["post_id"] == "p_1" and ad["asset_hash"] and ad["url_tags"].startswith("utm_content")


def test_meta_pagination_follows_next_and_rate_limit_is_retryable():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        if "after=" in str(req.url):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "ad_id": "2",
                            "date_start": "2026-09-06",
                            "spend": "1",
                            "impressions": "1",
                            "clicks": "0",
                            "inline_link_clicks": "0",
                        }
                    ],
                    "paging": {},
                },
            )
        if len(calls) == 1:
            return (
                httpx.Response(200, json={"error": {"code": 17, "message": "rate limit"}})
                if False
                else httpx.Response(429, headers={"Retry-After": "0"})
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "ad_id": "1",
                        "date_start": "2026-09-06",
                        "spend": "1",
                        "impressions": "1",
                        "clicks": "0",
                        "inline_link_clicks": "0",
                    }
                ],
                "paging": {"next": "https://graph.facebook.com/vX/act_1/insights?after=abc&access_token=t"},
            },
        )

    a = MetaAdapter(
        "t",
        "vX",
        http=RetryingClient(
            client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda s: None
        ),
    )
    env = a.sync(
        SyncRequest(
            stream="insights_daily", account_id="act_1", date_from=date(2026, 9, 6), date_to=date(2026, 9, 6)
        )
    )
    assert [r["ad_external_id"] for r in env.records] == ["1", "2"] and env.pagination_complete


def test_mcp_arguments_are_never_invented():
    schema = {
        "type": "object",
        "properties": {"date_from": {"type": "string"}, "sklep": {"type": "string"}},
        "required": ["date_from", "sklep", "token"],
    }
    kept, missing = filter_arguments(
        schema, {"date_from": "2026-09-01", "date_to": "2026-09-06", "shop": "veluskin"}
    )
    assert kept == {"date_from": "2026-09-01"} and missing == ["sklep", "token"]
    args, missing_required, unmapped = build_arguments(
        schema,
        SyncRequest(
            stream="panel_summary",
            account_id="veluskin",
            date_from=date(2026, 9, 1),
            date_to=date(2026, 9, 6),
        ),
        "veluskin",
    )
    assert (
        args == {"date_from": "2026-09-01", "sklep": "veluskin"}
        and missing_required == ["token"]
        and unmapped == ["date_to"]
    )
    assert schema_hash(schema) != schema_hash({**schema, "properties": {}})
