"""Safe read-only availability checks for shop pages. Never places orders or posts forms."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import httpx

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind


class StoreHealthAdapter:
    source = SourceKind.STORE_HEALTH
    streams = ("health",)

    def __init__(
        self,
        urls_by_shop: dict[str, list[str]],
        *,
        client: httpx.Client | None = None,
        expect_text: dict[str, str] | None = None,
    ):
        self.urls_by_shop = urls_by_shop
        self.client = client or httpx.Client(
            timeout=15, follow_redirects=True, headers={"User-Agent": "performance-director-healthcheck/1.0"}
        )
        self.expect_text = expect_text or {}

    def discover_capabilities(self) -> list[Capability]:
        return [Capability("GET", "HTTP GET status/content/latency", {}, True)]

    def healthcheck(self) -> HealthResult:
        return HealthResult(
            self.source, DataStatus.OK, f"{sum(len(v) for v in self.urls_by_shop.values())} urls configured"
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        return list(raw)

    def check_url(self, url: str) -> dict[str, Any]:
        started = time.monotonic()
        try:
            resp = self.client.get(url)
            latency = (time.monotonic() - started) * 1000
            ok_text = self.expect_text.get(url)
            content_ok = (ok_text in resp.text) if ok_text else True
            return {
                "url": url,
                "status_code": resp.status_code,
                "latency_ms": round(latency, 1),
                "ok": 200 <= resp.status_code < 400 and content_ok,
                "content_ok": content_ok,
                "error": None,
            }
        except httpx.HTTPError as exc:
            return {
                "url": url,
                "status_code": None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "ok": False,
                "content_ok": False,
                "error": str(exc)[:200],
            }

    def sync(self, request: SyncRequest) -> DataEnvelope:
        urls = self.urls_by_shop.get(request.account_id, [])
        records = [self.check_url(u) for u in urls]
        return DataEnvelope(
            source=self.source,
            stream="health",
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            status=DataStatus.OK if urls else DataStatus.UNCONFIGURED,
            records=records,
            warnings=[] if urls else ["no health urls configured"],
            request_signature=request.signature(),
        )
