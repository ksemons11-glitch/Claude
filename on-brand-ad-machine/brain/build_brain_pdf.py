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
    ("brand-core.csv", "1. Brand core", "Firma, Big Idea, pozycjonowanie, obietnice, mechanizm, ton, twarde zasady.", ["key", "value", "status"]),
    ("products.csv", "2. Product & offer", "Jeden produkt, cennik 1/2/3, koszt użycia, dostawa, płatność, zwrot.", ["field", "value", "status"]),
    ("audiences.csv", "3. Audiences", "Segment główny 40–55, poboczne 35–44 i 50+, hipotezy.", ["segment_id", "name", "age", "pain_points", "objections", "proof_wanted", "status"]),
    ("belief-chain.csv", "4. Łańcuch przekonań", "6 przekonań w kolejności — storyboard każdej kreacji i strony.", ["step", "belief", "how_to_build", "evidence_gap"]),
    ("claims.csv", "5. Claim sheet", "Co wolno, co zakazane, co niezweryfikowane. Brak dowodu = brak claimu.", ["claim_id", "claim", "allowed", "evidence", "note"]),
    ("proof-assets.csv", "6. Materiały dowodowe do nagrania", "Bez nich kreacje nie przejdą przekonań 4–5.", ["asset_id", "asset", "spec", "unlocks", "status"]),
    ("copy-rules.csv", "7. Copy rules (checklista Jev)", "Każdy prompt i każda kreacja przechodzi przez tę listę.", ["rule_id", "check", "type", "status"]),
    ("visual-universe.csv", "8. Visual universe", "Jak marka wygląda — i jak nigdy nie wygląda.", ["element", "rule", "status"]),
    ("brand-kit.csv", "9. Brand kit", "Sklep, firma, logo, paleta po nazwach, fonty.", ["asset", "value", "status"]),
    ("competitors.csv", "10. Competitors", "Z researchu + GetHookd spy: kto wygrywa, jakim kątem, czego nie kopiować.", ["brand", "best_tier", "signature_angle", "notes"]),
    ("inspiration-set.csv", "11. Inspiration set — 10 marek (Krok 2)", "5 direct + 5 adjacent; adjacent dają kąty, których kategoria nie używa.", ["rank", "type", "brand", "why", "status"]),
    ("inspirations.csv", "12. Kąty reklamowe", "5 kierunków z briefu + kąty kategorii; status ready / blocked / banned.", ["rank", "angle", "role", "pl_headline", "pl_subcopy", "status"]),
    ("winning-creatives.csv", "13. Dawne winnery (Meta, konto Pooa)", "Referencja i benchmark — hard_rule_1 zabrania remiksu.", ["rank", "ad_name", "created", "spend_pln", "purchases", "cpa_pln", "ctr", "format_guess", "note"]),
    ("creative-library.csv", "13b. Biblioteka copy VeluSkin + audyt claimów", "15 unikalnych copy z konta; flagi = claimy zakazane przez brief.", ["copy_id", "variants", "angle", "headline", "banned_flags", "status"]),
    ("campaign-learnings.csv", "14. Campaign learnings", "Wnioski, hipotezy testowe, write-back.", ["date", "learning", "implication", "status"]),
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
