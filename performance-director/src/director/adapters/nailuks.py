"""Nailuks panel via MCP. Tool names `nailuks_dane` / `nailuks_meta_ads` are *hints* from the
historical notes: real names and schemas are discovered live and recorded in connector_capabilities.
Arguments are filtered against the discovered input schema - nothing is invented.

Aggregates from the panel are used to cross-check sums, never to attribute revenue to
individual ads unless the tool actually returns ad-level rows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.adapters.mcp_client import MCPClient, filter_arguments
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind

TOOL_HINTS = {
    "panel_summary": ("nailuks_dane", "dane", "summary", "orders"),
    "panel_ads": ("nailuks_meta_ads", "meta_ads", "ads"),
}
DATE_ARG_CANDIDATES = {
    "date_from": ("date_from", "from", "start_date", "od", "start"),
    "date_to": ("date_to", "to", "end_date", "do", "end"),
    "shop": ("shop", "shop_id", "store", "sklep", "account"),
}


def pick_tool(caps: list[Capability], stream: str) -> Capability | None:
    hints = TOOL_HINTS.get(stream, ())
    for h in hints:
        for c in caps:
            if c.tool_name == h:
                return c
    for h in hints:
        for c in caps:
            if h in c.tool_name.lower():
                return c
    return None


def build_arguments(
    schema: dict[str, Any], request: SyncRequest, shop_ref: str | None
) -> tuple[dict[str, Any], list[str], list[str]]:
    props = (schema or {}).get("properties") or {}
    candidates: dict[str, Any] = {}
    unmapped: list[str] = []
    for logical, names in DATE_ARG_CANDIDATES.items():
        value: Any = None
        if logical == "date_from" and request.date_from:
            value = request.date_from.isoformat()
        elif logical == "date_to" and request.date_to:
            value = request.date_to.isoformat()
        elif logical == "shop":
            value = shop_ref
        if value is None:
            continue
        hit = next((n for n in names if n in props), None)
        if hit:
            candidates[hit] = value
        else:
            unmapped.append(logical)
    args, missing_required = filter_arguments(schema, candidates)
    return args, missing_required, unmapped


def normalize_panel(rows: Any, stream: str) -> list[dict[str, Any]]:
    """Accept a list of dict rows or {"rows"/"data": [...]}; keep fields verbatim plus `_date`."""
    if isinstance(rows, dict):
        for key in ("rows", "data", "items", "results"):
            if isinstance(rows.get(key), list):
                rows = rows[key]
                break
        else:
            rows = [rows]
    out: list[dict[str, Any]] = []
    for r in rows if isinstance(rows, list) else []:
        if not isinstance(r, dict):
            continue
        d = r.get("date") or r.get("day") or r.get("data") or r.get("dzien")
        rec = dict(r)
        rec["_stream"] = stream
        rec["_date"] = str(d)[:10] if d else None
        out.append(rec)
    return out


class NailuksAdapter:
    source = SourceKind.NAILUKS
    streams = ("panel_summary", "panel_ads")

    def __init__(self, client: MCPClient, *, shop_refs: dict[str, str] | None = None):
        self.client = client
        self.shop_refs = shop_refs or {}
        self._caps: list[Capability] | None = None
        self.discovery_info: dict[str, Any] = {}

    def discover_capabilities(self) -> list[Capability]:
        caps, info = self.client.list_tools()
        self._caps = caps
        self.discovery_info = info
        return caps

    def healthcheck(self) -> HealthResult:
        started = datetime.now(UTC)
        try:
            caps = self.discover_capabilities()
        except Exception as exc:
            return HealthResult(self.source, DataStatus.UNAVAILABLE, str(exc))
        if not caps:
            return HealthResult(self.source, DataStatus.NOT_SUPPORTED, "server exposes no tools")
        return HealthResult(
            self.source,
            DataStatus.OK,
            f"{len(caps)} tools",
            (datetime.now(UTC) - started).total_seconds() * 1000,
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        return normalize_panel(raw, "panel_summary")

    def sync(self, request: SyncRequest) -> DataEnvelope:
        caps = self._caps if self._caps is not None else self.discover_capabilities()
        tool = pick_tool(caps, request.stream)
        base = dict(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            requested_range=(request.date_from, request.date_to)
            if request.date_from and request.date_to
            else None,
            request_signature=request.signature(),
        )
        if tool is None:
            return DataEnvelope(
                **base,
                status=DataStatus.NOT_SUPPORTED,
                warnings=[
                    f"no MCP tool matches stream {request.stream}; tools: {[c.tool_name for c in caps]}"
                ],
            )
        args, missing_required, unmapped = build_arguments(
            tool.input_schema, request, self.shop_refs.get(request.account_id)
        )
        if missing_required:
            return DataEnvelope(
                **base,
                status=DataStatus.NOT_SUPPORTED,
                warnings=[
                    f"tool {tool.tool_name} requires {missing_required}; schema not recognized - map manually in SETUP_REQUIRED.md"
                ],
            )
        call = self.client.call_tool(tool.tool_name, args)
        if call.is_error:
            return DataEnvelope(
                **base, status=DataStatus.UNAVAILABLE, warnings=[f"tool error: {call.text[:300]}"]
            )
        records = normalize_panel(call.as_json(), request.stream)
        warnings = [f"unmapped request dimensions: {unmapped}"] if unmapped else []
        dates = sorted({r["_date"] for r in records if r.get("_date")})
        return DataEnvelope(
            **base,
            records=records,
            warnings=warnings,
            returned_range=(date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])) if dates else None,
            schema_version=tool.tool_name,
        )
