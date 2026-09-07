"""Marginal allocation of the next N PLN. Compares expected marginal contribution after ads, not historical
average ROAS. With thin data -> 'no reliable response curve; propose a bounded experiment'."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

D0 = Decimal("0")
MIN_POINTS = 10


@dataclass
class Candidate:
    key: str  # shop or campaign ref
    spend_points: list[Decimal]
    result_points: list[Decimal]  # expected_result_after_ads for the same days
    current_daily_budget: Decimal
    is_cbo: bool = False
    stock_days_cover: Decimal | None = None
    fulfillment_ok: bool | None = None
    season_note: str | None = None
    economics_known: bool = True


@dataclass
class AllocationProposal:
    key: str
    delta_pln: Decimal
    marginal_estimate: Decimal | None
    kind: str  # ALLOCATE | EXPERIMENT | BLOCKED
    reasons: list[str] = field(default_factory=list)


def marginal_slope(spend: list[Decimal], result: list[Decimal]) -> Decimal | None:
    """OLS slope d(result)/d(spend) on the top half of spend observations (local response). None if unreliable."""
    if len(spend) < MIN_POINTS or len(spend) != len(result):
        return None
    pairs = sorted(zip(spend, result, strict=True), key=lambda p: p[0])[len(spend) // 2 :]
    n = len(pairs)
    mx = sum((p[0] for p in pairs), start=D0) / n
    my = sum((p[1] for p in pairs), start=D0) / n
    sxx = sum(((p[0] - mx) ** 2 for p in pairs), start=D0)
    if sxx == 0:
        return None
    sxy = sum(((p[0] - mx) * (p[1] - my) for p in pairs), start=D0)
    return sxy / sxx


def allocate(
    candidates: list[Candidate],
    *,
    amount_pln: Decimal,
    total_daily_cap: Decimal | None,
    current_total: Decimal,
    cash_reserve_ok: bool | None,
    max_step_pct: Decimal = Decimal("0.15"),
) -> list[AllocationProposal]:
    out: list[AllocationProposal] = []
    if total_daily_cap is not None and current_total + amount_pln > total_daily_cap:
        amount_pln = max(D0, total_daily_cap - current_total)
        out.append(
            AllocationProposal(
                "portfolio",
                D0,
                None,
                "BLOCKED",
                [f"total daily cap {total_daily_cap} PLN; dostępne {amount_pln} PLN"],
            )
        )
    if cash_reserve_ok is False:
        return out + [
            AllocationProposal(
                "portfolio", D0, None, "BLOCKED", ["rezerwa gotówki poniżej limitu (COD settlement lag)"]
            )
        ]
    scored: list[tuple[Decimal, Candidate]] = []
    for c in candidates:
        if not c.economics_known:
            out.append(AllocationProposal(c.key, D0, None, "BLOCKED", ["brak ekonomiki produktu"]))
            continue
        if c.stock_days_cover is not None and c.stock_days_cover < 7:
            out.append(AllocationProposal(c.key, D0, None, "BLOCKED", [f"zapas na {c.stock_days_cover} dni"]))
            continue
        if c.fulfillment_ok is False:
            out.append(AllocationProposal(c.key, D0, None, "BLOCKED", ["ograniczenie realizacji zamówień"]))
            continue
        slope = marginal_slope(c.spend_points, c.result_points)
        if slope is None:
            step = min(amount_pln, (c.current_daily_budget * max_step_pct).quantize(Decimal("1")))
            out.append(
                AllocationProposal(
                    c.key,
                    step,
                    None,
                    "EXPERIMENT",
                    [
                        f"brak wiarygodnej krzywej odpowiedzi; proponowany ograniczony eksperyment (+{step} PLN/dzień, 3 dni, loss cap wymagany)"
                    ],
                )
            )
            continue
        scored.append((slope, c))
    remaining = amount_pln
    for slope, c in sorted(scored, key=lambda t: t[0], reverse=True):
        if remaining <= 0:
            break
        if slope <= 0:
            out.append(
                AllocationProposal(
                    c.key,
                    D0,
                    slope,
                    "BLOCKED",
                    ["ujemna marginalna kontrybucja na ostatnich poziomach spendu"],
                )
            )
            continue
        step = min(remaining, (c.current_daily_budget * max_step_pct).quantize(Decimal("1")))
        out.append(
            AllocationProposal(
                c.key,
                step,
                slope,
                "ALLOCATE",
                [
                    f"marginalny wynik ≈ {slope:.2f} PLN na 1 PLN (lokalna estymata, {len(c.spend_points)} dni)",
                    "daily i lifetime budżety liczone osobno; budżet CBO nie sumuje się z zestawami",
                ],
            )
        )
        remaining -= step
    return out
