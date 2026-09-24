# Krok 4 — shortlista: 90 reklam → top 10 SPRAWDZONYCH

Data: 2026-09-24 (rev. 2 — po uwadze właściciela: „co to za sprawdzone adsy, które chodzą od paru dni”). Sędzia: manualny (4 typowane pytania z `gate/gate/schemas.py`). Ranking w kodzie `gate/gate/rank.py`: angle 0,45 / fit 0,40 / repro 0,15; odrzut gdy P(borrowed_ip) > 0,6; **bramka „sprawdzone”: performance_score >= 61 or days_active >= 30** (GetHookd: Growing 61 / Optimized 81 / Winning 91+); remis → wyższy wynik platformy. Odtworzenie: `python3 extraction/shortlist.py && python3 extraction/shortlist_report.py`.

Wejście: 90 reklam z 8 marek, 53 wideo z transkrypcją (39 gotowych, 13 bez mowy, 1 niedostępny). Koszt kroku: 0,2 kredytu GetHookd (pobranie klatek). Oceny dotyczą POMYSŁU względem pozycjonowania VeluSkin; wszystkie stwierdzenia konkurencji zostały w polu `claims` bez filtrowania — decyduje właściciel.

## Top 10 (sprawdzone przez rynek)

| # | ID | Reklama | Perf. | Dni | Wynik sędziego | Kąt / Fit / Repro | Rola u nas |
|---|---|---|---|---|---|---|---|
| 1 | 149861556 | SoSmooth — „Zawsze chciałaś spróbować? ~1,50 $ za użycie” | Optimized (86) | 37 | 0.775 | 1 / 2 / 2 | Cold A2 / value statyk |
| 2 | 119368742 | SiO — „Śpisz na boku? Skóra składa się w tym samym miejscu” (DCO) | Optimized (86) | 77 | 0.725 | 2 / 1 / 1 | Cold — przyczyna → mechanizm → rano (nasz wzorzec) |
| 3 | 143124227 | Eight Sleep — karta „raport nocy” (Autopilot recap) | Optimized (81) | 45 | 0.725 | 2 / 1 / 1 | Format dowodu (remarketing) |
| 4 | 173665393 | Hers — „3 powody, dla których NIENAWIDZĘ minoxidilu” (odwrócona obiekcja) | Optimized (81) | 22 | 0.725 | 2 / 1 / 1 | Hook cold (odwrócona obiekcja) |
| 5 | 157292606 | Scarlette — „Moje 11 sprawiały, że wyglądałam na złą” | Growing (61) | 31 | 0.725 | 2 / 1 / 1 | Cold — strefa „11” (hipoteza #3) |
| 6 | 128944655 | SiO — „Obudziłam się w szoku, jak gładko” (DCO, Winning) | Winning (100) | 65 | 0.575 | 1 / 1 / 2 | UGC 13 s — szkielet winnera |
| 7 | 149861557 | SoSmooth — „Plaster na każdą linię” (makro odklejania) | Winning (100) | 37 | 0.575 | 1 / 1 / 2 | Demo makro (cold i remarketing) |
| 8 | 119368763 | SiO — „Zmarszczki nie czekają. Bez kremów, bez rutyny.” (Winning) | Winning (100) | 77 | 0.575 | 1 / 1 / 2 | UGC 21 s — „bez kremów” (Winning) |
| 9 | 133043224 | SiO — „Ten plaster obudził mnie w szoku” (wersja pojedyncza) | Optimized (86) | 52 | 0.575 | 1 / 1 / 2 | Wariant #6 |
| 10 | 124333814 | SiO — „Nocna poprawka dla śpiących na boku” | Growing (61) | 73 | 0.575 | 1 / 1 / 2 | Cold — „dociska i nawilża” w 11 s |

## Dlaczego te i jak je przepisać na VeluSkin

### 1. SoSmooth — „Zawsze chciałaś spróbować? ~1,50 $ za użycie” (`149861556`, image, Optimized (86), 37 dni)

- **Kąt:** „Zawsze chciałaś spróbować, ale nie wiedziałaś, czy warto?” + ~$1,50/użycie + „Proven, not promised”
- **Fit:** K8 + K3 + niezdecydowana debiutantka (A2) + „udowodnione, nie obiecane” ≈ „pokaż, nie obiecuj”; tylko „medical-grade” do wycięcia
- **Odtwarzalność:** Prosty statyk z packshotem i ceną za użycie — 1:1 z inspirations #6
- **Adaptacja:** „Zawsze chciałaś sprawdzić plastry, ale nie wiedziałaś, czy warto? Do ok. 20 użyć. Około 19 groszy za noc.” Statyk z packshotem w ciepłej bieli; „Proven, not promised” → „Pokażemy zamiast obiecywać” + „ponad 1500 opinii, 4,7/5” (K17). Wyciąć „medical-grade”.
- **Claimy konkurenta (nieprzefiltrowane):** Always wanted to try wrinkle patches but weren't sure they were worth it? • Reusable up to 20 times • About $1.50 a use • 100% medical-grade silicone • Proven, not promised • Fast-acting; safe for all skin types • … (+1)

### 2. SiO — „Śpisz na boku? Skóra składa się w tym samym miejscu” (DCO) (`119368742`, dco/carousel 6 videos 11s, Optimized (86), 77 dni)

- **Kąt:** Przyczyna („skóra składa się w tym samym miejscu co noc — linie się sumują”) → mechanizm (dociska, nawilża) → rano
- **Fit:** Szkielet identyczny z naszym wzorcem (hook → mechanizm → dowód); „medical-grade” i przyczyna do zamiany na własną
- **Odtwarzalność:** 6 klipów 11 s — potrzebna własna, uczciwa przyczyna dla ust/„11”
- **Adaptacja:** 11 s, talking-head w łazience: „[uczciwa przyczyna] → to VeluSkin → 100% silikon, wielorazowy, pomaga zachować wilgoć przez noc”. U nas przyczyna dla ust/„11”: mimika + sucha skóra + makijaż, bez straszenia (C14). 6 wariantów DCO = ten sam skrypt, różne ujęcia — łatwe do AI-UGC.
- **Transkrypt:** I'm a side sleeper, so my skin was basically folding in the same spot every night. This is the CO Chest Patch. It's a reusable medical grade silicone patch that helps gently compress and hydrate the skin while you sleep.
- **Claimy konkurenta (nieprzefiltrowane):** As a side sleeper your skin folds in the same spot every night, creating lines that add up over time • Reusable, medical-grade silicone patch • Gently compresses and hydrates your skin while you sleep • Wake up smoother

### 3. Eight Sleep — karta „raport nocy” (Autopilot recap) (`143124227`, image, Optimized (81), 45 dni)

- **Kąt:** Karta „Autopilot recap” — nocny raport (24 korekty, +20% deep sleep) jako dowód zamiast obietnicy; pomysł „pokaż noc w liczbach”
- **Fit:** Adaptowalne jako „karta poranka” (wieczór → rano), ale liczby u nas muszą mieć źródło (C5); inna kategoria
- **Odtwarzalność:** Format karty da się odtworzyć; brak danych = zastąpić checklistą rytuału
- **Adaptacja:** Karta „raport” na packshocie/wideo: zamiast „+20% deep sleep” — checklista rytuału: „wieczór: naklejone / rano: nadal na miejscu / płukanie: 1 z ~20”. Liczby tylko ze źródłem (C5); to wzorzec wizualny, nie copy.
- **Claimy konkurenta (nieprzefiltrowane):** Pod 5 transforms any bed into an intelligent, adaptive environment • Automatically adjusts temperature, elevation and sound • Maximize sleep performance and optimize health • Autopilot made 24 adjustments to elevation and temperature (on-image) • Deep sleep +20% (on-image) • Snoring -36% (on-image) • … (+1)

### 4. Hers — „3 powody, dla których NIENAWIDZĘ minoxidilu” (odwrócona obiekcja) (`173665393`, video 35s, Optimized (81), 22 dni)

- **Kąt:** Hook odwrócony: „3 powody, dla których NIENAWIDZĘ minoxidilu” → sprzedaje ten sam składnik; obiekcja jako otwarcie
- **Fit:** Struktura (obiekcja → wyjaśnienie) pasuje do sceptycznej A1; treść medyczna i lektor AI z disclaimerem — nie do przeniesienia 1:1
- **Odtwarzalność:** AI-UGC + napisy wykonalne; potrzebne własne 3 obiekcje (odpada, klej, „to tylko plaster”)
- **Adaptacja:** „3 powody, dla których NIE wierzyłam w plastry na zmarszczki” → 1. odpadają w nocy (u mnie trzymały), 2. to tylko taśma (nie: 100% silikon zatrzymuje wilgoć), 3. jeden plaster = jedno użycie (do ~20). Postać UGC, napisy, bez lektora AI z disclaimerem.
- **Transkrypt:** 3 Reasons Why I Hate Minoxidil for Hair Regrowth 1. Minoxidil is an ingredient used to regrow hair in 3-6 months, and I'm already seeing growth. 2. I get so many compliments on how thick and voluminous my hair looks. 3. My hairstylist keeps asking what I'm using. She can't believe it's real hair growth and not extensions. I just take one prescription Minoxidil hair vitamin a day, through hers. The
- **Claimy konkurenta (nieprzefiltrowane):** Stop hair loss in its tracks • Thicker, fuller hair in 3-6 months with minoxidil • Range of treatment options tailored to your hair needs • Minoxidil shown to regrow hair in 3-6 months (based on studies of oral minoxidil up to 2.5 mg/day) • Personalized plans starting at $35/month with a 5-month plan paid upfront • Hair Blends are compounded and not FDA approved/evaluated • … (+9)

### 5. Scarlette — „Moje 11 sprawiały, że wyglądałam na złą” (`157292606`, image, Growing (61), 31 dni)

- **Kąt:** Historia „moje 11 sprawiały, że wyglądałam na złą — w pracy pytali, czy wszystko OK” — konkretna emocja strefy; odwołana konsultacja
- **Fit:** Rdzeń (11 + „wyglądam na złą”) = nasza hipoteza #3; ale 3× botoks, „medical-grade”, „40x wilgoci”, „po jednej nocy” — do wycięcia (C3/C4/C5/C8)
- **Odtwarzalność:** Statyk z packshotem tak; taca medyczna = banned_visuals → zamienić na łazienkę
- **Adaptacja:** Historia w copy: „W pracy pytali, czy wszystko OK. Było OK — tak wyglądały te dwie linie między brwiami.” Wyciąć botoks ×3, medical-grade, „40× wilgoci”, „po jednej nocy”, tacę medyczną (banned_visuals). Statyk: plaster między brwiami w łazience.
- **Claimy konkurenta (nieprzefiltrowane):** My 11s made me look angry when I was happy • Looked into Botox, booked the consultation, cancelled it three times • Needles in the forehead and losing natural expression didn't sit right • Medical-grade silicone that plastic surgeons have quietly used for over 40 years • Not a cream, not a serum • Physically retrains your facial muscles while you sleep • … (+6)

### 6. SiO — „Obudziłam się w szoku, jak gładko” (DCO, Winning) (`128944655`, dco/carousel 6 videos 13s, Winning (100), 65 dni)

- **Kąt:** „Linie robiły się coraz gorsze → znalazłam plaster → rano szok” + „gruby, wygodny, wielorazowy”
- **Fit:** Cechy fizyczne (wygodny, wielorazowy) wzmacniają #5; „szok rano” = obietnica efektu bez dowodu
- **Odtwarzalność:** 6 klipów UGC 13 s — wykonalne z AI-UGC
- **Adaptacja:** Winning (100) od 65 dni: problem → znalazłam → rano → cechy (gruby, wygodny, wielorazowy) → CTA. U nas: „linie wokół ust przeszkadzały mi w makijażu → VeluSkin na noc → rano sprawdzam tę samą strefę → 100% silikon, wielorazowy” — bez „szok/one night” (K12), z „sprawdź rano”.
- **Transkrypt:** My chest lines were starting to get so bad. That's when I found CO-Hydrocele chest patches for overnight use. I woke up and I was shocked by how much smoother my skin looked. The patch is thick, it's comfortable, it's reusable. Try CO-Hydrocele chest patch today.
- **Claimy konkurenta (nieprzefiltrowane):** My chest lines were starting to get so bad • Found the SiO chest patch for overnight use • Woke up shocked by how much smoother my skin looked • Thick, comfortable, and reusable • Try it tonight

### 7. SoSmooth — „Plaster na każdą linię” (makro odklejania) (`149861557`, video 24s, Winning (100), 37 dni)

- **Kąt:** Ekstremalne makro odklejania plastra spod oka + „plaster na każdą linię” + made in Australia
- **Fit:** Makro-demonstracja i lokalność (#8 „Lekiro, Polska”) pasują; „jak po zastrzykach”, 87% vs zastrzyki, medical-grade — nie
- **Odtwarzalność:** Makro odklejania plastra — proste ujęcie
- **Adaptacja:** Ekstremalne zbliżenie odklejania plastra z okolic ust/„11” + jedno zdanie. „Made in Australia” → „Lekiro, Polska” (#8). Wyciąć „87% vs zastrzyki”, „medical-grade”, „jak po zastrzykach”.
- **Transkrypt:** These patches are targeting fine lines and results can be seen just after one hour. They are made with 100% medical grade silicone which stimulates blood circulation and boosts collagen production. You can either wear them after your skincare, before you go out or even overnight. For even better results I recommend using them while you sleep. The best part is that these patches can be reused for u
- **Claimy konkurenta (nieprzefiltrowane):** "It's like I've had injectables. My skin feels so much smoother." (real customer) • One of 200,000+ customers • 87% of users prefer our patches over injectables • Medical-grade silicone • Reusable up to 20 times • Made in Australia • … (+1)

### 8. SiO — „Zmarszczki nie czekają. Bez kremów, bez rutyny.” (Winning) (`119368763`, video 21s (2 media), Winning (100), 77 dni)

- **Kąt:** „Zmarszczki nie czekają, więc nasze plastry też nie. Bez kremów, bez rutyny.”
- **Fit:** „Bez kremów” = nie kolejny krem (+); „just results while you sleep” = obietnica, „don't wait” = presja (C6/C14)
- **Odtwarzalność:** Postać w szlafroku przyciska plaster — wykonalne
- **Adaptacja:** Kobieta w szlafroku przyciska plaster: „Bez kolejnego kremu, bez rutyny. Naklejasz na noc na wybraną strefę.” To nasz kąt #1 „nie kolejny krem” w wersji, która u SiO wygrywa od 77 dni. Bez „zmarszczki nie czekają” (C14) i bez „just results” (C15).
- **Transkrypt:** If you wake up with chest creases, this is what I'd try. I'm a side sleeper, so my skin was basically folding in the same spot every night. This is the CO chest patch. It's a reusable medical grade silicone patch that gently compresses and hydrates the skin while you sleep. If your chest is the one area your skincare routine keeps missing, try the CO chest hydrosil patch.
- **Claimy konkurenta (nieprzefiltrowane):** Chest wrinkles don't wait, so our patches don't either • Apply before bed, wake up to visibly smoother, hydrated skin • No creams, no routine • Just results while you sleep • Overnight chest smoothing

### 9. SiO — „Ten plaster obudził mnie w szoku” (wersja pojedyncza) (`133043224`, video 13s, Optimized (86), 52 dni)

- **Kąt:** Ta sama kreacja co 182246289 (poranny reveal)
- **Fit:** Jak 182246289 — „one night” do przepisania
- **Odtwarzalność:** Jak 182246289
- **Adaptacja:** Ta sama kreacja co 128944655 w wersji pojedynczej (52 dni, Optimized) — potwierdza, że szkielet działa w obu formatach; dla nas jeden skrypt, dwa cięcia (DCO 6 ujęć + pojedyncze).
- **Transkrypt:** My chest lines were starting to get so bad. That's when I found CO-Hydrocele chest patches for overnight use. I woke up and I was shocked by how much smoother my skin looked. The patch is thick, it's comfortable, it's reusable. Try CO-Hydrocele chest patch today.
- **Claimy konkurenta (nieprzefiltrowane):** Woke up shocked how smooth my chest looked • One night with the SiO patch • My overnight routine to smooth chest wrinkles (on-screen)

### 10. SiO — „Nocna poprawka dla śpiących na boku” (`124333814`, video 11s (2 media), Growing (61), 73 dni)

- **Kąt:** „Nocna poprawka dla śpiących na boku” + „dociska i nawilża”
- **Fit:** Mechanizm „dociska i nawilża” jest OK (C20); „medical-grade” do wycięcia (C3)
- **Odtwarzalność:** Blondynka ~45 w łazience z plastrem = nasz ugc_character
- **Adaptacja:** Najkrótszy skrypt w puli: „jestem X → to VeluSkin → wielorazowy plaster ze 100% silikonu, który pomaga zachować wilgoć w skórze przez noc”. Mechanizm C20 w jednym zdaniu; blondynka ~45 w łazience = nasz ugc_character.
- **Transkrypt:** I'm a side sleeper, so my skin was basically folding in the same spot every night. This is the CO Chest Patch. It's a reusable medical grade silicone patch that helps gently compress and hydrate the skin while you sleep.
- **Claimy konkurenta (nieprzefiltrowane):** Reusable medical-grade silicone • Compresses and hydrates your chest skin while you sleep • Wake up smoother, starting tonight • The overnight fix for side sleepers

## Świeże hipotezy (dobry pomysł wg sędziego, ale NIE sprawdzone: Testing / kilka dni)

Nie są inspiracją do batcha 1. Sprawdzić ponownie za 2–3 tygodnie (GetHookd brand spy na SoSmooth / SiO / Scarlette); jeśli przejdą do Growing+, wchodzą do puli.

- `180682320` SiO — „Rytuał, nie naprawa” — „rytuał, nie naprawa” — 6 dni, Testing (28)
- `181080083` SoSmooth — „1,05 $ za noc” — matematyka za noc (K8) — 4 dni, Testing (1)
- `181482577` Scarlette — „Taśma na twarzy? Serio?” — obiekcja „taśma na twarzy?” jako hook 7 s — 3 dni, Testing (14)
- `174013810` SoSmooth — „8 nocy, jeden plaster” — trigger makijażu + strefa — 17 dni, Scaling (41), najbliżej progu
- `181080114` SoSmooth — „Myślałam, że to bajer” — dialog sceptyczek + wyjaśniacz — 4 dni, Testing (1)
- `177231372` SiO — „Jedyna rzecz, którą daję sobie” — linia emocjonalna — 12 dni, Scaling (48)
- `177231360` SiO — „Trzyma skórę płasko, gdy śpisz” — mechanizm w jednym zdaniu / profilaktyka — 11 dni, Testing (38)
- `181332804` SiO — „Śpisz na boku? To tłumaczy coś…” — edukacja przyczyną — 4 dni, Testing (16)
- `177231362` SiO — „Bluzka, którą znów noszę” — wynik behawioralny zamiast claimu — 11 dni, Testing (38)

## Co wypadło i dlaczego

- **20 reklam za pożyczone IP** (Ulta, Boots, Shark Tank, The Plaza, Byrdie, NYFW, Wegovy): Wrinkles Schminkles i 111SKIN opierają obecny push na dystrybucji i autorytecie. Nasz odpowiednik = trust „Lekiro, Gostynin, zwrot 14 dni, BLIK/pobranie” (#8).
- **Sprawdzone, ale poza marką (fit = 0)**: SoSmooth „Real women. No needles.” (Winning 100 — botoks jako oś), „Reusable 20+ times / po 60. zmarszczki pogłębiają się” (Winning 100 — straszenie wiekiem), „UNBELIEVABLE 50% OFF” (Winning 100), Scarlette „60% OFF + botoks” ×4 (Optimized 86–90), 111SKIN „injectables in a bottle” (90). To, co w kategorii sprzedaje najmocniej, brief wprost zakazuje (C4, C6, C14) — stąd wynik sędziego ≤ 0,3 mimo wyników platformy.
- **Wniosek z rev. 2**: sprawdzone winnery kategorii to prawie wyłącznie SiO (UGC 11–21 s w łazience, przyczyna → mechanizm → rano) i SoSmooth (statyk value + makro). Pięć „najładniejszych” pomysłów z rev. 1 to testy sprzed kilku dni — przeniesione do hipotez.

## Co z tego wynika dla kroku 5

1. Szkielet batcha 1 = szkielet SiO (Winning 100, 65–77 dni): **problem w 1 zdaniu → „to VeluSkin” → mechanizm prostym językiem → rano sprawdzasz tę samą strefę → cechy (100% silikon, wielorazowy) → CTA**, 11–21 s, postać w łazience. To pokrywa się z naszym `ugc_structure` i z aktualnym winnerem v1.
2. Statyk value (SoSmooth 149861556, Optimized 86, 37 dni) = jedyny sprawdzony statyk w puli, który pasuje do marki: pytanie do niezdecydowanej + reuse + koszt/użycie. Inspirations #6.
3. Hooki: „11”/strefa (Scarlette 157292606, Growing) i odwrócona obiekcja (Hers, Optimized) — jako warianty otwarcia tego samego szkieletu, nie osobne kreacje.
4. Każda z 10 wymaga wycięcia „medical-grade” (C3); żadna nie wymaga PRZED/PO.
