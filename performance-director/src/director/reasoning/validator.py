"""Output validator: rejects unknown refs/IDs, disallowed action types, numbers absent from the evidence,
recommendations that contradict gates, and any attempt to set execution_allowed. Also flags prompt-injection
style content (ad copy telling the model what to do)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from director.contracts.reasoning import ActionType, EvidenceBundle, LLMResponse

NUMBER_RE = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w.])")
INJECTION_MARKERS = (
    "ignore previous",
    "ignoruj poprzednie",
    "system prompt",
    "execute",
    "wykonaj natychmiast",
    "zwiększ budżet do",
    "api key",
    "token",
)
MAX_RECOMMENDATIONS = 5
ALLOWED_GATE_ACTIONS_WHEN_BLOCKED = {
    ActionType.HOLD,
    ActionType.WATCH,
    ActionType.DIAGNOSE,
    ActionType.INVESTIGATE_DATA,
    ActionType.BACKLOG_CONCEPT,
    ActionType.FIX_INTEGRATION,
    ActionType.REVIEW_OFFER,
    ActionType.NEW_CREATIVE_TEST,
}


@dataclass
class ValidationResult:
    ok: bool
    response: LLMResponse | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _numbers_in_evidence(bundle: EvidenceBundle) -> set[str]:
    nums: set[str] = set()
    for ref in bundle.metric_refs.values():
        v = ref.get("value")
        if v is not None:
            nums.update(_variants(str(v)))
    for r in bundle.rule_results:
        for text in (r.fact, r.hypothesis):
            nums.update(NUMBER_RE.findall(text))
        for v in list(r.observed.values()) + list(r.baseline.values()):
            if isinstance(v, (int, float, str)):
                nums.update(_variants(str(v)))
    for ref in list(bundle.all_refs()) + list(bundle.allowed_entity_refs):
        nums.update(NUMBER_RE.findall(ref.replace(":", " ")))
    nums.update(
        {
            str(bundle.business_date.year),
            str(bundle.business_date.month),
            str(bundle.business_date.day),
            f"{bundle.business_date.day:02d}",
            f"{bundle.business_date.month:02d}",
            str(bundle.constraints.get("max_actions", 5)),
        }
    )
    return nums


def _variants(s: str) -> set[str]:
    out = {s}
    try:
        f = float(s.replace(",", "."))
        out.add(f"{f:.0f}")
        out.add(f"{f:.1f}")
        out.add(f"{f:.2f}")
        out.add(f"{int(round(f * 100))}")
        out.add(str(int(f)) if f == int(f) else s)
    except ValueError:
        pass
    return {x.replace(".", ",") for x in out} | out


def validate(raw: dict[str, Any], bundle: EvidenceBundle) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        resp = LLMResponse.model_validate(raw)
    except ValidationError as exc:
        return ValidationResult(False, None, [f"schema: {e['loc']} {e['msg']}" for e in exc.errors()][:10])
    if resp.business_date != bundle.business_date:
        errors.append(f"business_date {resp.business_date} != {bundle.business_date}")
    known_refs = bundle.all_refs() | {
        f"dq:{c}" for q in bundle.quality.values() for c in (q.get("critical", []) + q.get("watch", []))
    }
    allowed_entities = set(bundle.allowed_entity_refs)
    known_numbers = _numbers_in_evidence(bundle)
    if len(resp.recommendations) > MAX_RECOMMENDATIONS:
        errors.append(f"too many recommendations: {len(resp.recommendations)} > {MAX_RECOMMENDATIONS}")
    gates_by_entity: dict[str, set[str]] = {}
    for r in bundle.rule_results:
        gates_by_entity.setdefault(r.entity_ref, set()).update(r.blocking_gates)
    for i, rec in enumerate(resp.recommendations):
        if rec.entity_ref not in allowed_entities:
            errors.append(f"rec[{i}] unknown entity_ref {rec.entity_ref}")
        for ref in rec.fact_refs:
            if ref not in known_refs:
                errors.append(f"rec[{i}] unknown fact_ref {ref}")
        if rec.execution_allowed:
            warnings.append(f"rec[{i}] set execution_allowed=true; overridden to false")
            rec.execution_allowed = False
        gates = gates_by_entity.get(rec.entity_ref, set())
        if gates and rec.action_type not in ALLOWED_GATE_ACTIONS_WHEN_BLOCKED:
            errors.append(f"rec[{i}] action {rec.action_type} contradicts blocking gates {sorted(gates)}")
        for num in NUMBER_RE.findall(rec.hypothesis + " " + rec.alternative + " " + " ".join(rec.conditions)):
            if num not in known_numbers and len(num) > 1:
                errors.append(f"rec[{i}] number '{num}' not present in evidence")
        text = (rec.hypothesis + " " + rec.alternative).lower()
        if any(m in text for m in INJECTION_MARKERS):
            errors.append(f"rec[{i}] suspicious instruction-like content")
    for j, fact in enumerate(resp.facts):
        for num in NUMBER_RE.findall(fact):
            if num not in known_numbers and len(num) > 1:
                errors.append(f"facts[{j}] number '{num}' not present in evidence")
        if any(m in fact.lower() for m in INJECTION_MARKERS):
            errors.append(f"facts[{j}] suspicious instruction-like content")
    for num in NUMBER_RE.findall(resp.summary):
        if num not in known_numbers and len(num) > 1:
            errors.append(f"summary number '{num}' not present in evidence")
    return ValidationResult(not errors, resp if not errors else None, errors, warnings)
