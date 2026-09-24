# VeluSkin — Brand Brain (file-based)

Zamiennik „company brain" z Pletora: cały kontekst marki żyje tu jako pliki, które Claude Code
czyta przed każdym krokiem Ad Machine (spy → inspiracje → gate promptów → generacja → QA → kuracja).

Źródła: brief oferty, awatar klienta, łańcuch przekonań, Executive Summary (research) + dane właściciela
(Lekiro / lekiro.pl). Tam, gdzie research i właściciel się różnią, **decyzja właściciela jest nadrzędna**.

## Pliki

| Plik | Co zawiera | Kto to czyta w pipeline |
|---|---|---|
| `brand-core.csv` | Firma, Big Idea, nagłówek/podnagłówek, pozycjonowanie, obietnice, mechanizm (fakt vs hipoteza), ton, twarde zasady | Każdy krok; Jev `brand_context` |
| `products.csv` | Jeden produkt: 16 plastrów, 100% silikon, użycia, cennik 1/2/3, koszt użycia, dostawa/płatność/zwrot | Generacja (brief), Jev `brand_products` |
| `audiences.csv` | Segment główny 40–55 (usta / „11"), poboczne 35–44 i 50+, hipotezy; bóle, triggery, obiekcje, dowody, język | Inspiracje, generacja |
| `claims.csv` | **Claim sheet**: co wolno powiedzieć (K1–K9), co zakazane (K10–K16, K20–K23), co niezweryfikowane (K17–K19) | Gate promptów, QA outputów (`claim_risk`, `unsupported_claim`) |
| `belief-chain.csv` | 6 przekonań w kolejności, obiekcje, jak budować, gdzie, luki dowodowe | Storyboard kreacji, landing |
| `proof-assets.csv` | Lista materiałów dowodowych do nagrania (P1–P10) i co odblokowują | Produkcja przed skalowaniem |
| `copy-rules.csv` | Checklista copy C1–C19 (must/should) | Gate promptów, kuracja |
| `visual-universe.csv` | Zasady wizualne, paleta po nazwach, zakazy, formaty | Generacja, QA (`palette_on_brand`, `tone_match`) |
| `brand-kit.csv` | Sklep, firma, logo, paleta (nazwy + hex do produkcji), fonty, Canva kit | Generacja, QA (`logo_correct`) |
| `competitors.csv` | Konkurenci z researchu + GetHookd spy (id, tier, kąt, czego nie kopiować) | Krok 2–3 |
| `inspiration-set.csv` | 10 marek do ekstrakcji (5 direct + 5 adjacent) z URL FB | Krok 2–3 |
| `inspirations.csv` | Kąty reklamowe: 5 kierunków z briefu + kąty kategorii; status ready/blocked/banned | Krok 4–5 (2 produkty × 10 kreacji → u nas 1 produkt × 2 strefy) |
| `winning-creatives.csv` | Top 12 reklam VeluSkin z Meta (konto Pooa) z metrykami — benchmark i referencja, NIE do remiksu | Krok 4 |
| `creative-library.csv` | 15 unikalnych copy z konta + audyt claimów wg `claims.csv` / `copy-rules.csv` | Krok 4–5, write-back |
| `site-audit.csv` | Audyt strony produktu lekiro.pl vs brief/claim sheet (S1–S14) — do poprawy przed skalowaniem | Landing = część kreacji |
| `meta-images.csv` | Obrazy reklam VeluSkin w Meta (hash, wymiary, permalink) — do wyboru packshotu i reużycia przez API | Krok 6 |
| `campaign-learnings.csv` | Wnioski, hipotezy testowe, wyniki (write-back po każdym runie i po każdej odrzuconej kreacji) | Pętla zwrotna |
| `VeluSkin-Brand-Brain.pdf` | Skompilowany widok całości | Ludzie |
| `assets/` | logo-lekiro.png, packshot-veluskin-16-plastrow-a/b.png, ugc-ai-v1.1.mp4 (działający AI-UGC) | Generacja |

## Konwencja `status`
`confirmed` (właściciel/produkt) · `recommended` (brief) · `pattern` (wzorzec z researchu) · `hypothesis` (do testu) ·
`draft` / `draft_accepted` (propozycja) · `unverified` (liczba bez źródła — nie używać) · `missing` / `TODO` · `banned`.

## Jak pipeline używa mózgu
1. **Spy (krok 3)** — `inspiration-set.csv` + `competitors.csv` (kogo śledzić, czego nie kopiować).
2. **Jev shortlist (krok 4)** — `brand_context` = brand-core + audiences + belief-chain; `brand_products` = products.
3. **Gate promptów (krok 5)** — `copy-rules.csv` + `claims.csv` + `visual-universe.csv` zakazy.
4. **Generacja (krok 6)** — brand-core + visual-universe + brand-kit + products + assets/ = brief każdej kreacji; jedna kreacja = jeden kąt z `inspirations.csv`.
5. **QA outputów (krok 7)** — `brand_rules` = visual-universe + brand-kit (paleta po nazwach) + copy-rules; `claims.csv` dla `unsupported_claim`.
6. **Write-back** — każda odrzucona kreacja i każdy wynik testu → wiersz w `campaign-learnings.csv`.

## Odbudowa PDF
```
python3 build_brain_pdf.py
```
