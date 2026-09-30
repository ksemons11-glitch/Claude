# Q4 Leaderboard (Next Level)

Mobilna aplikacja webowa z rankingiem przychodów uczestników programu mentoringowego w Q4.
Specyfikacja: ranking całego Q4 + ranking przyrostu tygodniowego, samodzielna rejestracja z kodem eventu,
akceptacja kont przez administratora, dziennik zmian wyników, eksport CSV.

**Stos:** Next.js 15 (App Router, TypeScript) · Tailwind CSS · MySQL/MariaDB (`mysql2`) · własne logowanie
(bcrypt + sesje w bazie) · SMTP (Brevo) przez `nodemailer`. Brak natywnych zależności — działa na hostingu
współdzielonym z Node.js (Hostido — DirectAdmin + CloudLinux).

Stan projektu i podział pracy: [docs/STAN_PROJEKTU.md](docs/STAN_PROJEKTU.md). Wdrożenie: [docs/WDROZENIE_VERCEL.md](docs/WDROZENIE_VERCEL.md) (Vercel + MySQL na Hostido). Hosting z panelem
„Setup Node.js App”: [docs/WDROZENIE_HOSTIDO.md](docs/WDROZENIE_HOSTIDO.md).

## Jak działa ranking

- Uczestnik wpisuje **łączny przychód od początku Q4**. Wpis trafia do tygodnia trwającego w chwili zapisu;
  w obrębie tygodnia można go poprawiać do zamknięcia tygodnia.
- **Ranking Q4** — malejąco po ostatnim wyniku narastającym.
- **Ranking tygodnia** — malejąco po `wynik na koniec tygodnia − wynik na koniec poprzedniego tygodnia`
  (tylko osoby, które w danym tygodniu zgłosiły wynik).
- **Zmiana pozycji** — miejsce w rankingu Q4 teraz vs. na koniec poprzedniego tygodnia (liczone na bieżąco,
  więc korekty administratora automatycznie się uwzględniają).
- **Remisy** — ten sam wynik = to samo miejsce, kolejne pomija (1, 2, 2, 4).
- Nowy wynik nie może być niższy niż zgłoszony w poprzednich tygodniach — zamiast tego uczestnik wysyła
  zgłoszenie korekty, które administrator rozpatruje w panelu.

Logika jest w czystych funkcjach (`src/lib/ranking.ts`, `src/lib/periods.ts`) pokrytych testami.

## Prywatność

Publiczna strona i `/api/ranking` budują odpowiedź z białej listy pól (`toPublicRow` w `src/lib/leaderboard.ts`):
nick, awatar, miejsce, kwoty, zmiana pozycji. E-mail, nick Discord i identyfikatory kont nigdy nie trafiają do
odpowiedzi dla gości. Własne zdjęcia są skalowane w przeglądarce do 256×256, a serwer sprawdza typ pliku po jego
zawartości (JPG/PNG/WEBP, maks. 300 KB) i trzymane w bazie, więc aplikacja nie potrzebuje zapisywalnego dysku.

## Praca lokalna

```bash
npm install
cp .env.example .env.local   # uzupełnij DATABASE_URL (pusta baza MySQL/MariaDB)
npm run dev                  # http://localhost:3000
npm test                     # testy logiki rankingu, tygodni i walidacji
npm run typecheck
```

Tabele, event i domyślne tygodnie tworzą się automatycznie przy pierwszym zapytaniu do bazy.
Bez skonfigurowanego SMTP treść maili (np. link do resetu hasła) trafia do logu serwera.

## Paczka na hosting

```bash
npm run build && npm run package   # → dist/q4-leaderboard.zip
```

Paczka nie zawiera `node_modules` (CloudLinux na Hostido instaluje je sam przez „Run NPM Install”);
`package.json` w paczce ma przypięte dokładne wersje użyte przy budowaniu.

## Struktura

```
src/app/                 strony (dashboard, logowanie, rejestracja, konto, admin) i API
src/app/actions/         akcje serwerowe (auth, uczestnik, admin) — każda sprawdza uprawnienia
src/components/          komponenty UI (podium, Top 10, lista, karta „Twoja pozycja”, formularze)
src/lib/                 baza, sesje, ranking, tygodnie, walidacja, maile, awatary
public/avatars/          16 gotowych awatarów
```
