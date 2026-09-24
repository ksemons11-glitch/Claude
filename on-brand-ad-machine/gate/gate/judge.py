"""Pluggable judge. Same questions and answer shapes whichever backend answers them.

- ClaudeJudge: Anthropic SDK, structured output (messages.parse) — needs credentials.
- ManualJudge: writes each request to a JSON file for an in-session reviewer to fill; reads answers back.
- StubJudge:   offline heuristic derived from the deterministic rules — keeps the pipeline runnable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

from .brain import Brain
from .rules import check_text
from .schemas import QUESTIONS, AdScore, BoolAnswer, OutputQA, PromptGate, ScoreAnswer

T = TypeVar("T", bound=BaseModel)

MODEL_ID = "claude-opus-5"

SYSTEM = (
    "You are the decision layer of an ad pipeline for the Polish skincare brand VeluSkin. "
    "You do not write copy. You answer typed questions about the item under review, one answer per "
    "question, using ONLY the brand context, products and rules given. Answer in the exact schema. "
    "Confidence is your calibrated probability that the chosen level/value is right. Reasons are short, "
    "in Polish, and cite the rule or claim id when one applies."
)


def _questions_block(schema_name: str) -> str:
    return json.dumps(QUESTIONS[schema_name], ensure_ascii=False, indent=1)


class Judge(Protocol):
    def score_ad(self, ad: dict) -> AdScore: ...
    def gate_prompt(self, prompt: dict) -> PromptGate: ...
    def qa_output(self, item: dict) -> OutputQA: ...


# --- Claude via SDK -------------------------------------------------------------------------------
@dataclass
class ClaudeJudge:
    brain: Brain
    model: str = MODEL_ID

    def _client(self):
        import anthropic  # imported lazily so the offline backends never need the SDK
        return anthropic.Anthropic()

    def _ask(self, schema: type[T], schema_name: str, payload: dict, extra_context: str) -> T:
        user = (
            f"<brand_context>\n{self.brain.brand_context()}\n</brand_context>\n"
            f"<brand_products>\n{self.brain.brand_products()}\n</brand_products>\n"
            f"<brand_rules>\n{self.brain.brand_rules()}\n</brand_rules>\n"
            f"<questions>\n{_questions_block(schema_name)}\n</questions>\n"
            f"{extra_context}\n"
            f"<item>\n{json.dumps(payload, ensure_ascii=False, indent=1)}\n</item>"
        )
        content: list[dict] = [{"type": "text", "text": user}]
        if payload.get("image_path"):
            import base64, mimetypes
            p = Path(payload["image_path"])
            content.insert(0, {"type": "image", "source": {"type": "base64",
                               "media_type": mimetypes.guess_type(p.name)[0] or "image/png",
                               "data": base64.b64encode(p.read_bytes()).decode()}})
        resp = self._client().messages.parse(
            model=self.model,
            max_tokens=4000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_format=schema,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"judge refused: {resp.stop_details}")
        return resp.parsed_output

    def score_ad(self, ad: dict) -> AdScore:
        return self._ask(AdScore, "AdScore", ad, "Judge `ad.transcript`/`ad.body` against brand_context and brand_products.")

    def gate_prompt(self, prompt: dict) -> PromptGate:
        return self._ask(PromptGate, "PromptGate", prompt, "Judge the generation prompt BEFORE any credit is spent.")

    def qa_output(self, item: dict) -> OutputQA:
        return self._ask(OutputQA, "OutputQA", item, "Judge the generated output (image and/or its `description`).")


# --- Manual (in-session reviewer) -----------------------------------------------------------------
@dataclass
class ManualJudge:
    brain: Brain
    outdir: Path

    def _dump(self, kind: str, schema_name: str, payload: dict):
        self.outdir.mkdir(parents=True, exist_ok=True)
        key = payload.get("id") or payload.get("copy_id") or str(abs(hash(json.dumps(payload, sort_keys=True))))
        req = self.outdir / f"{kind}-{key}.request.json"
        ans = self.outdir / f"{kind}-{key}.answer.json"
        req.write_text(json.dumps({"schema": schema_name, "questions": QUESTIONS[schema_name], "item": payload},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        if ans.exists():
            return json.loads(ans.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"answer missing: {ans} (fill it from {req})")

    def score_ad(self, ad: dict) -> AdScore:
        return AdScore.model_validate(self._dump("score", "AdScore", ad))

    def gate_prompt(self, prompt: dict) -> PromptGate:
        return PromptGate.model_validate(self._dump("gate", "PromptGate", prompt))

    def qa_output(self, item: dict) -> OutputQA:
        return OutputQA.model_validate(self._dump("qa", "OutputQA", item))


# --- Stub (offline heuristic) ---------------------------------------------------------------------
@dataclass
class StubJudge:
    brain: Brain

    def score_ad(self, ad: dict) -> AdScore:
        text = " ".join(str(ad.get(k, "")) for k in ("headline", "body", "transcript"))
        rep = check_text(text)
        fit = 0 if any(r.startswith(("C4", "C7", "C8", "C6")) for r in rep.must_ids) else (1 if rep.violations else 2)
        return AdScore(
            angle_strength=ScoreAnswer(level=1, confidence=0.5, reason="stub: nieznany kąt = familiar"),
            positioning_fit=ScoreAnswer(level=fit, confidence=0.6, reason=f"stub z reguł: {rep.summary()}"),
            reproducibility=ScoreAnswer(level=2 if "wideo" not in text.lower() else 1, confidence=0.5, reason="stub"),
            borrowed_ip=BoolAnswer(value=False, confidence=0.6, reason="stub: brak detekcji IP"),
        )

    def gate_prompt(self, prompt: dict) -> PromptGate:
        text = " ".join(str(prompt.get(k, "")) for k in ("headline", "subcopy", "prompt", "body"))
        rep = check_text(text, prompt.get("headline"), prompt.get("subcopy"))
        has = all(prompt.get(k) for k in ("zone", "offer_lockup", "cta"))
        risk = 2 if rep.hard_fail else (1 if any(w in text.lower() for w in ("pomaga", "wspiera", "gładsz")) else 0)
        return PromptGate(
            rule_conflict=BoolAnswer(value=rep.hard_fail, confidence=0.9 if rep.hard_fail else 0.7, reason=rep.summary()),
            elements_present=BoolAnswer(value=has, confidence=0.9, reason="zone/offer_lockup/cta present" if has else "missing field"),
            claim_risk=ScoreAnswer(level=risk, confidence=0.7, reason=rep.summary()),
            completeness=ScoreAnswer(level=2 if has and prompt.get("visual") else (1 if has else 0), confidence=0.6, reason="stub"),
        )

    def qa_output(self, item: dict) -> OutputQA:
        desc = str(item.get("description", ""))
        rep = check_text(desc)
        return OutputQA(
            logo_correct=BoolAnswer(value="logo" in desc.lower() or "veluskin" in desc.lower(), confidence=0.5, reason="stub"),
            palette_on_brand=BoolAnswer(value=any(c in desc.lower() for c in ("koral", "biel", "beż", "grafit")), confidence=0.5, reason="stub"),
            tone_match=ScoreAnswer(level=1, confidence=0.5, reason="stub"),
            unsupported_claim=BoolAnswer(value=rep.hard_fail, confidence=0.8, reason=rep.summary()),
            zone_shown=BoolAnswer(value=any(z in desc.lower() for z in ("ust", "brwi", "czoł", "ocz")), confidence=0.6, reason="stub"),
        )


def make_judge(kind: str, brain: Brain, outdir: Path | None = None) -> Judge:
    if kind == "claude":
        return ClaudeJudge(brain)
    if kind == "manual":
        return ManualJudge(brain, outdir or Path("judge-io"))
    return StubJudge(brain)
