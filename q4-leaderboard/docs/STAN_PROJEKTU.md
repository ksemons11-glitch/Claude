# Stan projektu — Q4 Leaderboard (Next Level)

Wspólne źródło prawdy dla obu sesji Claude i organizatorów. Stan na: **30.09.2026**, ostatni commit na gałęzi:
`Use Sunday 23:59 as the only weekly deadline`.

## Kto co robi

| Sesja | Zakres | Czego NIE robi |
|---|---|---|
| **Chmura** (repo `ksemons11-glitch/claude`, gałąź `claude/funny-turing-fsl3d7`, katalog `q4-leaderboard/`) | Kod aplikacji: zmiany, testy, build, push | Nie ma dostępu do Vercela, Hostido, Brevo ani produkcyjnej bazy |
| **Komputer** (Claude Desktop + Claude in Chrome, folder „mózg claude”) | Klikanie w przeglądarce: Vercel, DirectAdmin (Hostido), Brevo, panel admina aplikacji | Nie zmienia kodu (zmiany kodu → przez sesję w chmurze), nie rusza produkcyjnej bazy przez SQL |

Zasada: ustawienia aplikacji (daty, kod, tryby, kopie) zmieniamy **w panelu admina aplikacji**, nie w bazie.

## Infrastruktura

- **Aplikacja:** Next.js 15 + TypeScript + Tailwind, hostowana na **Vercel**. Hostido wycofało Node.js, więc nie działa tam.
- **Baza:** MySQL/MariaDB na **Hostido** — `host308836_leaderboard` (użytkownik `host308836_lb`, host dostępu `%`).
  Tabele i nowe kolumny tworzą się same przy starcie aplikacji.
- **Domena:** `nextlevel-q4.pl` (DNS w DirectAdmin → Vercel).
- **Maile:** Brevo SMTP (reset hasła, „konto zaakceptowane”) — skonfigurowane.
- **Wdrażanie:** produkcja (`nextlevel-q4.pl`) budowana z gałęzi **`produkcja`**. Push z chmury na
  `claude/funny-turing-fsl3d7` tworzy tylko **podgląd** (Preview, testowa baza `host308836_test`, widoczny tylko dla
  zespołu Vercel). **Publikacja:** organizator pisze sesji w chmurze „publikuj” → sesja przesuwa gałąź `produkcja`
  na sprawdzoną wersję → Vercel wdraża. Awaryjnie: Vercel → Deployments → Instant Rollback. Szczegóły:
  `docs/BEZPIECZNE_WDRAZANIE.md`.

### Zmienne środowiskowe (Vercel)
Wymagane: `DATABASE_URL`, `APP_URL=https://nextlevel-q4.pl`, `EVENT_ACCESS_CODE` (tylko przy pierwszym starcie),
`ADMIN_EMAILS` (e-maile, które przy **rejestracji** dostają rolę admina), `SMTP_HOST/PORT/USER/PASS`, `MAIL_FROM`.
Mają wartości domyślne w kodzie (nie trzeba ustawiać): `TERMS_URL`, `PRIVACY_URL` (strony nextlevel-marketing.pl),
`DATA_CONTROLLER` (NEXT LEVEL MARKETING sp. z o.o.), `SUPPORT_DISCORD` („Adrian - Młody”).
Nieużywana, do usunięcia jeśli jest: `CONTACT_EMAIL`.

## Harmonogram eventu

- **30.09:** drop na grupy — rejestracja i akceptacja kont.
- **Od 1.10 00:00:** uczestnicy wpisują **łączny przychód od 1.10** (narastająco).
- **Tygodnie:** pon–niedz, wpisy do **niedzieli 23:59** (jedyny termin). Tydzień 1 = 1.10–11.10, ostatni 28.12–3.01 (13 tygodni).
- **Odsłonięcie rankingu: 5.10 00:00** (Panel admina → Ustawienia → „Odsłonięcie rankingu”). Do tego czasu
  uczestnicy widzą tylko odliczanie i swój wynik; admini widzą podgląd tabeli.
- **Kod dostępu:** `NEXTLEVEL-Q4` (zmiana: Ustawienia).

## Funkcje

**Uczestnik:** rejestracja (kod eventu, e-mail, hasło, nick Discord — prywatny, nick rankingowy — publiczny, awatar
gotowy lub własne zdjęcie, 2 zgody) → czeka na akceptację (komunikat kieruje do „Adrian - Młody” na Discordzie) →
wpisuje przychód narastająco, może poprawiać do końca tygodnia; niższej wartości niż w poprzednich tygodniach nie wpisze —
wtedy formularz „Zgłoś korektę”. Historia wpisów, profil, zmiana hasła, reset hasła mailem, prośba o usunięcie konta.

**Ranking:** Cały Q4 (wg wyniku narastającego) / Ten tydzień / Poprzedni tydzień (wg przyrostu w tygodniu);
remisy 1, 2, 2, 4; strzałki awansu/spadku vs koniec poprzedniego tygodnia; „NOWY”; podium, Top 10, lista 11–50,
reszta rozwijana po 25 + wyszukiwarka; przyklejona karta „Twoja pozycja” (miejsce, brakująca kwota do kolejnego miejsca).
**Spóźnialscy:** pierwszy wpis po tygodniu 1 liczy się do rankingu Q4, ale nie do tygodniowego.
Publicznie tylko nick, awatar, kwoty i pozycja — e-mail i Discord nigdy nie wychodzą do gości (także przez API).

**Panel admina** (`/admin`, zakładki): Oczekujące (akceptacja pojedyncza i zbiorcza, odrzucanie) · Uczestnicy
(wyszukiwarka, filtr, karta: blokada/odblokowanie, korekta wyniku z powodem dla każdego tygodnia, historia zmian,
anonimizacja konta) · Korekty (zgłoszenia uczestników) · Tygodnie (daty początku/końca, ręczne zamknięcie, dodanie tygodnia) ·
Dziennik zmian · Ustawienia (nazwa, komunikat, kod dostępu, rejestracja otwarta, ranking publiczny, odsłonięcie rankingu,
dane testowe: 50 kont jednym kliknięciem i usuwanie) · **Kopie i serwis** · eksport CSV (uczestnicy, wyniki).

**Bezpieczeństwo i awarie:**
- **Kopie zapasowe:** automatycznie raz na dobę + ręcznie + przed każdym przywróceniem; 40 najnowszych w bazie;
  pobieranie na dysk (JSON, zawiera dane osobowe); przywracanie z listy lub pliku (transakcja — wszystko albo nic).
  Bez zdjęć awatarów. Zalecenie: raz w tygodniu pobrać kopię na dysk.
- **Tryb serwisowy:** „Tylko odczyt” (strona widoczna, zapisy zablokowane, czerwony pasek z komunikatem) i
  „Przerwa techniczna” (strona zamknięta, logowanie działa). Admini zawsze mają dostęp.
- Limity prób logowania/rejestracji/resetu trzymane w bazie (działają na Vercelu), hasła bcrypt, sesje w bazie.
- Wydajność: test 250 uczestników / 50 równoczesnych — ok. 145 odsłon strony na sekundę na jednym serwerze.

## Otwarte sprawy

- [x] Bezpieczne wdrażanie: gałąź `produkcja`, testowa baza `host308836_test`, `DATABASE_URL` osobno dla Production/Preview,
  Branch Tracking = `produkcja`, Deployment Protection = Standard.
- [ ] Preview: dodać `EVENT_ACCESS_CODE` i `ADMIN_EMAILS` (bez SMTP), potem pierwszy podgląd i publikacja
  poprawki „niedziela 23:59 jako jedyny termin”.
- [ ] Potwierdzić w panelu: odsłonięcie 5.10 00:00, kod `NEXTLEVEL-Q4`, 0 kont testowych, tryb „Normalna praca”.
- [ ] Akapit o rankingu Q4 w polityce prywatności (cel, zakres danych, okres przechowywania).
- [ ] Kolejni admini (np. Agata): e-mail do `ADMIN_EMAILS` **przed** jej rejestracją + Redeploy; jeśli już ma konto — do ustalenia.
- [ ] Usunąć zmienną `CONTACT_EMAIL` z Vercela, jeśli istnieje.

## Dokumenty w repo
`README.md` (technicznie) · `docs/STAN_PROJEKTU.md` (ten plik) · `docs/WDROZENIE_VERCEL.md` · `docs/BEZPIECZNE_WDRAZANIE.md` ·
`docs/WDROZENIE_HOSTIDO.md` (nieaktualne dla Hostido — zostaje dla hostingów z Node.js).
