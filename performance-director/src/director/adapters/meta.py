"""Meta Marketing API connector (Graph API). Read-only endpoints only.

Contract written from the public Marketing API documentation; verify field names and
the API version against the live account during setup. Budgets arrive in minor units
(e.g. grosze) as strings and are converted to major units here.

Rules enforced here:
- link clicks (`inline_link_clicks`) and outbound clicks are fetched explicitly; never mixed with `clicks`.
- `reach`/`frequency` are only meaningful for the requested window; we store them on
  window-level rows (stream `insights_window`) and never sum them across days.
- attribution windows and action_report_time are part of the row identity.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.adapters.http import RetryingClient
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind
from director.jobs.worker import PermanentError, RetryableError

DEFAULT_ATTRIBUTION = ["7d_click", "1d_view"]
INSIGHT_FIELDS = [
    "ad_id",
    "ad_name",
    "adset_id",
    "adset_name",
    "campaign_id",
    "campaign_name",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "inline_link_clicks",
    "outbound_clicks",
    "actions",
    "action_values",
    "date_start",
    "date_stop",
]
PURCHASE_TYPES = ("purchase", "omni_purchase", "offsite_conversion.fb_pixel_purchase")
MAX_PAGES = 500


def _minor_to_major(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return (Decimal(str(value)) / Decimal(100)).quantize(Decimal("0.000001"))


def _action(actions: list[dict[str, Any]] | None, types: tuple[str, ...]) -> Decimal | None:
    if not actions:
        return None
    by_type = {a.get("action_type"): a for a in actions}
    for t in types:
        if t in by_type:
            return Decimal(str(by_type[t].get("value", "0")))
    return None


def normalize_insights(
    payload: dict[str, Any], *, attribution: list[str], action_report_time: str, hourly: bool = False
) -> list[dict[str, Any]]:
    attribution_key = "+".join(attribution) + "|" + action_report_time
    out: list[dict[str, Any]] = []
    for row in payload.get("data", []) or []:
        actions = row.get("actions") or []
        action_values = row.get("action_values") or []
        purchases = _action(actions, PURCHASE_TYPES)
        outbound = _action(row.get("outbound_clicks") or [], ("outbound_click",))
        hour = -1
        if hourly and row.get("hourly_stats_aggregated_by_advertiser_time_zone"):
            hour = int(str(row["hourly_stats_aggregated_by_advertiser_time_zone"]).split(":")[0])
        out.append(
            {
                "ad_external_id": str(row["ad_id"]),
                "ad_name": row.get("ad_name"),
                "adset_external_id": str(row.get("adset_id", "")),
                "campaign_external_id": str(row.get("campaign_id", "")),
                "date": row["date_start"],
                "date_stop": row.get("date_stop"),
                "hour": hour,
                "attribution_key": attribution_key,
                "action_report_time": action_report_time,
                "spend": str(Decimal(str(row.get("spend", "0") or "0"))),
                "impressions": int(row.get("impressions", 0) or 0),
                "reach": int(row["reach"]) if row.get("reach") not in (None, "") else None,
                "frequency": str(row["frequency"]) if row.get("frequency") not in (None, "") else None,
                "clicks_all": int(row.get("clicks", 0) or 0),
                "link_clicks": int(row.get("inline_link_clicks", 0) or 0),
                "outbound_clicks": int(outbound) if outbound is not None else None,
                "landing_page_views": int(_action(actions, ("landing_page_view",)) or 0)
                if _action(actions, ("landing_page_view",)) is not None
                else None,
                "add_to_cart": int(_action(actions, ("add_to_cart", "omni_add_to_cart")) or 0)
                if _action(actions, ("add_to_cart", "omni_add_to_cart")) is not None
                else None,
                "initiate_checkout": int(
                    _action(actions, ("initiate_checkout", "omni_initiated_checkout")) or 0
                )
                if _action(actions, ("initiate_checkout", "omni_initiated_checkout")) is not None
                else None,
                "purchases": int(purchases) if purchases is not None else 0,
                "purchase_value": str(_action(action_values, PURCHASE_TYPES) or Decimal("0")),
                "actions_raw": actions,
                "_date": row["date_start"],
            }
        )
    return out


def _asset_hash(creative: dict[str, Any]) -> str | None:
    keys = {
        k: creative.get(k)
        for k in ("video_id", "image_hash", "effective_object_story_id", "object_story_id")
        if creative.get(k)
    }
    if not keys:
        return None
    return hashlib.sha256(json.dumps(keys, sort_keys=True).encode()).hexdigest()


def normalize_structure(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """payload = {"campaigns": [...], "adsets": [...], "ads": [...]} (raw Graph rows)."""
    out: list[dict[str, Any]] = []
    for c in payload.get("campaigns", []) or []:
        budget_type = "CBO" if (c.get("daily_budget") or c.get("lifetime_budget")) else "ABO"
        out.append(
            {
                "kind": "campaign",
                "external_id": str(c["id"]),
                "name": c.get("name", ""),
                "objective": c.get("objective"),
                "configured_status": c.get("status"),
                "effective_status": c.get("effective_status"),
                "daily_budget": str(_minor_to_major(c.get("daily_budget")))
                if c.get("daily_budget")
                else None,
                "lifetime_budget": str(_minor_to_major(c.get("lifetime_budget")))
                if c.get("lifetime_budget")
                else None,
                "budget_type": budget_type,
                "metadata": {k: c.get(k) for k in ("bid_strategy", "updated_time", "buying_type") if k in c},
            }
        )
    for a in payload.get("adsets", []) or []:
        out.append(
            {
                "kind": "adset",
                "external_id": str(a["id"]),
                "campaign_external_id": str(a.get("campaign_id")),
                "name": a.get("name", ""),
                "configured_status": a.get("status"),
                "effective_status": a.get("effective_status"),
                "daily_budget": str(_minor_to_major(a.get("daily_budget")))
                if a.get("daily_budget")
                else None,
                "lifetime_budget": str(_minor_to_major(a.get("lifetime_budget")))
                if a.get("lifetime_budget")
                else None,
                "targeting": a.get("targeting") or {},
                "metadata": {
                    k: a.get(k) for k in ("optimization_goal", "billing_event", "updated_time") if k in a
                },
            }
        )
    for ad in payload.get("ads", []) or []:
        creative = ad.get("creative") or {}
        out.append(
            {
                "kind": "ad",
                "external_id": str(ad["id"]),
                "adset_external_id": str(ad.get("adset_id")),
                "campaign_external_id": str(ad.get("campaign_id", "")),
                "name": ad.get("name", ""),
                "configured_status": ad.get("status"),
                "effective_status": ad.get("effective_status"),
                "post_id": creative.get("effective_object_story_id") or creative.get("object_story_id"),
                "asset_ids": [
                    str(v)
                    for v in (creative.get("video_id"), creative.get("image_hash"), creative.get("id"))
                    if v
                ],
                "asset_hash": _asset_hash(creative),
                "url_tags": creative.get("url_tags"),
                "destination_url": (creative.get("object_story_spec") or {}).get("link_data", {}).get("link")
                if isinstance(creative.get("object_story_spec"), dict)
                else None,
                "metadata": {"creative_id": creative.get("id"), "updated_time": ad.get("updated_time")},
            }
        )
    return out


class MetaAdapter:
    source = SourceKind.META
    streams = ("account", "structure", "insights_daily", "insights_hourly", "insights_window")

    def __init__(
        self,
        access_token: str,
        api_version: str,
        graph_url: str = "https://graph.facebook.com",
        *,
        http: RetryingClient | None = None,
        attribution: list[str] | None = None,
        action_report_time: str = "conversion",
    ):
        if not access_token:
            raise PermanentError("META_ACCESS_TOKEN missing")
        if not api_version:
            raise PermanentError(
                "META_API_VERSION missing - set it after checking the current Graph API version"
            )
        self.token = access_token
        self.version = api_version
        self.graph = graph_url.rstrip("/")
        self.http = http or RetryingClient(timeout=90)
        self.attribution = attribution or DEFAULT_ATTRIBUTION
        self.action_report_time = action_report_time
        self.last_usage_header: str | None = None

    def _get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self.graph}/{self.version}/{path_or_url.lstrip('/')}"
        )
        params = dict(params or {})
        if "access_token" not in url:
            params["access_token"] = self.token
        # httpx replaces the query string when `params` is given, so a paging `next` URL must be sent untouched
        resp = self.http.request("GET", url, params=params or None)
        self.last_usage_header = resp.headers.get("x-business-use-case-usage") or resp.headers.get(
            "x-ad-account-usage"
        )
        try:
            body = resp.json()
        except ValueError as exc:
            raise RetryableError("Meta returned non-JSON") from exc
        if "error" in body:
            err = body["error"]
            code = err.get("code")
            if code in (190, 10, 200, 294):
                raise PermanentError(f"Meta error {code}: {err.get('message')}")
            if code in (4, 17, 32, 613, 80000, 80004):
                raise RetryableError(f"Meta rate limit {code}: {err.get('message')}", retry_after=300)
            raise RetryableError(f"Meta error {code}: {err.get('message')}")
        return body

    def _paginate(self, path: str, params: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
        rows: list[dict[str, Any]] = []
        body = self._get(path, params)
        for _ in range(MAX_PAGES):
            rows.extend(body.get("data", []) or [])
            nxt = (body.get("paging") or {}).get("next")
            if not nxt:
                return rows, True
            body = self._get(nxt)
        return rows, False

    def discover_capabilities(self) -> list[Capability]:
        return [
            Capability(f"GET /{self.version}/act_{{id}}/{p}", d, {}, True)
            for p, d in (
                ("insights", "ad-level insights"),
                ("campaigns", "campaign structure"),
                ("adsets", "adset structure"),
                ("ads", "ad structure + creative"),
            )
        ]

    def healthcheck(self) -> HealthResult:
        started = datetime.now(UTC)
        try:
            self._get("me", {"fields": "id"})
        except (PermanentError, RetryableError) as exc:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, str(exc))
        return HealthResult(
            self.source, DataStatus.OK, "ok", (datetime.now(UTC) - started).total_seconds() * 1000
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        if isinstance(raw, dict) and "campaigns" in raw:
            return normalize_structure(raw)
        return normalize_insights(
            raw, attribution=self.attribution, action_report_time=self.action_report_time
        )

    def _envelope(
        self,
        request: SyncRequest,
        records: list[dict[str, Any]],
        *,
        complete: bool,
        warnings: list[str],
        tz: str | None,
        currency: str | None,
    ) -> DataEnvelope:
        dates = sorted({r.get("_date") for r in records if r.get("_date")})
        return DataEnvelope(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            requested_range=(request.date_from, request.date_to)
            if request.date_from and request.date_to
            else None,
            returned_range=(date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])) if dates else None,
            timezone=tz,
            currency=currency,
            pagination_complete=complete,
            records=records,
            warnings=warnings,
            request_signature={
                **request.signature(),
                "attribution": self.attribution,
                "action_report_time": self.action_report_time,
                "usage": self.last_usage_header,
            },
        )

    def account_info(self, account_id: str) -> dict[str, Any]:
        return self._get(account_id, {"fields": "name,currency,timezone_name,account_status"})

    def sync(self, request: SyncRequest) -> DataEnvelope:
        acct = request.account_id
        if request.stream == "account":
            info = self.account_info(acct)
            rec = {
                "external_id": acct,
                "name": info.get("name"),
                "currency": info.get("currency"),
                "timezone": info.get("timezone_name"),
                "account_status": info.get("account_status"),
            }
            return self._envelope(
                request,
                [rec],
                complete=True,
                warnings=[],
                tz=info.get("timezone_name"),
                currency=info.get("currency"),
            )
        if request.stream == "structure":
            camps, c1 = self._paginate(
                f"{acct}/campaigns",
                {
                    "fields": "id,name,objective,status,effective_status,daily_budget,lifetime_budget,bid_strategy,buying_type,updated_time",
                    "limit": 200,
                },
            )
            adsets, c2 = self._paginate(
                f"{acct}/adsets",
                {
                    "fields": "id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,targeting,optimization_goal,billing_event,updated_time",
                    "limit": 200,
                },
            )
            ads, c3 = self._paginate(
                f"{acct}/ads",
                {
                    "fields": "id,name,adset_id,campaign_id,status,effective_status,updated_time,creative{id,effective_object_story_id,object_story_id,url_tags,video_id,image_hash,object_story_spec}",
                    "limit": 200,
                },
            )
            recs = normalize_structure({"campaigns": camps, "adsets": adsets, "ads": ads})
            return self._envelope(
                request, recs, complete=c1 and c2 and c3, warnings=[], tz=None, currency=None
            )
        if request.stream in ("insights_daily", "insights_hourly", "insights_window"):
            if not (request.date_from and request.date_to):
                raise PermanentError("insights require a date range")
            params: dict[str, Any] = {
                "level": "ad",
                "fields": ",".join(INSIGHT_FIELDS),
                "limit": 500,
                "time_range": json.dumps(
                    {"since": request.date_from.isoformat(), "until": request.date_to.isoformat()}
                ),
                "action_attribution_windows": json.dumps(self.attribution),
                "action_report_time": self.action_report_time,
                "use_unified_attribution_setting": "true",
            }
            hourly = request.stream == "insights_hourly"
            if request.stream == "insights_daily":
                params["time_increment"] = 1
            elif hourly:
                params["time_increment"] = 1
                params["breakdowns"] = "hourly_stats_aggregated_by_advertiser_time_zone"
            rows, complete = self._paginate(f"{acct}/insights", params)
            recs = normalize_insights(
                {"data": rows},
                attribution=self.attribution,
                action_report_time=self.action_report_time,
                hourly=hourly,
            )
            if request.stream == "insights_window":
                for r in recs:
                    r["window"] = [request.date_from.isoformat(), request.date_to.isoformat()]
            return self._envelope(
                request,
                recs,
                complete=complete,
                warnings=[] if complete else ["pagination stopped early"],
                tz=None,
                currency=None,
            )
        raise PermanentError(f"unknown Meta stream {request.stream}")


def chunk_ranges(start: date, end: date, days: int = 7) -> list[tuple[date, date]]:
    out: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        stop = min(end, cur + timedelta(days=days - 1))
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out
