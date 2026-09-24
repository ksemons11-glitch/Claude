#!/usr/bin/env python3
"""Compile the VeluSkin brand-brain CSVs into one readable PDF."""
import csv
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

HERE = Path(__file__).parent
OUT = HERE / "VeluSkin-Brand-Brain.pdf"

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Title"], fontName="DVB", fontSize=22, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="DVB", fontSize=14, spaceBefore=10, spaceAfter=6)
BODY = ParagraphStyle("b", parent=ss["BodyText"], fontName="DV", fontSize=9, leading=12)
CELL = ParagraphStyle("c", parent=BODY, fontSize=7.5, leading=9.5)
CELLB = ParagraphStyle("cb", parent=CELL, fontName="DVB")

# (file, title, intro, columns to show or None=all)
SECTIONS = [
    ("brand-core.csv", "1. Brand core", "Kim jest VeluSkin, co obiecuje i jakich zasad nie łamie.", ["key", "value", "status"]),
    ("audiences.csv", "2. Audiences (ICP)", "Do kogo mówimy i co ich boli.", ["name", "age", "pain_points", "triggers", "objections", "status"]),
    ("visual-universe.csv", "3. Visual universe", "Jak marka wygląda — i jak nigdy nie wygląda.", ["element", "rule", "status"]),
    ("brand-kit.csv", "4. Brand kit", "Logo, kolory, fonty, linki.", ["asset", "value", "status"]),
    ("products.csv", "5. Products", "Co sprzedajemy i za ile.", ["name", "placement", "price_pln", "reuses", "key_claim", "status"]),
    ("competitors.csv", "6. Competitors (GetHookd spy)", "Kto wygrywa w kategorii i jakim kątem.", ["brand", "best_tier", "formats", "signature_angle", "watched"]),
    ("inspiration-set.csv", "6b. Inspiration set — 10 marek (Krok 2)", "5 bezpośrednich + 5 sąsiednich; sąsiednie dają kąty, których kategoria jeszcze nie używa.", ["rank", "type", "brand", "why", "status"]),
    ("winning-creatives.csv", "6c. Dawne winnery (referencja)", "Tylko jako kontekst dla Jev (positioning_fit) — hard_rule_1 zabrania remiksu.", ["creative_id", "headline_pl", "angle", "why_it_worked", "status"]),
    ("inspirations.csv", "7. Inspirations — 10 kątów", "Zwycięskie kąty kategorii i ich świeży re-voice dla VeluSkin.", ["rank", "angle", "pl_headline", "pl_subcopy", "status"]),
    ("copy-rules.csv", "8. Copy rules (checklista JEV)", "Każda kreacja przechodzi przez tę listę.", ["rule_id", "check", "type"]),
    ("campaign-learnings.csv", "9. Campaign learnings", "Czego się nauczyliśmy i co z tego wynika.", ["date", "learning", "implication", "status"]),
]


def table(rows, cols):
    data = [[Paragraph(c, CELLB) for c in cols]]
    for r in rows:
        data.append([Paragraph(str(r.get(c, "")).replace("&", "&amp;"), CELL) for c in cols])
    avail = A4[0] - 30 * mm
    widths = [avail / len(cols)] * len(cols)
    # give the longest text column extra room
    if len(cols) > 2:
        widths = [avail * 0.18] + [avail * 0.82 / (len(cols) - 1)] * (len(cols) - 1)
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDE7DF")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9C2B8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF7F2")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def main():
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm, title="VeluSkin — Brand Brain")
    story = [Paragraph("VeluSkin — Brand Brain", H1),
             Paragraph("Kontekst marki dla On-Brand Ad Machine. Źródło prawdy: pliki CSV w tym folderze; "
                       "ten PDF jest ich skompilowanym widokiem. Statusy: confirmed / draft / missing (TODO).", BODY),
             Spacer(1, 6)]
    for fname, title, intro, cols in SECTIONS:
        rows = list(csv.DictReader(open(HERE / fname, encoding="utf-8")))
        cols = cols or list(rows[0].keys())
        story += [Paragraph(title, H2), Paragraph(intro, BODY), Spacer(1, 4), table(rows, cols), Spacer(1, 8)]
    doc.build(story)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
