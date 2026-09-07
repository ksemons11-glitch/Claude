from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from director.contracts.common import ConfidenceClass, Severity


class Gate(BaseModel):
    code: str
    passed: bool
    detail: str = ""


class RuleResult(BaseModel):
    rule_id: str
    rule_version: str = "1"
    entity_ref: str  # e.g. shop:veluskin, ad:123, creative:abc
    business_date: date
    metric_window: str
    baseline: dict[str, Any] = Field(default_factory=dict)
    observed: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    severity: Severity = Severity.INFO
    fact: str = ""
    hypothesis: str = ""
    missing_data: list[str] = Field(default_factory=list)
    candidate_action: str = "HOLD"
    blocking_gates: list[str] = Field(default_factory=list)
    gates: list[Gate] = Field(default_factory=list)
    confidence: ConfidenceClass = ConfidenceClass.LOW
    confidence_components: dict[str, str] = Field(default_factory=dict)
    evidence_score: int | None = None  # "heuristic evidence quality", never a probability
    priority_class: str = "EXPLORATION"  # FAILURE_LOSS | RISK | PROFIT | EXPLORATION
    impact: str = "LOW"
    urgency: str = "LOW"
    effort: str = "LOW"

    @property
    def executable(self) -> bool:
        return not self.blocking_gates
