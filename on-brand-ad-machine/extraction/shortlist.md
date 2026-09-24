# Krok 4 — shortlista: 90 reklam → top 10

Data: 2026-09-24. Sędzia: manualny (Claude w sesji, 4 typowane pytania z `gate/gate/schemas.py` na reklamę). Ranking w kodzie: `gate/gate/rank.py` (angle 0,45 / fit 0,40 / repro 0,15; odrzut gdy P(borrowed_ip) > 0,6; remis → wyższa średnia pewność sędziego). Odtworzenie: `python3 extraction/shortlist.py`.

Wejście: 90 reklam z 8 marek (`extraction/*.json`), 53 wideo z kolejki transkrypcji: 39 transkryptów, 13 bez mowy (sama muzyka), 1 „unavailable” (Eight Sleep 125821396). Koszt kroku 4: 0 kredytów GetHookd. Yope i Resibo bez aktywnych reklam (decyzja: nie dobieramy marek na siłę).

Oceny są oceną POMYSŁU względem pozycjonowania VeluSkin (brain/brand-core.csv), nie jakości wykonania konkurenta. Wszystkie stwierdzenia konkurencji zostały zachowane w polu `claims` bez filtrowania — co użyć, decyduje właściciel.

## Top 10

| # | ID | Reklama | Wynik | Kąt / Fit / Repro | Rola u nas |
|---|---|---|---|---|---|
| 1 | 180682320 | SiO — „Rytuał, nie naprawa” | 1.000 | 2 / 2 / 2 | Retargeting / cold A1 |
| 2 | 181080083 | SoSmooth — „1,05 $ za noc” | 1.000 | 2 / 2 / 2 | Retargeting / value (inspirations #6) |
| 3 | 181482577 | Scarlette — „Taśma na twarzy? Serio?” | 1.000 | 2 / 2 / 2 | Cold — hook 7 s przed AI-UGC |
| 4 | 174013810 | SoSmooth — „8 nocy, jeden plaster” (podkład wsiąka w linie) | 1.000 | 2 / 2 / 2 | Cold — strefa (inspirations #2 i #3) |
| 5 | 181080114 | SoSmooth — „Myślałam, że to bajer” | 1.000 | 2 / 2 / 2 | Cold / remarketing — edytorski statyk |
| 6 | 177231372 | SiO — „Jedyna rzecz, którą daję sobie” | 0.800 | 2 / 1 / 2 | Remarketing — linia emocjonalna |
| 7 | 177231360 | SiO — „Trzyma skórę płasko, gdy śpisz” | 0.775 | 1 / 2 / 2 | Cold A2 (profilaktyka) / remarketing #4 |
| 8 | 149861556 | SoSmooth — „~1,50 $ za użycie. Udowodnione, nie obiecane” | 0.775 | 1 / 2 / 2 | Cold A2 / value statyk |
| 9 | 157292606 | Scarlette — „Moje 11 sprawiały, że wyglądałam na złą” | 0.725 | 2 / 1 / 1 | Cold — strefa „11” (hipoteza #3) |
| 10 | 181332804 | SiO — „Śpisz na boku? To tłumaczy coś…” | 0.725 | 2 / 1 / 1 | Cold — edukacja przyczyną |

## Dlaczego te i jak je przepisać na VeluSkin

### 1. SiO — „Rytuał, nie naprawa” (`180682320`, SiO Beauty, dpa/carousel 6 images, Testing (28), 6 dni)

- **Kąt:** „Niektóre rzeczy działają jako rytuał, nie jako naprawa. Jeden plaster, co noc. Mało i konsekwentnie.” — odwrotność „efekt od 1. nocy”; rzadkie w kategorii
- **Fit:** Dokładnie nasz ton (dorosły, spokojny), K4 (2–3×/tyg.), zero claimów, zero botoksu — wprost wzmacnia „nocne wsparcie tam, gdzie widzisz linie”
- **Odtwarzalność:** Katalog/statyk z packshotem — mamy packshoty; jedno zdanie copy
- **Adaptacja:** „Nie efekt od pierwszej nocy. Rytuał 2–3 razy w tygodniu, dokładnie tam, gdzie widzisz linie.” Statyk z packshotem + plaster NA strefie. Zero claimów — najbezpieczniejszy kąt w zestawie; jednocześnie odpowiedź na badge K12 z opakowania.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Some things work best as a ritual, not a fix • One patch, worn while you sleep, every night • Small and consistent • Hydroseal range: Chest, FaceLift, Lip, Eye, Eye & Smile, Forehead

### 2. SoSmooth — „1,05 $ za noc” (`181080083`, SoSmooth Skincare, video 28s, Testing (1), 4 dni)

- **Kąt:** „$30 brzmi drogo, dopóki nie policzysz” → $1,05 za noc + „tańsze niż taśma, którą wszyscy polecają, i naprawdę trzyma się skóry” — matematyka + obiekcja przyczepności
- **Fit:** K8 (≈0,19 zł/użycie), K3 (do 20 użyć), przyczepność (#5), ton rzeczowy; bez botoksu; tylko „medical grade” do wycięcia
- **Odtwarzalność:** POV dłoń z plastrem nad umywalką + napis — najprostsze ujęcie w zestawie
- **Adaptacja:** POV: dłoń z plastrem nad umywalką, napis „około 19 groszy za noc”. Copy: „59,90 zł brzmi drogo, dopóki nie policzysz: 16 plastrów × ok. 20 użyć.” + „płuczesz, suszysz, naklejasz ponownie — i trzyma”. Claimy K3/K8; bez „medical grade”.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Thirty dollars for one patch sounds steep until you do the maths • Medical grade silicone • Rinse in cold water and use again, up to 20 times • 5-pack: $21 a patch • $1.05 a night • Cheaper per night than the tape people keep recommending • … (+2)

### 3. Scarlette — „Taśma na twarzy? Serio?” (`181482577`, Scarlette, video 7s, Testing (14), 3 dni)

- **Kąt:** Obiekcja jako hook: „Taśma na twarzy? Serio?” + „już przerobiłaś pół szafki kosmetyków na te linie” — 7 s, konkretny pomysł
- **Fit:** Wprost nasze przekonanie „nie kolejny krem” + sceptyczna A1 + strefa; ton dorosły, bez claimów, bez botoksu
- **Odtwarzalność:** Postać UGC z ręcznikiem w łazience wskazująca strefę — 1:1 z naszym ugc_character
- **Adaptacja:** Postać UGC z ręcznikiem wskazuje usta/„11”: „Plaster na twarz? Serio?” → „Zwłaszcza gdy przerobiłaś już pół szafki kremów na te linie. Zobacz, zanim to skreślisz.” Idealne otwarcie dla przekonania #1 „nie kolejny krem”.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Tape on my face? Really? (objection hook) • You've already tried a bathroom cabinet's worth of skincare for forehead lines • Watch this before you rule it out • "face taping will do nothing against your wrinkles!" (on-screen objection)

### 4. SoSmooth — „8 nocy, jeden plaster” (podkład wsiąka w linie) (`174013810`, SoSmooth Skincare, video 39s, Scaling (41), 17 dni)

- **Kąt:** Trigger makijażu („podkład wsiąka w dwie linie między brwiami”) + „8 nocy, jeden plaster” + raport klientek zamiast obietnicy
- **Fit:** Dokładnie inspirations #2 (makijaż podkreśla linie) i #3 („11”); „klientki mówią nam” = źródłowany dowód jak K19; bez botoksu; „medical grade” do wycięcia
- **Odtwarzalność:** Blondynka w łazience przyciska plaster na czoło + napis = nasz ugc_character 1:1
- **Adaptacja:** „Podkład rano leży dobrze, a o 11 siedzi w liniach wokół ust / między brwiami.” Postać UGC przyciska plaster w łazience; „nie chciałam innej twarzy, chciałam, żeby makijaż leżał płasko”; „trzyma się — śpię na boku”; dowód: „w ankiecie naszych klientek 89%…” (K19 wording). Najbliższa nasza brief-kreacja.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Foundation settling into the two lines between your brows • One Forehead Patch, medical grade silicone, worn overnight • Eight nights in, finer frown lines look softer (customers tell us) • Makeup sits flatter • Rinse and reuse up to 20 times • Any 5 patches, $21 each • … (+2)

### 5. SoSmooth — „Myślałam, że to bajer” (`181080114`, SoSmooth Skincare, image, Testing (1), 4 dni)

- **Kąt:** Dialog sceptyczek („myślałam, że to bajer” / „też, sądziłam, że to taśma”) + edytorski wyjaśniacz „To nie taśma. Oto, co silikon naprawdę robi” + zwrot „jeśli się mylę”
- **Fit:** Sceptyczna A1, mechanizm prostym językiem („zatrzymuje wilgoć, delikatnie podpiera skórę” = C20), zwrot jako trust (#8); „medical-grade” i 40% off do wycięcia
- **Odtwarzalność:** Edytorski statyk z rysunkiem liniowym + packshot — wykonalny w Canva
- **Adaptacja:** Dwie kwestie sceptyczek + rysunek liniowy twarzy + tytuł „To nie taśma. Oto, co silikon naprawdę robi” + 2 zdania mechanizmu (C20) + „Zwrot w 14 dni, jeśli się mylę”. Bez rabatu i bez „medical-grade”.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** I thought they were a gimmick / glorified sticky tape • Wore them overnight and forehead looked visibly smoother by morning • Face Plumping Duo now 40% off at $36 • 30-day returns • It is not tape • Soft silicone patch holds in moisture and gently supports the skin • … (+4)

### 6. SiO — „Jedyna rzecz, którą daję sobie” (`177231372`, SiO Beauty, dpa/carousel 6 images, Scaling (48), 12 dni)

- **Kąt:** „Daję wszystko wszystkim cały dzień. To jedyna rzecz, którą daję sobie.” — emocja opiekunki, bez claimu
- **Fit:** Ton i A1 (40–55) pasują; brak strefy/mechanizmu — użyteczne jako linia w remarketingu, nie jako samodzielny kąt cold
- **Odtwarzalność:** Katalog + jedno zdanie — packshoty są
- **Adaptacja:** Jedno zdanie do karuzeli/packshotu: „Cały dzień dajesz wszystko wszystkim. To jedna rzecz wieczorem tylko dla Ciebie.” Uwaga: brak strefy i mechanizmu — tylko jako dodatek do kreacji z przekonaniami 1–4, nie samodzielny cold.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** I give everything to everyone all day long; this is the one thing I give to myself • Hydroseal range: FaceLift, Forehead, Eye, Eye & Smile, Lip, Chest

### 7. SiO — „Trzyma skórę płasko, gdy śpisz” (`177231360`, SiO Beauty, dco/carousel 2 images + video 12s, Testing (38), 11 dni)

- **Kąt:** „Trzyma skórę płasko, gdy śpisz. Jeden krok więcej wieczorem.” — mechanizm w jednym zdaniu
- **Fit:** C20 (mechanizm prostym językiem), C1 (jedna propozycja), rytuał wieczorny, bez claimów o efekcie
- **Odtwarzalność:** Statyk/krótki klip z plastrem NA strefie — mamy zasoby
- **Adaptacja:** „Trzyma skórę na wybranej strefie i pomaga zachować wilgoć przez noc. Jeden krok więcej wieczorem.” Transkrypt oryginału to kąt profilaktyczny („nie mam jeszcze widocznych linii i chcę, żeby tak zostało”) — pasuje do A2 35–44.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** One more step at night • SiO holds your chest skin flat while you sleep

### 8. SoSmooth — „~1,50 $ za użycie. Udowodnione, nie obiecane” (`149861556`, SoSmooth Skincare, image, Optimized (86), 37 dni)

- **Kąt:** „Zawsze chciałaś spróbować, ale nie wiedziałaś, czy warto?” + ~$1,50/użycie + „Proven, not promised”
- **Fit:** K8 + K3 + niezdecydowana debiutantka (A2) + „udowodnione, nie obiecane” ≈ „pokaż, nie obiecuj”; tylko „medical-grade” do wycięcia
- **Odtwarzalność:** Prosty statyk z packshotem i ceną za użycie — 1:1 z inspirations #6
- **Adaptacja:** „Zawsze chciałaś sprawdzić plastry, ale nie wiedziałaś, czy warto? Do ok. 20 użyć. Około 19 groszy za noc.” Prosty statyk z packshotem w ciepłej bieli; „Udowodnione, nie obiecane” → u nas „Pokażemy zamiast obiecywać” + link do opinii (K17).
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Always wanted to try wrinkle patches but weren't sure they were worth it? • Reusable up to 20 times • About $1.50 a use • 100% medical-grade silicone • Proven, not promised • Fast-acting; safe for all skin types • … (+1)

### 9. Scarlette — „Moje 11 sprawiały, że wyglądałam na złą” (`157292606`, Scarlette, image, Growing (61), 31 dni)

- **Kąt:** Historia „moje 11 sprawiały, że wyglądałam na złą — w pracy pytali, czy wszystko OK” — konkretna emocja strefy; odwołana konsultacja
- **Fit:** Rdzeń (11 + „wyglądam na złą”) = nasza hipoteza #3; ale 3× botoks, „medical-grade”, „40x wilgoci”, „po jednej nocy” — do wycięcia (C3/C4/C5/C8)
- **Odtwarzalność:** Statyk z packshotem tak; taca medyczna = banned_visuals → zamienić na łazienkę
- **Adaptacja:** Historia: „W pracy pytali, czy wszystko OK. Było OK — tylko te dwie linie między brwiami tak wyglądały.” Wyciąć: botoks ×3, medical-grade, „40× wilgoci”, „po jednej nocy”, tacę medyczną. Zostaje emocja strefy + odstawiona decyzja o zabiegu (bez nazywania botoksu).
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** My 11s made me look angry when I was happy • Looked into Botox, booked the consultation, cancelled it three times • Needles in the forehead and losing natural expression didn't sit right • Medical-grade silicone that plastic surgeons have quietly used for over 40 years • Not a cream, not a serum • Physically retrains your facial muscles while you sleep • … (+6)

### 10. SiO — „Śpisz na boku? To tłumaczy coś…” (`181332804`, SiO Beauty, dco/carousel 2 images + video 32s, Testing (16), 4 dni)

- **Kąt:** Insight przyczyny: „śpisz na boku? to tłumaczy coś, czego nigdy nie połączyłaś” — edukacja przyczyną, nie produktem
- **Fit:** Struktura „ukryta przyczyna → mechanizm” pasuje (brief: edukować w 1–2 zdaniach); przyczyna u nas inna (mimika, makijaż, sucha skóra) — bez straszenia (C14)
- **Odtwarzalność:** Talking-head AI-UGC wykonalny; trzeba własnego, uczciwego „dlaczego” bez claimów
- **Adaptacja:** Szkielet „nikt Ci nie mówi, że… → mechanizm → rano” do przepisania na naszą, uczciwą przyczynę: linie wokół ust pogłębia sucha skóra + mimika + makijaż, nie „wiek”. Bez straszenia (C14); mechanizm = „zachowuje wilgoć pod plastrem”.
- **Claimy konkurenta (nieprzefiltrowane, do decyzji właściciela):** Do you sleep on your side? This might explain something you've never connected • Nobody tells you that how you sleep folds the same skin nightly • The side-sleeping secret nobody explains • Why did no one tell me? (on-screen)

## Co wypadło i dlaczego

- **20 reklam odrzuconych za pożyczone IP** (P > 0,6): Wrinkles Schminkles (7 — cały push „Now at Ulta / Boots” + Shark Tank), 111SKIN (9 — założyciel-chirurg, The Plaza, Byrdie, NYFW/Harrods/Proenza Schouler), Hers (3 — Wegovy/Zepbound/Ozempic), Eight Sleep (1 — afiliacyjna redakcja). Wniosek: dwaj najwięksi konkurenci bezpośredni opierają obecne kampanie na dystrybucji i autorytecie, których nie mamy — nasz odpowiednik to trust „Lekiro, Gostynin, zwrot 14 dni, BLIK/pobranie” (inspirations #8).
- **Botoks jako oś** (fit = 0): Scarlette 6/10, SoSmooth 4/14, WS 2/10. Najczęstszy wzorzec kategorii i jednocześnie zakazany przez brief (C4). Kilka z nich ma dobre ELEMENTY (np. „odwołałam konsultację” w 157292606) — użyte tylko po wycięciu porównania.
- **Rabat/kotwica/urgency** (C6): Scarlette „60% OFF” ×5, SoSmooth 40–50%, Glossier „value $114 → $97”. Realna oszczędność 2-paku (K9) zostaje jako lockup, nie jako hook.
- **Marki sąsiednie**: Eight Sleep dał 1 pomysł formatu (karta „raport nocy” 143124227 — miejsce 12), Hers 1 hook (odwrócona obiekcja „3 powody, dla których NIENAWIDZĘ…” 173665393 — miejsce 14), Glossier tylko wzorzec „demo + komentarz klientki” (180667103). Reszta neutralna lub poza marką.
- **Miejsca 11–14 (0,725, poza top 10):** 119368742 SiO (przyczyna → mechanizm → rano), 143124227 Eight Sleep (karta raportu), 177231362 SiO („Bluzka, którą znów noszę”), 173665393 Hers (odwrócona obiekcja). Do wykorzystania w kroku 5 jako warianty hooków.

## Co z tego wynika dla kroku 5 (prompty)

1. Pięć reklam z pełnym wynikiem 1,0 to pięć szkieletów bez botoksu, bez procentów, z jednym pomysłem: **matematyka za noc**, **trigger makijażu + strefa**, **obiekcja „plaster na twarz?”**, **„rytuał, nie naprawa”**, **dialog sceptyczek + wyjaśniacz**. Prompty na 2 strefy (usta / „11”) budujemy z nich, nie ze starych winnerów (hard_rule_1).
2. Każda z 10 wymaga wycięcia „medical-grade” (C3) — to jedyny wspólny konflikt; potwierdza decyzję „100% silikon”.
3. Dowód w top 10 to zawsze „klientki mówią nam / w ankiecie” albo „sprawdź rano” — nigdy „klinicznie”. Nasz K19 (ankieta 87%/89%) i K17 (1558 opinii) wystarczą, jeśli zapisane z „w ankiecie”.
4. Format: 6/10 to statyk lub katalog z packshotem (mamy zasoby), 4/10 to UGC z postacią w łazience (mamy `ugc_character`). Nic w top 10 nie wymaga PRZED/PO — P1/P2 nadal brakuje, ale nie blokuje batcha 1.
