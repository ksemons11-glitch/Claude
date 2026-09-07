"""Get Hooked competitor-creative source. Either an MCP connector (discovered live) or a
manual JSON/CSV import. Without either, the module reports UNAVAILABLE and the market
scan produces no fictitious trends."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.adapters.mcp_client import MCPClient, filter_arguments
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind

REQUIRED = ("external_id", "brand")


def normalize_market_rows(
    rows: list[dict[str, Any]], *, source_label: str = "gethooked"
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in rows:
        ext = str(r.get("external_id") or r.get("id") or r.get("ad_id") or "")
        brand = str(r.get("brand") or r.get("advertiser") or r.get("page_name") or "")
        if not ext or not brand:
            continue
        media = r.get("media_url") or r.get("video_url") or r.get("image_url") or r.get("media_ref")
        media_hash = hashlib.sha256(str(media).encode()).hexdigest() if media else None
        countries = r.get("countries") or r.get("country") or []
        if isinstance(countries, str):
            countries = [c.strip() for c in countries.split(",") if c.strip()]
        out.append(
            {
                "external_id": ext,
                "brand": brand,
                "media_ref": media,
                "media_hash": media_hash,
                "first_seen": str(r.get("first_seen") or r.get("start_date") or "")[:10] or None,
                "last_seen": str(r.get("last_seen") or r.get("end_date") or r.get("observed_at") or "")[:10]
                or None,
                "countries": countries,
                "transcript": r.get("transcript"),
                "hook": r.get("hook"),
                "format": r.get("format"),
                "taxonomy": {
                    k: r.get(k)
                    for k in ("angle", "problem", "mechanism", "concept_hint", "offer")
                    if r.get(k)
                },
                "_date": (
                    str(r.get("last_seen") or r.get("observed_at") or datetime.now(UTC).date().isoformat())[
                        :10
                    ]
                ),
                "_source": source_label,
            }
        )
    return out


class ManualImportAdapter:
    source = SourceKind.GETHOOKED
    streams = ("market_ads",)

    def __init__(self, import_dir: Path):
        self.import_dir = import_dir

    def discover_capabilities(self) -> list[Capability]:
        return [Capability("manual_import", f"JSON/CSV files in {self.import_dir}", {}, True)]

    def healthcheck(self) -> HealthResult:
        files = (
            list(self.import_dir.glob("*.json")) + list(self.import_dir.glob("*.csv"))
            if self.import_dir.exists()
            else []
        )
        if not files:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, "no import files present")
        return HealthResult(self.source, DataStatus.OK, f"{len(files)} import files")

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        return normalize_market_rows(
            raw if isinstance(raw, list) else raw.get("ads", []), source_label="manual_import"
        )

    def sync(self, request: SyncRequest) -> DataEnvelope:
        rows: list[dict[str, Any]] = []
        files = sorted(self.import_dir.glob("*")) if self.import_dir.exists() else []
        for f in files:
            if f.suffix == ".json":
                data = json.loads(f.read_text(encoding="utf-8"))
                rows.extend(data if isinstance(data, list) else data.get("ads", []))
            elif f.suffix == ".csv":
                rows.extend(list(csv.DictReader(io.StringIO(f.read_text(encoding="utf-8")))))
        status = DataStatus.OK if files else DataStatus.UNAVAILABLE
        records = self.normalize(rows)
        return DataEnvelope(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            status=status,
            records=records,
            warnings=[] if files else ["no manual import files"],
            request_signature=request.signature(),
        )


class GetHookedMCPAdapter:
    source = SourceKind.GETHOOKED
    streams = ("market_ads",)

    def __init__(self, client: MCPClient, brands: list[str]):
        self.client = client
        self.brands = brands
        self._caps: list[Capability] | None = None

    def discover_capabilities(self) -> list[Capability]:
        caps, _ = self.client.list_tools()
        self._caps = caps
        return caps

    def healthcheck(self) -> HealthResult:
        try:
            caps = self.discover_capabilities()
        except Exception as exc:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, str(exc))
        return HealthResult(
            self.source, DataStatus.OK if caps else DataStatus.NOT_SUPPORTED, f"{len(caps)} tools"
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        rows = raw if isinstance(raw, list) else (raw or {}).get("ads") or (raw or {}).get("results") or []
        return normalize_market_rows(rows)

    def sync(self, request: SyncRequest) -> DataEnvelope:
        caps = self._caps if self._caps is not None else self.discover_capabilities()
        search = next(
            (c for c in caps if "search" in c.tool_name.lower() and "ad" in c.tool_name.lower()), None
        )
        base = dict(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            request_signature=request.signature(),
        )
        if search is None:
            return DataEnvelope(
                **base,
                status=DataStatus.NOT_SUPPORTED,
                warnings=[f"no ad-search tool discovered; tools: {[c.tool_name for c in caps]}"],
            )
        records: list[dict[str, Any]] = []
        warnings: list[str] = []
        for brand in self.brands:
            args, missing = filter_arguments(
                search.input_schema,
                {"brand": brand, "query": brand, "advertiser": brand, "country": "PL", "geo": "PL"},
            )
            if missing:
                warnings.append(
                    f"{search.tool_name} requires {missing}; cannot call without inventing arguments"
                )
                break
            call = self.client.call_tool(search.tool_name, args)
            if call.is_error:
                warnings.append(f"{brand}: tool error {call.text[:200]}")
                continue
            records.extend(self.normalize(call.as_json()))
        status = DataStatus.OK if records or not warnings else DataStatus.PARTIAL
        return DataEnvelope(
            **base, status=status, records=records, warnings=warnings, schema_version=search.tool_name
        )


def as_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None
