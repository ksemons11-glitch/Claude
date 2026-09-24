"""Deterministic copy gate — regex checks derived from brain/copy-rules.csv and brain/claims.csv.

These are the checks that are rules anyway; no model is needed and no model is allowed to override them.
A `must` violation is a hard fail; `should` violations are reported for the judge / human.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Text normalisation helpers ---------------------------------------------------------------------
_EXEMPT = [
    (r"100\s?%\s*silikon\w*", "STOPROC silikon"),   # "100% silikon" is the allowed material claim (K1)
]


def _normalise(text: str) -> str:
    t = text
    for pat, rep in _EXEMPT:
        t = re.sub(pat, rep, t, flags=re.I)
    return t


@dataclass(frozen=True)
class Rule:
    rule_id: str
    severity: str          # "must" | "should"
    pattern: str
    message: str
    flags: int = re.I

    def find(self, text: str) -> list[str]:
        return [m.group(0) for m in re.finditer(self.pattern, text, self.flags)]


RULES: list[Rule] = [
    Rule("C2", "must", r"!", "Wykrzyknik (zero wykrzykników)"),
    Rule("C3/K10", "must", r"medyczn\w*|medical[- ]grade|klasy medycznej",
         "„Silikon medyczny” — tylko „100% silikon” (K10 parked)"),
    Rule("C4/K13", "must",
         r"botoks\w*|botox\w*|liftin\w*|zamiast zabieg\w*|zast[ęe]puje zabieg\w*|alternatyw\w+ dla zabieg\w*|jak po zabiegu|efekt\w* jak po",
         "Botoks / lifting / zabieg jako punkt odniesienia skuteczności (K13)"),
    Rule("C6/K20-21", "must",
         r"-\s?\d{1,2}\s?%|promocj\w*|rabat\w*|tylko dzi[śs]|tylko teraz|ostatnie sztuki|do wyczerpania|najcz[eę][śs]ciej wybieran\w*|popularn\w*|bestseller|okazj\w*|oszcz[ęe]dzasz \d|przekre[śs]l\w*|odliczani\w*",
         "Rabat / deadline / fałszywy social proof cenowy (C6, K20, K21)"),
    Rule("C7/K22", "must",
         r"dermatolo\w*|ekspert\w*|lekarz\w*|chirurg\w*|laborator\w*|klinik\w*|latami bada[ńn]|badania klinicz\w*|klinicznie",
         "Fałszywy ekspert / klinika / badania (C7, K14, K22)"),
    Rule("C8/K12", "must",
         r"pierwsz\w*\s+(nocy|u[żz]yci\w*)|1\.\s*nocy|jedn\w+\s+u[żz]yciu|od pierwszej|po pierwszym|ju[żz] po (jednym|1)",
         "„Efekt od 1. nocy / po pierwszym użyciu” (K12)"),
    Rule("C8/K11", "must", r"ci[ąa][żz]\w*|karmieni\w*|laktacj\w*", "Bezpieczeństwo w ciąży/laktacji (K11)"),
    Rule("C8/K15-16", "must",
         r"trwale|na sta[łl]e|kolagen\w*|redukcj\w+ zmarszczek o \d|stymul\w*",
         "Trwałe usunięcie / kolagen / procent redukcji (K15, K16)"),
    Rule("C12", "must", r"\b(?!VeluSkin\b)[Vv][Ee][Ll][Uu][Ss][Kk][Ii][Nn]\b", "Pisownia marki: „VeluSkin”", flags=0),
    Rule("C15/K23", "must",
         r"usuwa\w*|likwiduj\w*|cofa\w* (czas|wiek|zmarszczki)|pozb[ąa]d[źz]|[żz]egnaj\w*|zatrzymaj (m[łl]odo[śs][ćc]|zmarszczki)|koniec ze zmarszczkami|metamorfoz\w*|ka[żz]d[ąa] zmarszczk\w*|na pewno zadzia[łl]a",
         "Język „usuwa / pozbądź się / żegnaj / każdą zmarszczkę” (C15, K23)"),
    Rule("K25", "must", r"napina\w*|pobudza\w*|odnow\w*|uj[ęe]drni\w*|napi[ęe]ci\w* sk[óo]ry",
         "„Napina / pobudza / odnowa / ujędrnia” — brak dowodu (K25)"),
    Rule("C21", "must", r"efekt\w* wow|rewolucj\w*|100\s?% gwarancj\w*|\bcud\w*", "Żargon „efekt WOW / rewolucja / cud” (C21)"),
    Rule("C14", "should", r"starze\w*|staro[śs][ćc]|wygl[ąa]dasz staro|m[łl]odziej|odm[łl]adza\w*",
         "Wstyd wokół wieku / „młodziej” (C14) — sprawdzić kontekst"),
    Rule("C20", "should", r"okluzj\w*|TEWL", "„Okluzja” — w copy konsumenckim mówić „zachowuje wilgoć” (C20)"),
    Rule("C13", "should", r"zmarszczk\w* palacza", "„Zmarszczki palacza” — preferować „linie wokół ust” (C13)"),
    Rule("C17", "should", r"skincare|routine|glow|anti[- ]aging", "Kalka z angielskiego (C17)"),
]

HEADLINE_MAX_WORDS = 12
SUBCOPY_MAX_WORDS = 18


@dataclass
class Violation:
    rule_id: str
    severity: str
    matches: list[str]
    message: str


@dataclass
class Report:
    violations: list[Violation] = field(default_factory=list)

    @property
    def hard_fail(self) -> bool:
        return any(v.severity == "must" for v in self.violations)

    @property
    def must_ids(self) -> list[str]:
        return [v.rule_id for v in self.violations if v.severity == "must"]

    @property
    def should_ids(self) -> list[str]:
        return [v.rule_id for v in self.violations if v.severity == "should"]

    def summary(self) -> str:
        if not self.violations:
            return "PASS"
        parts = [f"{v.rule_id}({', '.join(sorted(set(v.matches))[:3])})" for v in self.violations]
        return ("FAIL " if self.hard_fail else "WARN ") + "; ".join(parts)


_PERCENT = re.compile(r"(?<!STOPROC )(?<![\d,.])\d{1,3}\s?%")
_SOURCE_WORDS = re.compile(r"ankie[tc]\w*|badani\w+ naszych|w[śs]r[óo]d \d+ klientek", re.I)


def _percent_without_source(norm: str, window: int = 90) -> list[str]:
    """C5/K19: a percentage is allowed only when a survey/source word sits within `window` chars of it."""
    hits = []
    for m in _PERCENT.finditer(norm):
        ctx = norm[max(0, m.start() - window): m.end() + window]
        if not _SOURCE_WORDS.search(ctx):
            hits.append(m.group(0))
    return hits


def check_text(text: str, headline: str | None = None, subcopy: str | None = None) -> Report:
    """Run every deterministic rule on `text` (+ optional headline/subcopy length checks)."""
    norm = _normalise(text)
    rep = Report()
    pct = _percent_without_source(norm)
    if pct:
        rep.violations.append(Violation("C5/K19", "must", pct, "Procent bez źródła — dozwolony tylko jako „w ankiecie … %” (C5, K19)"))
    for rule in RULES:
        found = rule.find(norm)
        if found:
            rep.violations.append(Violation(rule.rule_id, rule.severity, found, rule.message))
    if headline is not None and len(headline.split()) > HEADLINE_MAX_WORDS:
        rep.violations.append(Violation("C18", "should", [headline], f"Nagłówek > {HEADLINE_MAX_WORDS} słów"))
    if subcopy is not None and len(subcopy.split()) > SUBCOPY_MAX_WORDS:
        rep.violations.append(Violation("C18", "should", [subcopy], f"Podtytuł > {SUBCOPY_MAX_WORDS} słów"))
    return rep
