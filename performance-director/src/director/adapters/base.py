"""Adapter protocol shared by every source (live, fixture, unconfigured)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

from director.contracts.common import DataStatus
from director.contracts.envelope import DataEnvelope, SourceKind


@dataclass(frozen=True)
class SyncRequest:
    stream: str
    account_id: str
    date_from: date | None = None
    date_to: date | None = None
    cursor: str | None = None
    params: dict[str, Any] = field(default_factory=dict)

    def signature(self) -> dict[str, Any]:
        return {
            "stream": self.stream,
            "account_id": self.account_id,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "cursor": self.cursor,
            "params": self.params,
        }


@dataclass
class Capability:
    tool_name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    read_only_hint: bool | None = None


@dataclass
class HealthResult:
    source: SourceKind
    status: DataStatus
    detail: str = ""
    latency_ms: float | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Adapter(Protocol):
    source: SourceKind
    streams: tuple[str, ...]

    def discover_capabilities(self) -> list[Capability]: ...

    def healthcheck(self) -> HealthResult: ...

    def sync(self, request: SyncRequest) -> DataEnvelope: ...

    def normalize(self, raw: Any) -> list[dict[str, Any]]: ...


class UnconfiguredAdapter:
    """Stands in for a source without credentials. Every call answers UNCONFIGURED, never zeros."""

    def __init__(self, source: SourceKind, streams: tuple[str, ...], reason: str = "missing credentials"):
        self.source = source
        self.streams = streams
        self.reason = reason

    def discover_capabilities(self) -> list[Capability]:
        return []

    def healthcheck(self) -> HealthResult:
        return HealthResult(self.source, DataStatus.UNCONFIGURED, self.reason)

    def sync(self, request: SyncRequest) -> DataEnvelope:
        return DataEnvelope(
            source=self.source,
            stream=request.stream,
            account_id=request.account_id,
            fetched_at_utc=datetime.now(UTC),
            requested_range=(request.date_from, request.date_to)
            if request.date_from and request.date_to
            else None,
            status=DataStatus.UNCONFIGURED,
            warnings=[f"{self.source}: {self.reason}"],
            request_signature=request.signature(),
        )

    def normalize(self, raw: Any) -> list[dict[str, Any]]:
        return []
