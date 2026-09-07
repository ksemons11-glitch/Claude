"""Fixture adapters replay raw API-shaped payloads from disk through the *same* normalizers
used for live data, so fixture mode exercises the real normalization path.

Layout: <fixture_dir>/<source>/<account_id>/<stream>.json
  {"meta": {"timezone": "...", "currency": "...", "status": "OK"}, "pages": [<raw page>, ...]}
A missing file yields status MISSING (never an empty OK)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from director.adapters.base import Capability, HealthResult, SyncRequest
from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind

Normalizer = Callable[[dict[str, Any], str], list[dict[str, Any]]]


class FixtureAdapter:
    def __init__(
        self,
        source: SourceKind,
        streams: tuple[str, ...],
        fixture_dir: Path,
        normalizers: dict[str, Normalizer],
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.source = source
        self.streams = streams
        self.fixture_dir = fixture_dir
        self.normalizers = normalizers
        self.clock = clock or (lambda: datetime.now(UTC))
        self.calls: list[SyncRequest] = []
        self.fail_streams: set[str] = set()  # tests: simulate a source outage for these streams

    def _path(self, account_id: str, stream: str, variant: str | None = None) -> Path:
        name = f"{stream}.{variant}.json" if variant else f"{stream}.json"
        return self.fixture_dir / self.source.value / account_id / name

    def discover_capabilities(self) -> list[Capability]:
        return [Capability(f"fixture:{s}", "replayed fixture", {}, True) for s in self.streams]

    def healthcheck(self) -> HealthResult:
        root = self.fixture_dir / self.source.value
        if not root.exists():
            return HealthResult(self.source, DataStatus.MISSING, f"no fixtures under {root}")
        return HealthResult(self.source, DataStatus.OK, "fixture", 0.0)

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        stream = self.streams[0]
        return self.normalizers[stream](raw, stream)

    def sync(self, request: SyncRequest) -> DataEnvelope:
        self.calls.append(request)
        path = self._path(request.account_id, request.stream, request.params.get("variant"))
        base = dict(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=self.clock(),
            requested_range=(request.date_from, request.date_to)
            if request.date_from and request.date_to
            else None,
            request_signature=request.signature(),
        )
        if request.stream in self.fail_streams:
            return DataEnvelope(**base, status=DataStatus.UNAVAILABLE, warnings=["simulated outage"])
        if not path.exists():
            return DataEnvelope(**base, status=DataStatus.MISSING, warnings=[f"fixture missing: {path}"])
        doc = json.loads(path.read_text(encoding="utf-8"))
        meta = doc.get("meta", {})
        status = DataStatus(meta.get("status", "OK"))
        if status not in (DataStatus.OK, DataStatus.PARTIAL):
            return DataEnvelope(
                **base,
                status=status,
                warnings=meta.get("warnings", []),
                timezone=meta.get("timezone"),
                currency=meta.get("currency"),
            )
        normalizer = self.normalizers.get(request.stream)
        records: list[dict[str, Any]] = []
        for page in doc.get("pages", []):
            records.extend(normalizer(page, request.stream) if normalizer else page.get("records", []))
        if request.date_from and request.date_to:
            lo, hi = request.date_from.isoformat(), request.date_to.isoformat()
            records = [r for r in records if r.get("_date") is None or lo <= r["_date"] <= hi]
        if request.params.get("order_ids"):
            wanted = set(map(str, request.params["order_ids"]))
            records = [r for r in records if str(r.get("external_order_id")) in wanted]
        dates = sorted({r["_date"] for r in records if r.get("_date")})
        source_updated = meta.get("source_updated_at")
        return DataEnvelope(
            **base,
            status=status,
            records=records,
            warnings=list(meta.get("warnings", [])),
            timezone=meta.get("timezone"),
            currency=meta.get("currency"),
            pagination_complete=bool(meta.get("pagination_complete", True)),
            source_updated_at=datetime.fromisoformat(source_updated) if source_updated else None,
            returned_range=(date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])) if dates else None,
        )
