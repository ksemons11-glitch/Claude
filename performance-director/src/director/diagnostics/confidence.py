"""Confidence classes + a deterministic 0-100 'heuristic evidence quality' score (never a probability)."""

from __future__ import annotations

from dataclasses import dataclass

from director.contracts.common import ConfidenceClass

SCORE_VERSION = "1"
WEIGHTS = {"data_quality": 35, "sample_strength": 30, "consistency": 20, "confounding": 15}
LEVELS = {"LOW": 0.0, "MEDIUM": 0.5, "HIGH": 1.0}


@dataclass
class Components:
    data_quality: str  # LOW/MEDIUM/HIGH
    sample_strength: str
    consistency: str
    confounding: str  # HIGH = little confounding

    def as_dict(self) -> dict[str, str]:
        return {
            "data_quality": self.data_quality,
            "sample_strength": self.sample_strength,
            "consistency": self.consistency,
            "confounding": self.confounding,
            "score_version": SCORE_VERSION,
        }


def evidence_score(c: Components) -> int:
    total = sum(WEIGHTS[k] * LEVELS[getattr(c, k)] for k in WEIGHTS)
    return int(round(total))


def confidence_class(c: Components) -> ConfidenceClass:
    if c.data_quality == "LOW" or c.sample_strength == "LOW":
        return ConfidenceClass.LOW
    score = evidence_score(c)
    if score >= 75 and c.confounding != "LOW":
        return ConfidenceClass.HIGH
    if score >= 45:
        return ConfidenceClass.MEDIUM
    return ConfidenceClass.LOW


def sample_level(n: int, low: int) -> str:
    if n < max(1, low // 3):
        return "LOW"
    if n < low:
        return "MEDIUM"
    return "HIGH"
