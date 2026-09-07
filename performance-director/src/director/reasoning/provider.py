"""ReasoningProvider interface + FakeProvider (tests/demo). The Anthropic provider lives in anthropic_provider.py."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from director.contracts.reasoning import EvidenceBundle


@dataclass
class Budget:
    max_input_tokens: int = 60_000
    max_output_tokens: int = 2_000
    max_evidence_items: int = 120


@dataclass
class ProviderResult:
    raw: dict[str, Any] | None
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class ReasoningProvider(Protocol):
    name: str

    def generate(
        self,
        bundle: EvidenceBundle,
        schema: dict[str, Any],
        budget: Budget,
        *,
        repair_errors: list[str] | None = None,
        previous: str | None = None,
    ) -> ProviderResult: ...


class FakeProvider:
    """Deterministic provider: echoes rule results into the contract. `script` can inject a canned reply (e.g. hallucinations for tests)."""

    name = "fake"

    def __init__(self, script: list[dict[str, Any]] | None = None, model: str = "fake-1"):
        self.script = list(script or [])
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        bundle: EvidenceBundle,
        schema: dict[str, Any],
        budget: Budget,
        *,
        repair_errors: list[str] | None = None,
        previous: str | None = None,
    ) -> ProviderResult:
        self.calls.append({"repair": repair_errors, "bundle_date": bundle.business_date.isoformat()})
        if self.script:
            raw = self.script.pop(0)
            return ProviderResult(
                raw=raw, text=json.dumps(raw, default=str), model=self.model, tokens_in=1000, tokens_out=300
            )
        recs = []
        for r in bundle.rule_results[:5]:
            recs.append(
                {
                    "entity_ref": r.entity_ref,
                    "action_type": r.candidate_action
                    if r.candidate_action
                    in ("HOLD", "WATCH", "DIAGNOSE", "INVESTIGATE_DATA", "PAUSE_TEST", "BACKLOG_CONCEPT")
                    else "WATCH",
                    "fact_refs": [f"rule:{r.rule_id}:{r.entity_ref}"],
                    "hypothesis": r.hypothesis,
                    "confidence": r.confidence.value,
                    "blocking_gates": r.blocking_gates,
                    "impact": r.impact,
                    "urgency": r.urgency,
                    "effort": r.effort,
                    "next_check_after_hours": 24 if r.severity.value != "CRITICAL" else 4,
                    "execution_allowed": False,
                    "alternative": "Bez zmian",
                    "conditions": ["świeże źródła", "brak konfliktującego eksperymentu"],
                }
            )
        status = (
            "DATA_ISSUE"
            if any(q.get("critical") for q in bundle.quality.values())
            else (
                "ACTION_REQUIRED"
                if any(r.severity.value == "CRITICAL" for r in bundle.rule_results)
                else ("WATCH" if bundle.rule_results else "NORMAL")
            )
        )
        raw = {
            "schema_version": "1",
            "business_date": bundle.business_date.isoformat(),
            "status": status,
            "summary": "Interpretacja deterministyczna (FakeProvider).",
            "facts": [f"{r.fact} [rule:{r.rule_id}:{r.entity_ref}]" for r in bundle.rule_results[:3]],
            "do_not_touch": [],
            "recommendations": recs,
        }
        return ProviderResult(
            raw=raw,
            text=json.dumps(raw, ensure_ascii=False, default=str),
            model=self.model,
            tokens_in=1500,
            tokens_out=400,
        )


class NoProvider:
    name = "none"

    def generate(
        self,
        bundle: EvidenceBundle,
        schema: dict[str, Any],
        budget: Budget,
        *,
        repair_errors: list[str] | None = None,
        previous: str | None = None,
    ) -> ProviderResult:
        return ProviderResult(raw=None, text="", model="none", error="LLM_PROVIDER=none")


def bundle_to_prompt(bundle: EvidenceBundle, budget: Budget) -> str:
    data = bundle.model_dump(mode="json")
    data["metric_refs"] = dict(list(data["metric_refs"].items())[: budget.max_evidence_items])
    data["rule_results"] = data["rule_results"][:40]
    data["allowed_action_types"] = [
        "HOLD",
        "WATCH",
        "DIAGNOSE",
        "INVESTIGATE_DATA",
        "PAUSE_TEST",
        "PROPOSE_BUDGET_INCREASE",
        "PROPOSE_BUDGET_DECREASE",
        "NEW_CREATIVE_TEST",
        "BACKLOG_CONCEPT",
        "FIX_INTEGRATION",
        "REVIEW_OFFER",
    ]
    return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
