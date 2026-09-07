"""Weekly creative plan: briefs for backlog concepts, constrained by production capacity and test budget.
Never fabricates testimonials, doctors, or efficacy proof."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def build_briefs(
    *,
    shop_key: str,
    gaps: list[dict[str, Any]],
    concentration: dict[str, Any],
    capacity_per_week: int,
    test_budget_pln: Decimal | None,
    target_cpa: Decimal | None,
) -> list[dict[str, Any]]:
    briefs: list[dict[str, Any]] = []
    if capacity_per_week <= 0:
        return briefs
    slots = capacity_per_week
    if concentration.get("top_share") and concentration["top_share"] >= Decimal("0.70"):
        briefs.append(
            _brief(
                shop_key,
                "independent-winner-candidate",
                "Zbudować niezależny koncept obok dominującej kreacji (koncentracja ryzyka)",
                test_budget_pln,
                target_cpa,
                inspiration=f"concentration:{shop_key}",
                problem="uzależnienie wyniku od jednej kreacji",
                mechanism="nowy problem/desire, nie wariacja hooka",
            )
        )
        slots -= 1
    for g in sorted(gaps, key=lambda x: -(x["trend_score"] or 0))[: max(0, slots)]:
        briefs.append(
            _brief(
                shop_key,
                g["concept_key"],
                f"Koncept obserwowany na rynku ({g['coverage']} coverage, trend {g['trend_score']}); brak naszych wyników",
                test_budget_pln,
                target_cpa,
                inspiration=f"market_signal:{g['concept_key']}",
                problem=g["concept_key"].replace("-", " "),
                mechanism="do zdefiniowania w briefie - hipoteza, nie dowód",
            )
        )
    return briefs


def _brief(
    shop_key: str,
    concept_id: str,
    hypothesis: str,
    budget: Decimal | None,
    target_cpa: Decimal | None,
    *,
    inspiration: str,
    problem: str,
    mechanism: str,
) -> dict[str, Any]:
    return {
        "shop_key": shop_key,
        "concept_id": concept_id,
        "hypothesis": hypothesis,
        "problem": problem,
        "mechanism": mechanism,
        "hook": "(do napisania - 3 warianty hooka na ten sam rdzeń)",
        "shot_list": [
            "ujęcie problemu",
            "mechanizm/demonstracja",
            "efekt bez fikcyjnych dowodów",
            "CTA z ofertą",
        ],
        "vo": "(skrypt VO)",
        "cta": "Sprawdź ofertę",
        "offer": "aktualna oferta z modułu promotions",
        "proof_note": "Wyłącznie prawdziwe opinie/dowody z materiałów właściciela; nie sugerować fikcyjnych lekarzy ani wyników skuteczności.",
        "inspiration_evidence": inspiration,
        "primary_kpi": "expected_result_after_ads / CPA attributed",
        "test_budget_pln": str(budget) if budget is not None else None,
        "test_days": 3,
        "success_criterion": f"CPA attributed <= {target_cpa} PLN przy >= 10 zakupach po 3 pełnych dniach"
        if target_cpa
        else "brak docelowego CPA - kryterium do ustalenia",
        "stop_criterion": "przekroczony test_loss_cap lub brak zakupów przy spend >= 2x docelowego CPA",
    }
