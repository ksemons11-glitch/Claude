from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from director.contracts.reasoning import ReportStatus


class ShopRow(BaseModel):
    shop_key: str
    name: str
    orders: str | None
    revenue_ordered: str | None
    spend: str | None
    expected_result_after_ads: str | None
    expected_low: str | None = None
    expected_high: str | None = None
    mer_ordered: str | None
    mer_label: str
    roas_meta: str | None
    cpa_attributed: str | None
    coverage_ad_orders: str | None
    uncertainty: str
    status: str
    missing: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)


class ActionItem(BaseModel):
    rank: int
    entity_ref: str
    action_type: str
    fact: str
    hypothesis: str
    confidence: str
    evidence_score: int | None
    evidence_refs: list[str]
    blocking_gates: list[str]
    impact: str
    urgency: str
    effort: str
    alternative: str
    conditions: list[str] = Field(default_factory=list)
    next_check_after_hours: int
    execution_allowed: bool = False
    recommendation_id: str | None = None


class DailyReportBody(BaseModel):
    business_date: date
    as_of: datetime
    completeness: str
    status: ReportStatus
    headline: dict[str, Any]
    facts: list[str]
    shops: list[ShopRow]
    diagnosis: list[dict[str, Any]]
    actions: list[ActionItem]
    do_not_touch: list[str]
    next_review: str
    missing: list[str]
    cashflow: dict[str, Any]
    definitions_version: str
    llm: dict[str, Any]
    revision: int = 1
    revision_reason: str | None = None


class WeeklyReportBody(BaseModel):
    period_start: date
    period_end: date
    as_of: datetime
    completeness: str
    maturity_note: str
    shops: list[dict[str, Any]]
    concepts: dict[str, Any]
    decisions: list[dict[str, Any]]
    experiments: list[dict[str, Any]]
    constraints: list[str]
    plan_7d: list[dict[str, Any]]
    missing: list[str]
