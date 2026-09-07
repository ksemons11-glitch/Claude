"""Generate -> validate -> (one repair) -> fallback. Records tokens/cost. Never lets model text decide execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from director.contracts.reasoning import EvidenceBundle, LLMResponse
from director.reasoning.budget import estimate_cost_pln, within_budget
from director.reasoning.prompts import PROMPT_VERSION
from director.reasoning.provider import Budget, ReasoningProvider
from director.reasoning.validator import validate


@dataclass
class ReasoningOutcome:
    response: LLMResponse | None
    used: bool
    model: str
    error: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_pln: Decimal = Decimal(0)
    validation_errors: list[str] = field(default_factory=list)
    attempts: int = 0

    def meta(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "error": self.error,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_pln": str(self.cost_pln),
            "validation_errors": self.validation_errors[:10],
            "attempts": self.attempts,
        }


def run_reasoning(
    session: Session,
    provider: ReasoningProvider,
    bundle: EvidenceBundle,
    *,
    daily_budget_pln: Decimal,
    now: datetime,
    budget: Budget | None = None,
) -> ReasoningOutcome:
    budget = budget or Budget()
    if provider.name == "none":
        return ReasoningOutcome(None, False, "none", error="brak dostawcy LLM - raport deterministyczny")
    ok, spent = within_budget(session, daily_budget_pln=daily_budget_pln, now=now)
    if not ok and provider.name != "fake":
        return ReasoningOutcome(
            None,
            False,
            getattr(provider, "model", provider.name),
            error=f"budżet dzienny LLM wyczerpany ({spent} PLN) - raport deterministyczny",
        )
    schema = LLMResponse.model_json_schema()
    outcome = ReasoningOutcome(None, False, provider.name)
    res = provider.generate(bundle, schema, budget)
    outcome.attempts = 1
    outcome.model = res.model
    outcome.tokens_in += res.tokens_in
    outcome.tokens_out += res.tokens_out
    if res.error or res.raw is None:
        outcome.error = res.error or "empty model output"
        outcome.cost_pln = estimate_cost_pln(res.model, outcome.tokens_in, outcome.tokens_out)
        return outcome
    v = validate(res.raw, bundle)
    if not v.ok:
        outcome.validation_errors = v.errors
        res2 = provider.generate(bundle, schema, budget, repair_errors=v.errors, previous=res.text)
        outcome.attempts = 2
        outcome.tokens_in += res2.tokens_in
        outcome.tokens_out += res2.tokens_out
        if res2.raw is not None and not res2.error:
            v = validate(res2.raw, bundle)
            if not v.ok:
                outcome.validation_errors = v.errors
    outcome.cost_pln = estimate_cost_pln(res.model, outcome.tokens_in, outcome.tokens_out)
    if v.ok and v.response is not None:
        outcome.response, outcome.used = v.response, True
    else:
        outcome.error = "model output rejected by validator: " + "; ".join(outcome.validation_errors[:3])
    return outcome
