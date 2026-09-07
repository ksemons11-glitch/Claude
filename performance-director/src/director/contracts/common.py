from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

MONEY_Q = Decimal("0.000001")
PRESENT_Q = Decimal("0.01")


def money(value: Decimal | int | str | float | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, float):
        value = repr(value)
    return Decimal(str(value)).quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def present(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(PRESENT_Q, rounding=ROUND_HALF_UP)


class DataStatus(StrEnum):
    OK = "OK"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    UNCONFIGURED = "UNCONFIGURED"


class Severity(StrEnum):
    INFO = "INFO"
    WATCH = "WATCH"
    CRITICAL = "CRITICAL"


class ConfidenceClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MetricValue(BaseModel):
    """A metric with an explicit reason whenever it cannot be computed.

    Never encode 'unknown' as 0. `value is None` and `reason` explains why
    (ZERO_DENOMINATOR, MISSING_COSTS, NO_DATA, INCOMPATIBLE_WINDOWS ...).
    """

    metric: str
    value: Decimal | None = None
    numerator: Decimal | None = None
    denominator: Decimal | None = None
    reason: str | None = None
    unit: str = ""
    window: str = ""
    definition_version: str = "1"
    flags: list[str] = Field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.value is not None

    def __str__(self) -> str:  # pragma: no cover - convenience
        return f"{self.metric}={self.value if self.value is not None else 'n/a(' + str(self.reason) + ')'}"
