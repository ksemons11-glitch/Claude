"""Typed answer shapes for the judge — mirrors the Jev schemas from the plan (one typed answer per question).

`score` questions return 0/1/2 (index into `criteria`) plus a confidence in [0,1];
`noul` (yes/no) questions return a bool plus a confidence. Ranking and routing never read free text.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreAnswer(BaseModel):
    level: int = Field(ge=0, le=2, description="Index into the question's criteria list (0 = worst, 2 = best)")
    confidence: float = Field(ge=0, le=1, description="Calibrated probability that `level` is right")
    reason: str = Field(max_length=300)


class BoolAnswer(BaseModel):
    value: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(max_length=300)


# --- Step 4: score one competitor ad -----------------------------------------------------------
class AdScore(BaseModel):
    angle_strength: ScoreAnswer      # generic / competent-familiar / a specific new idea
    positioning_fit: ScoreAnswer     # contradicts / neutral / reinforces the brand
    reproducibility: ScoreAnswer     # needs assets we lack / with substitution / directly
    borrowed_ip: BoolAnswer          # true = depends on celebrity / character / partner brand


# --- Step 5: gate a generation prompt before spending a credit ----------------------------------
class PromptGate(BaseModel):
    rule_conflict: BoolAnswer        # true = prompt asks for something brand_rules forbid
    elements_present: BoolAnswer     # true = product, zone, offer lockup and CTA are all specified
    claim_risk: ScoreAnswer          # 0 none / 1 soft benefit language / 2 factual-health-performance claim
    completeness: ScoreAnswer        # 0 vague / 1 usable / 2 fully specified (visual, copy, format, palette)


# --- Step 7: compliance QA on a generated output (from an image or its description) -----------
class OutputQA(BaseModel):
    logo_correct: BoolAnswer
    palette_on_brand: BoolAnswer
    tone_match: ScoreAnswer          # off / neutral / unmistakably the brand
    unsupported_claim: BoolAnswer    # true = on-image copy asserts a benefit / result / comparison
    zone_shown: BoolAnswer           # VeluSkin-specific: product shown ON a face zone (belief #1)


QUESTIONS = {
    "AdScore": {
        "angle_strength": ["Generic category execution — product shot plus a claim, could be any brand",
                           "Competent but familiar — a recognised format executed well",
                           "A specific idea you have not seen in this category"],
        "positioning_fit": ["Contradicts the brand's positioning or tone",
                            "Neutral — could be adapted without conflict",
                            "Directly reinforces what the brand already stands for"],
        "reproducibility": ["Depends on assets or talent the brand does not have",
                            "Reproducible with effort or substitution",
                            "Reproducible directly with existing products/assets"],
        "borrowed_ip": {"true": "A named person, character, franchise or partner brand carries the idea",
                        "false": "The idea works without any external IP"},
    },
    "PromptGate": {
        "rule_conflict": {"true": "The prompt requests an element brand_rules forbid (banned claim, banned visual, wrong palette)",
                          "false": "No conflict with brand_rules"},
        "elements_present": {"true": "Product, face zone, offer lockup and CTA are all specified",
                             "false": "At least one required element is missing"},
        "claim_risk": ["No claim beyond descriptive / brand-name copy",
                       "Soft benefit language (pomaga, wspiera, gładszy wygląd)",
                       "Factual, health or performance claim (%, efekt od 1. nocy, klinicznie, botoks)"],
        "completeness": ["Vague — a generator would have to guess most of it",
                         "Usable — main elements set, some details open",
                         "Fully specified — visual, copy, format, palette, typography all stated"],
    },
    "OutputQA": {
        "logo_correct": {"true": "Wordmark/logo placement, colour and clear space match brand_rules",
                         "false": "Logo altered, wrongly coloured, cropped, dominant, or absent where required"},
        "palette_on_brand": {"true": "Dominant colours are among the named brand colours",
                             "false": "A dominant colour falls outside the named palette"},
        "tone_match": ["Actively off — mood contradicts the brand tone",
                       "Neutral — inoffensive but not recognisably the brand",
                       "Unmistakably the brand's tone (adult, calm, show-don't-promise)"],
        "unsupported_claim": {"true": "On-image copy asserts a specific benefit, result or comparison",
                              "false": "On-image copy is descriptive, brand-name only, or absent"},
        "zone_shown": {"true": "The patch is shown ON a specific face zone (lips / '11' / forehead / under-eye)",
                       "false": "Product shown beside packaging only, or no product visible"},
    },
}
