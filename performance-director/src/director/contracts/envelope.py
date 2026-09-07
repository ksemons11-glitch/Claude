from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from director.contracts.common import DataStatus


class SourceKind(StrEnum):
    META = "meta"
    BASELINKER = "baselinker"
    NAILUKS = "nailuks"
    GETHOOKED = "gethooked"
    STORE_HEALTH = "store_health"
    FIXTURE = "fixture"


class DataEnvelope(BaseModel):
    """Uniform wrapper for every adapter response.

    An empty `records` list with status OK means "source answered, zero rows".
    A missing/unavailable source must set `status` accordingly; consumers must
    never interpret it as zero sales.
    """

    source: SourceKind
    stream: str
    account_id: str
    fetched_at_utc: datetime
    source_updated_at: datetime | None = None
    requested_range: tuple[date, date] | None = None
    returned_range: tuple[date, date] | None = None
    timezone: str | None = None
    currency: str | None = None
    pagination_complete: bool = True
    schema_version: str = "1"
    status: DataStatus = DataStatus.OK
    records: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_batch_id: str | None = None
    request_signature: dict[str, Any] = Field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in (DataStatus.OK, DataStatus.PARTIAL) and self.pagination_complete
