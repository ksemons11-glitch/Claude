# VeluSkin — Brand Brain (file-based)

Zamiennik „company brain" z Pletora: cały kontekst marki żyje tu jako pliki, które Claude Code
czyta przed każdym krokiem Ad Machine (spy → inspiracje → generacja → kuracja).

## Pliki

| Plik | Co zawiera | Odpowiednik w Pletorze |
|---|---|---|
| `brand-core.csv` | Nazwa, kategoria, rynek, oferta, mechanizm, obietnica, ton, twarde zasady | Brand core |
| `audiences.csv` | Segmenty ICP: bóle, triggery, obiekcje, nawyki zakupowe | Identity → Audiences |
| `visual-universe.csv` | Tryby wizualne (studio/lifestyle), światło, typografia, zakazy, formaty | Identity → Visual universe |
| `brand-kit.csv` | Logo, kolory (hex), fonty, linki, Canva brand kit id | Identity → Brand kit |
| `products.csv` | SKU, umiejscowienie, cena, liczba użyć, claim, ścieżka do zdjęcia | Products |
| `competitors.csv` | Mapa konkurentów z GetHookd (id, tier, format, kąt) | Competitors / Brand spy |
| `inspiration-set.csv` | Krok 2 planu: 10 marek (5 direct + 5 adjacent) z URL stron FB do ekstrakcji | Inspiration set |
| `winning-creatives.csv` | Dawne kreacje, które działały — referencja dla Jev, NIE do remiksu | Existing ad creative |
| `inspirations.csv` | 10 zwycięskich kątów kategorii + ich re-voice dla VeluSkin (PL) | Inspirations |
| `copy-rules.csv` | Checklista copy (must/should) — JEV sprawdza każdą kreację | Campaign rules |
| `campaign-learnings.csv` | Czego się nauczyliśmy; wyniki testów | Campaign learnings |
| `VeluSkin-Brand-Brain.pdf` | Skompilowany, czytelny dokument z całości | Brain overview |
| `assets/` | Logo, packshoty, zdjęcia produktu (do wgrania) | Brand kit assets |

## Konwencja `status`
`confirmed` = potwierdzone z profilu/danych · `draft` = propozycja do akceptacji · `missing` / `TODO` = brakuje, uzupełnij · `generated` / `board` = kreacja istnieje / czeka w kolejce.

## Jak pipeline używa mózgu
1. **Spy** — `competitors.csv` (kogo śledzić, kogo nie kopiować).
2. **Inspiracje** — `inspirations.csv` (kąty ↔ re-voice PL).
3. **Generacja** — `brand-core` + `visual-universe` + `brand-kit` + `products` = brief każdej kreacji; jedna kreacja = jeden kąt.
4. **Kuracja (JEV)** — `copy-rules.csv` jako checklista pass/fail + `visual-universe.csv` zakazy.
5. **Learnings** — po każdym teście dopisz wiersz w `campaign-learnings.csv`.

## Odbudowa PDF
```
python3 build_brain_pdf.py
```
