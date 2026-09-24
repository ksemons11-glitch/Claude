"""Ranking and routing live in code, not in the model — change a coefficient and rerun."""
from __future__ import annotations

from dataclasses import dataclass

from .schemas import AdScore, OutputQA, PromptGate

WEIGHTS = {"angle_strength": 0.45, "positioning_fit": 0.40, "reproducibility": 0.15}
BORROWED_IP_DROP = 0.6          # drop when P(borrowed_ip) > this
REVIEW_BAND = (0.5, 0.85)       # confidence band that routes to a human
PROVEN_MIN_PERF = 61            # GetHookd performance score: Growing (61) / Optimized (81+) / Winning (91+)
PROVEN_MIN_DAYS = 30            # or: live for at least this many days


def _norm(level: int) -> float:
    return level / 2.0


def _p_true(b) -> float:
    return b.confidence if b.value else 1.0 - b.confidence


@dataclass
class Ranked:
    id: str
    score: float
    dropped: bool
    reason: str


def is_proven(perf: int | None, days: int | None) -> bool:
    """An ad counts as proven when the platform already rates it Growing+ or it has survived 30+ days.
    Testing-tier ads a few days old are hypotheses, not inspirations."""
    return (perf or 0) >= PROVEN_MIN_PERF or (days or 0) >= PROVEN_MIN_DAYS


def _mean_confidence(s: AdScore) -> float:
    return (s.angle_strength.confidence + s.positioning_fit.confidence
            + s.reproducibility.confidence + s.borrowed_ip.confidence) / 4


def rank_ads(scored: dict[str, AdScore], top_n: int = 10,
             evidence: dict[str, tuple[int | None, int | None]] | None = None) -> list[Ranked]:
    """Weighted judge score; ties broken by platform performance score, then judge confidence, then id.

    `evidence` maps ad id -> (performance_score, days_active). When given, ads that are not `is_proven`
    are dropped with reason "unproven" — the judge only sees the idea, the platform sees whether it sold.
    """
    out: list[Ranked] = []
    conf: dict[str, float] = {}
    perf: dict[str, int] = {}
    for ad_id, s in scored.items():
        p_ip = _p_true(s.borrowed_ip)
        score = sum(WEIGHTS[k] * _norm(getattr(s, k).level) for k in WEIGHTS)
        conf[ad_id] = _mean_confidence(s)
        pf, days = (evidence or {}).get(ad_id, (None, None))
        perf[ad_id] = pf or 0
        if p_ip > BORROWED_IP_DROP:
            out.append(Ranked(ad_id, round(score, 4), True, "borrowed_ip"))
        elif evidence is not None and not is_proven(pf, days):
            out.append(Ranked(ad_id, round(score, 4), True, "unproven"))
        else:
            out.append(Ranked(ad_id, round(score, 4), False, ""))
    kept = sorted([r for r in out if not r.dropped], key=lambda r: (-r.score, -perf[r.id], -conf[r.id], r.id))
    return kept[:top_n] + [r for r in out if r.dropped]


def route_prompt(g: PromptGate, hard_fail: bool) -> tuple[str, str]:
    """Plan's routing table: generate / review / reject."""
    if hard_fail:
        return "reject", "deterministic must-rule violation"
    p_conflict = _p_true(g.rule_conflict)
    if p_conflict > 0.85 or g.claim_risk.level == 2:
        return "reject", "rule conflict > 0.85 or top-level claim risk"
    flags = [p_conflict, 1 - _p_true(g.elements_present), g.claim_risk.confidence if g.claim_risk.level == 1 else 0.0]
    if any(REVIEW_BAND[0] <= f <= REVIEW_BAND[1] for f in flags):
        return "review", "a flag sits in the review band"
    completeness = _norm(g.completeness.level) * 2  # back to the plan's 0-2 scale
    if g.elements_present.value and g.claim_risk.level == 0 and completeness >= 1.5 and p_conflict < REVIEW_BAND[0]:
        return "generate", "clean"
    return "review", "not clean enough to auto-generate"


def route_output(q: OutputQA) -> tuple[str, str]:
    """Ship automatically above 0.85 on all checks, review in the band, reject below."""
    checks = {
        "logo_correct": _p_true(q.logo_correct),
        "palette_on_brand": _p_true(q.palette_on_brand),
        "tone_match": q.tone_match.confidence if q.tone_match.level == 2 else 0.0,
        "no_unsupported_claim": 1.0 - _p_true(q.unsupported_claim),
        "zone_shown": _p_true(q.zone_shown),
    }
    worst = min(checks, key=checks.get)
    if all(v > REVIEW_BAND[1] for v in checks.values()):
        return "ship", "all checks > 0.85"
    if any(v < REVIEW_BAND[0] for v in checks.values()):
        return "reject", f"{worst}={checks[worst]:.2f}"
    return "review", f"{worst}={checks[worst]:.2f} in band"
