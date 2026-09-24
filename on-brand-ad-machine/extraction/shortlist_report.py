"""Render extraction/shortlist.json -> shortlist.md + shortlist-gallery.html (images from shortlist-media/)."""
from __future__ import annotations

import base64
import glob
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "extraction"
d = json.loads((EX / "shortlist.json").read_text(encoding="utf-8"))
by = {r["id"]: r for r in d["ads"]}
full = {}
for f in EX.glob("*.json"):
    if f.name in {"all-ads.json", "judge-answers.json", "shortlist.json", "wrinkles-schminkles-test.json"}:
        continue
    for a in json.loads(f.read_text(encoding="utf-8")).get("ads", []):
        full[str(a["id"])] = a

SHARE = {
 "149861556": "https://app.gethookd.ai/share/ad/149861556?signature=cbc3c9b17f62985678bc22a81e1c15f5ace85e85deadf8548ad5d1c1da4377dd",
 "119368742": "https://app.gethookd.ai/share/ad/119368742?signature=2f045481bd77d8b6aa7d9e1ccb184f27257044b4f2e10652ca55fa74cc21b228",
 "143124227": "https://app.gethookd.ai/share/ad/143124227?signature=08c24d0945e8d4475362def316e691edcf3d3d08f535f990135c37d1ac2e95ba",
 "173665393": "https://app.gethookd.ai/share/ad/173665393?signature=f4a7511dd6aabb71247a1d5e54415bcbe27c6c7b51b331aaa7cdda629db92289",
 "157292606": "https://app.gethookd.ai/share/ad/157292606?signature=220671b1a25adaff8ff0be82e71ec35d30a97d2e99c569fc123b3bc74362939a",
 "128944655": "https://app.gethookd.ai/share/ad/128944655?signature=e6cfdebbd7f18798ce5caead60d827306002bfeff57a272df284a0ac99197d12",
 "149861557": "https://app.gethookd.ai/share/ad/149861557?signature=55813946d0c6a3224ba650abea460d84233306c5ae0ff2672b0bfb5b4e0b219d",
 "119368763": "https://app.gethookd.ai/share/ad/119368763?signature=fcd22580011a1387ad21e745adf8439fa1d720d7b19a6a3247e36d204990378d",
 "133043224": "https://app.gethookd.ai/share/ad/133043224?signature=2636a374420f120b218aaa1d273f570151dd430c6682e79142b858522f938303",
 "124333814": "https://app.gethookd.ai/share/ad/124333814?signature=ef2bec5111b7b8aaf25f474c06dd9dc416c2f696498f828ecb24cd04d1e94f85",
 "181080083": "https://app.gethookd.ai/share/ad/181080083?signature=203ccc569ec6ffa0ca3b03a9f69cbef54a3c487240f0a8177bfb636a41880605",
 "181482577": "https://app.gethookd.ai/share/ad/181482577?signature=98266961c0a5904c9b5c1417a71b5ed77f8ce045ae536f9b2924c185fdc3f23d",
 "174013810": "https://app.gethookd.ai/share/ad/174013810?signature=2c5c81712f3f5a9d9c83c0265a559dd94c41711e98ccaaa368e7eb59ecd22f35",
 "181080114": "https://app.gethookd.ai/share/ad/181080114?signature=cb6935a66320b9465e3fe0bbf5d48d85d61f4bc1fb5d48a1f9be0661a38ab9e1",
 "177231360": "https://app.gethookd.ai/share/ad/177231360?signature=43bde183dda8b07b7bddbe08884b3c68367ad4a8e65dbc79a8c5db757310ca87",
 "181332804": "https://app.gethookd.ai/share/ad/181332804?signature=511377e373c87ef2920badddf4209a0496ced57966b0fadf1192ac991b704507",
 "180682320": "https://app.gethookd.ai/share/ad/180682320?signature=757a695cb69dea95b11aa8d51c5a1702dce01a55047eb12bb116d184ddb4711a",
 "177231372": "https://app.gethookd.ai/share/ad/177231372?signature=f9694e54de9b0089255307ad9671c61f71cc4458b7ddc20982dc93a902d1732c",
}
NAMES = {
 "149861556": "SoSmooth — „Zawsze chciałaś spróbować? ~1,50 $ za użycie”",
 "119368742": "SiO — „Śpisz na boku? Skóra składa się w tym samym miejscu” (DCO)",
 "143124227": "Eight Sleep — karta „raport nocy” (Autopilot recap)",
 "173665393": "Hers — „3 powody, dla których NIENAWIDZĘ minoxidilu” (odwrócona obiekcja)",
 "157292606": "Scarlette — „Moje 11 sprawiały, że wyglądałam na złą”",
 "128944655": "SiO — „Obudziłam się w szoku, jak gładko” (DCO, Winning)",
 "149861557": "SoSmooth — „Plaster na każdą linię” (makro odklejania)",
 "119368763": "SiO — „Zmarszczki nie czekają. Bez kremów, bez rutyny.” (Winning)",
 "133043224": "SiO — „Ten plaster obudził mnie w szoku” (wersja pojedyncza)",
 "124333814": "SiO — „Nocna poprawka dla śpiących na boku”",
 "181080083": "SoSmooth — „1,05 $ za noc”", "181482577": "Scarlette — „Taśma na twarzy? Serio?”",
 "174013810": "SoSmooth — „8 nocy, jeden plaster”", "181080114": "SoSmooth — „Myślałam, że to bajer”",
 "177231360": "SiO — „Trzyma skórę płasko, gdy śpisz”", "181332804": "SiO — „Śpisz na boku? To tłumaczy coś…”",
 "180682320": "SiO — „Rytuał, nie naprawa”", "177231372": "SiO — „Jedyna rzecz, którą daję sobie”",
 "177231362": "SiO — „Bluzka, którą znów noszę”",
}
ADAPT = {
 "149861556": ("Cold A2 / value statyk", "„Zawsze chciałaś sprawdzić plastry, ale nie wiedziałaś, czy warto? Do ok. 20 użyć. Około 19 groszy za noc.” Statyk z packshotem w ciepłej bieli; „Proven, not promised” → „Pokażemy zamiast obiecywać” + „ponad 1500 opinii, 4,7/5” (K17). Wyciąć „medical-grade”."),
 "119368742": ("Cold — przyczyna → mechanizm → rano (nasz wzorzec)", "11 s, talking-head w łazience: „[uczciwa przyczyna] → to VeluSkin → 100% silikon, wielorazowy, pomaga zachować wilgoć przez noc”. U nas przyczyna dla ust/„11”: mimika + sucha skóra + makijaż, bez straszenia (C14). 6 wariantów DCO = ten sam skrypt, różne ujęcia — łatwe do AI-UGC."),
 "143124227": ("Format dowodu (remarketing)", "Karta „raport” na packshocie/wideo: zamiast „+20% deep sleep” — checklista rytuału: „wieczór: naklejone / rano: nadal na miejscu / płukanie: 1 z ~20”. Liczby tylko ze źródłem (C5); to wzorzec wizualny, nie copy."),
 "173665393": ("Hook cold (odwrócona obiekcja)", "„3 powody, dla których NIE wierzyłam w plastry na zmarszczki” → 1. odpadają w nocy (u mnie trzymały), 2. to tylko taśma (nie: 100% silikon zatrzymuje wilgoć), 3. jeden plaster = jedno użycie (do ~20). Postać UGC, napisy, bez lektora AI z disclaimerem."),
 "157292606": ("Cold — strefa „11” (hipoteza #3)", "Historia w copy: „W pracy pytali, czy wszystko OK. Było OK — tak wyglądały te dwie linie między brwiami.” Wyciąć botoks ×3, medical-grade, „40× wilgoci”, „po jednej nocy”, tacę medyczną (banned_visuals). Statyk: plaster między brwiami w łazience."),
 "128944655": ("UGC 13 s — szkielet winnera", "Winning (100) od 65 dni: problem → znalazłam → rano → cechy (gruby, wygodny, wielorazowy) → CTA. U nas: „linie wokół ust przeszkadzały mi w makijażu → VeluSkin na noc → rano sprawdzam tę samą strefę → 100% silikon, wielorazowy” — bez „szok/one night” (K12), z „sprawdź rano”."),
 "149861557": ("Demo makro (cold i remarketing)", "Ekstremalne zbliżenie odklejania plastra z okolic ust/„11” + jedno zdanie. „Made in Australia” → „Lekiro, Polska” (#8). Wyciąć „87% vs zastrzyki”, „medical-grade”, „jak po zastrzykach”."),
 "119368763": ("UGC 21 s — „bez kremów” (Winning)", "Kobieta w szlafroku przyciska plaster: „Bez kolejnego kremu, bez rutyny. Naklejasz na noc na wybraną strefę.” To nasz kąt #1 „nie kolejny krem” w wersji, która u SiO wygrywa od 77 dni. Bez „zmarszczki nie czekają” (C14) i bez „just results” (C15)."),
 "133043224": ("Wariant #6", "Ta sama kreacja co 128944655 w wersji pojedynczej (52 dni, Optimized) — potwierdza, że szkielet działa w obu formatach; dla nas jeden skrypt, dwa cięcia (DCO 6 ujęć + pojedyncze)."),
 "124333814": ("Cold — „dociska i nawilża” w 11 s", "Najkrótszy skrypt w puli: „jestem X → to VeluSkin → wielorazowy plaster ze 100% silikonu, który pomaga zachować wilgoć w skórze przez noc”. Mechanizm C20 w jednym zdaniu; blondynka ~45 w łazience = nasz ugc_character."),
}
FRESH_NOTE = {
 "181080083": "matematyka za noc (K8) — 4 dni, Testing (1)", "181482577": "obiekcja „taśma na twarzy?” jako hook 7 s — 3 dni, Testing (14)",
 "174013810": "trigger makijażu + strefa — 17 dni, Scaling (41), najbliżej progu", "181080114": "dialog sceptyczek + wyjaśniacz — 4 dni, Testing (1)",
 "177231360": "mechanizm w jednym zdaniu / profilaktyka — 11 dni, Testing (38)", "181332804": "edukacja przyczyną — 4 dni, Testing (16)",
 "180682320": "„rytuał, nie naprawa” — 6 dni, Testing (28)", "177231372": "linia emocjonalna — 12 dni, Scaling (48)",
 "177231362": "wynik behawioralny zamiast claimu — 11 dni, Testing (38)",
}
IMGNOTE = {
 "119368742": "DCO 6 wideo × 11 s — poster pierwszego wariantu.", "128944655": "DCO 6 wideo × 13 s — poster pierwszego wariantu.",
 "133043224": "Wideo 13 s — poster.", "124333814": "Wideo 11 s (2 warianty) — poster.", "119368763": "Wideo 21 s (2 warianty) — poster.",
 "149861557": "Wideo 24 s — klatka 0 s.", "143124227": "Statyk 9:16.", "173665393": "Wideo 35 s — klatka 0 s; lektor AI + „Actor Portrayal”.",
 "149861556": "Statyk.", "157292606": "Statyk (taca medyczna = banned_visuals) + długie copy-historia.",
}

def img64(aid):
    fs = glob.glob(str(EX / "shortlist-media" / f"{aid}-*.jpg"))
    return base64.b64encode(Path(fs[0]).read_bytes()).decode() if fs else ""

# ---------- markdown ----------
L = ["# Krok 4 — shortlista: 90 reklam → top 10 SPRAWDZONYCH\n",
     f"Data: 2026-09-24 (rev. 2 — po uwadze właściciela: „co to za sprawdzone adsy, które chodzą od paru dni”). Sędzia: manualny (4 typowane pytania z `gate/gate/schemas.py`). Ranking w kodzie `gate/gate/rank.py`: angle 0,45 / fit 0,40 / repro 0,15; odrzut gdy P(borrowed_ip) > 0,6; **bramka „sprawdzone”: {d['proven_rule']}** (GetHookd: Growing 61 / Optimized 81 / Winning 91+); remis → wyższy wynik platformy. Odtworzenie: `python3 extraction/shortlist.py && python3 extraction/shortlist_report.py`.\n",
     "Wejście: 90 reklam z 8 marek, 53 wideo z transkrypcją (39 gotowych, 13 bez mowy, 1 niedostępny). Koszt kroku: 0,2 kredytu GetHookd (pobranie klatek). Oceny dotyczą POMYSŁU względem pozycjonowania VeluSkin; wszystkie stwierdzenia konkurencji zostały w polu `claims` bez filtrowania — decyduje właściciel.\n",
     "## Top 10 (sprawdzone przez rynek)\n",
     "| # | ID | Reklama | Perf. | Dni | Wynik sędziego | Kąt / Fit / Repro | Rola u nas |", "|---|---|---|---|---|---|---|---|"]
for i, aid in enumerate(d["top10"], 1):
    r = by[aid]; lv = r["levels"]
    L.append(f"| {i} | {aid} | {NAMES[aid]} | {r['tier']} | {r['days_active']} | {r['score']:.3f} | {lv['angle']} / {lv['fit']} / {lv['repro']} | {ADAPT[aid][0]} |")
L.append("\n## Dlaczego te i jak je przepisać na VeluSkin\n")
for i, aid in enumerate(d["top10"], 1):
    r = by[aid]; a = full[aid]
    L.append(f"### {i}. {NAMES[aid]} (`{aid}`, {r['format']}, {r['tier']}, {r['days_active']} dni)\n")
    L += [f"- **Kąt:** {r['reasons']['angle']}", f"- **Fit:** {r['reasons']['fit']}", f"- **Odtwarzalność:** {r['reasons']['repro']}",
          f"- **Adaptacja:** {ADAPT[aid][1]}"]
    if a.get("transcript"):
        L.append(f"- **Transkrypt:** {a['transcript'][:400]}")
    cl = a.get("claims", [])
    L.append("- **Claimy konkurenta (nieprzefiltrowane):** " + " • ".join(cl[:6]) + (f" • … (+{len(cl)-6})" if len(cl) > 6 else ""))
    L.append("")
L.append("## Świeże hipotezy (dobry pomysł wg sędziego, ale NIE sprawdzone: Testing / kilka dni)\n")
L.append("Nie są inspiracją do batcha 1. Sprawdzić ponownie za 2–3 tygodnie (GetHookd brand spy na SoSmooth / SiO / Scarlette); jeśli przejdą do Growing+, wchodzą do puli.\n")
for aid in d["fresh_hypotheses"]:
    L.append(f"- `{aid}` {NAMES.get(aid, aid)} — {FRESH_NOTE.get(aid, '')}")
L.append("\n## Co wypadło i dlaczego\n")
L.append("- **20 reklam za pożyczone IP** (Ulta, Boots, Shark Tank, The Plaza, Byrdie, NYFW, Wegovy): Wrinkles Schminkles i 111SKIN opierają obecny push na dystrybucji i autorytecie. Nasz odpowiednik = trust „Lekiro, Gostynin, zwrot 14 dni, BLIK/pobranie” (#8).")
L.append("- **Sprawdzone, ale poza marką (fit = 0)**: SoSmooth „Real women. No needles.” (Winning 100 — botoks jako oś), „Reusable 20+ times / po 60. zmarszczki pogłębiają się” (Winning 100 — straszenie wiekiem), „UNBELIEVABLE 50% OFF” (Winning 100), Scarlette „60% OFF + botoks” ×4 (Optimized 86–90), 111SKIN „injectables in a bottle” (90). To, co w kategorii sprzedaje najmocniej, brief wprost zakazuje (C4, C6, C14) — stąd wynik sędziego ≤ 0,3 mimo wyników platformy.")
L.append("- **Wniosek z rev. 2**: sprawdzone winnery kategorii to prawie wyłącznie SiO (UGC 11–21 s w łazience, przyczyna → mechanizm → rano) i SoSmooth (statyk value + makro). Pięć „najładniejszych” pomysłów z rev. 1 to testy sprzed kilku dni — przeniesione do hipotez.\n")
L.append("## Co z tego wynika dla kroku 5\n")
L.append("1. Szkielet batcha 1 = szkielet SiO (Winning 100, 65–77 dni): **problem w 1 zdaniu → „to VeluSkin” → mechanizm prostym językiem → rano sprawdzasz tę samą strefę → cechy (100% silikon, wielorazowy) → CTA**, 11–21 s, postać w łazience. To pokrywa się z naszym `ugc_structure` i z aktualnym winnerem v1.")
L.append("2. Statyk value (SoSmooth 149861556, Optimized 86, 37 dni) = jedyny sprawdzony statyk w puli, który pasuje do marki: pytanie do niezdecydowanej + reuse + koszt/użycie. Inspirations #6.")
L.append("3. Hooki: „11”/strefa (Scarlette 157292606, Growing) i odwrócona obiekcja (Hers, Optimized) — jako warianty otwarcia tego samego szkieletu, nie osobne kreacje.")
L.append("4. Każda z 10 wymaga wycięcia „medical-grade” (C3); żadna nie wymaga PRZED/PO.")
(EX / "shortlist.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- gallery ----------
def card(i, aid, fresh=False):
    a = full[aid]; r = by[aid]; lv = r["levels"]
    tr = a.get("transcript") or ""
    claims = "".join(f"<li>{html.escape(c)}</li>" for c in a.get("claims", []))
    head = (f"HIPOTEZA · {html.escape(a['brand'])} · {html.escape(str(r['tier']))} · {r['days_active']} dni" if fresh
            else f"#{i} · {html.escape(a['brand'])} · {html.escape(str(r['tier']))} · {r['days_active']} dni · sędzia {r['score']:.2f} (kąt {lv['angle']} / fit {lv['fit']} / repro {lv['repro']})")
    body = f'''
  <h3>Nagłówek</h3><p>{html.escape(str(a.get("headline") or "—"))}</p>
  <h3>Treść reklamy</h3><p class="pre">{html.escape(a.get("body") or "—")}</p>
  {'<h3>Transkrypt wideo</h3><p class="pre">'+html.escape(tr)+'</p>' if tr else ''}'''
    if fresh:
        why = f'<p class="note">{html.escape(FRESH_NOTE.get(aid, ""))}</p>'
    else:
        why = f'''<p class="note">{html.escape(IMGNOTE.get(aid, ""))}</p>{body}
  <h3>Dlaczego w top 10</h3>
  <ul><li><b>Kąt:</b> {html.escape(r["reasons"]["angle"])}</li><li><b>Fit:</b> {html.escape(r["reasons"]["fit"])}</li><li><b>Odtwarzalność:</b> {html.escape(r["reasons"]["repro"])}</li></ul>
  <h3>Jak to przepisać na VeluSkin</h3><p>{html.escape(ADAPT[aid][1])}</p>
  <details><summary>Wszystkie stwierdzenia konkurenta ({len(a.get("claims", []))}) — nieprzefiltrowane, do Twojej decyzji</summary><ul>{claims}</ul></details>'''
    b64 = img64(aid)
    media = f'<div class="media"><img src="data:image/jpeg;base64,{b64}" alt=""></div>' if b64 else '<div class="media"><span>brak klatki</span></div>'
    return f'''<article class="card{' fresh' if fresh else ''}">{media}<div class="body">
  <div class="rank">{head}</div><h2>{html.escape(NAMES.get(aid, aid))}</h2>
  <p class="meta">{html.escape(str(a.get("format", "")))} · ID {aid} · <a href="{SHARE.get(aid, "#")}" target="_blank" rel="noopener">otwórz w GetHookd ↗</a></p>
  {why}{body if fresh else ''}
</div></article>'''

cards = "".join(card(i, aid) for i, aid in enumerate(d["top10"], 1))
fresh = "".join(card(0, aid, fresh=True) for aid in d["fresh_hypotheses"])
page = f'''<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Top 10 sprawdzonych inspiracji — VeluSkin</title>
<style>
:root{{--bg:#faf6f2;--card:#fff;--ink:#2b2b2b;--muted:#6b6b6b;--accent:#f89080;--line:#eadfd8}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#1b1917;--card:#252220;--ink:#efe9e4;--muted:#a8a09a;--line:#3a3532}}}}
:root[data-theme=dark]{{--bg:#1b1917;--card:#252220;--ink:#efe9e4;--muted:#a8a09a;--line:#3a3532}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Poppins,system-ui,sans-serif;padding:24px 16px}}
header,section h1{{max-width:1100px;margin:0 auto 24px}}h1{{font-size:26px;margin:0 0 4px}}header p{{color:var(--muted);margin:0;max-width:1100px}}
.grid{{max-width:1100px;margin:0 auto 40px;display:grid;gap:20px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:grid;grid-template-columns:1fr}}
.card.fresh{{opacity:.85;border-style:dashed}}
@media(min-width:760px){{.card{{grid-template-columns:360px 1fr}}}}
.media{{background:#111;display:flex;align-items:center;justify-content:center;color:#888}}.media img{{width:100%;height:auto;display:block;max-height:640px;object-fit:contain}}
.body{{padding:18px 20px}}.rank{{font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--accent);font-weight:600}}
h2{{margin:4px 0 6px;font-size:21px}}h3{{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 2px}}
.meta,.note{{color:var(--muted);font-size:14px;margin:0 0 4px}}.pre{{white-space:pre-wrap;margin:0}}ul{{margin:4px 0;padding-left:20px}}
details{{margin-top:12px;font-size:14px}}summary{{cursor:pointer;color:var(--accent)}}a{{color:var(--accent)}}
</style></head><body>
<header><h1>Top 10 sprawdzonych inspiracji dla VeluSkin</h1><p>Rev. 2 — tylko reklamy, które rynek już zweryfikował: wynik GetHookd ≥ 61 (Growing / Optimized / Winning) albo ≥ 30 dni emisji. Ocena sędziego = pomysł względem pozycjonowania VeluSkin. Pełne wideo pod linkiem „otwórz w GetHookd”. Wszystkie stwierdzenia konkurencji bez filtra.</p></header>
<div class="grid">{cards}</div>
<section><h1 style="font-size:20px">Świeże hipotezy — dobre pomysły, jeszcze niesprawdzone (Testing, kilka dni)</h1></section>
<div class="grid">{fresh}</div>
</body></html>'''
(EX / "shortlist-gallery.html").write_text(page, encoding="utf-8")
print("md", len("\n".join(L)) // 1024, "KB; html", len(page) // 1024, "KB")
