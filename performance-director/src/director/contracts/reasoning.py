from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from director.contracts.common import ConfidenceClass
from director.contracts.rules import RuleResult


class ActionType(StrEnum):
    HOLD = "HOLD"
    WATCH = "WATCH"
    DIAGNOSE = "DIAGNOSE"
    INVESTIGATE_DATA = "INVESTIGATE_DATA"
    PAUSE_TEST = "PAUSE_TEST"
    PROPOSE_BUDGET_INCREASE = "PROPOSE_BUDGET_INCREASE"
    PROPOSE_BUDGET_DECREASE = "PROPOSE_BUDGET_DECREASE"
    NEW_CREATIVE_TEST = "NEW_CREATIVE_TEST"
    BACKLOG_CONCEPT = "BACKLOG_CONCEPT"
    FIX_INTEGRATION = "FIX_INTEGRATION"
    REVIEW_OFFER = "REVIEW_OFFER"


class ReportStatus(StrEnum):
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    DATA_ISSUE = "DATA_ISSUE"
    FAILED = "FAILED"


class EvidenceBundle(BaseModel):
    business_date: date
    as_of: datetime
    scope: str
    definitions_version: str = "1"
    quality: dict[str, Any] = Field(default_factory=dict)
    metric_refs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    rule_results: list[RuleResult] = Field(default_factory=list)
    recent_changes: list[dict[str, Any]] = Field(default_factory=list)
    active_experiments: list[dict[str, Any]] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    past_decisions: list[dict[str, Any]] = Field(default_factory=list)
    market_refs: list[dict[str, Any]] = Field(default_factory=list)
    allowed_entity_refs: list[str] = Field(default_factory=list)

    def all_refs(self) -> set[str]:
        refs: set[str] = set(self.metric_refs.keys())
        for r in self.rule_results:
            refs.add(f"rule:{r.rule_id}:{r.entity_ref}")
            refs.update(r.evidence_refs)
        return refs


class LLMRecommendation(BaseModel):
    entity_ref: str
    action_type: ActionType
    fact_refs: list[str] = Field(default_factory=list)
    hypothesis: str = ""
    confidence: ConfidenceClass = ConfidenceClass.LOW
    blocking_gates: list[str] = Field(default_factory=list)
    impact: str = "LOW"
    urgency: str = "LOW"
    effort: str = "LOW"
    next_check_after_hours: int = 24
    execution_allowed: bool = False  # ALWAYS overwritten by the policy engine
    alternative: str = "Bez zmian"
    conditions: list[str] = Field(default_factory=list)

    @field_validator("impact", "urgency", "effort")
    @classmethod
    def _lvl(cls, v: str) -> str:
        v = v.upper()
        if v not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValueError("level must be LOW/MEDIUM/HIGH")
        return v


class LLMResponse(BaseModel):
    schema_version: str = "1"
    business_date: date
    status: ReportStatus
    summary: str = ""
    facts: list[str] = Field(default_factory=list)
    do_not_touch: list[str] = Field(default_factory=list)
    recommendations: list[LLMRecommendation] = Field(default_factory=list)
