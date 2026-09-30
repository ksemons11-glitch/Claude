# Wdrożenie na Hostido (nextlevel-q4.pl, panel DirectAdmin)

> **Nieaktualne dla nowych usług Hostido** — Hostido wycofało uruchamianie aplikacji Node.js pod domeną.
> Użyj [WDROZENIE_VERCEL.md](WDROZENIE_VERCEL.md). Ta instrukcja zostaje dla hostingów z „Setup Node.js App”.

Czas: ok. 20–30 minut. Potrzebujesz dostępu do panelu Hostido (DirectAdmin) i pliku `q4-leaderboard.zip`.
Ścieżki poniżej zakładają konto `host308836` (widoczne w Menedżerze plików jako UID/GID).

## 1. Domena i SSL

Domena `nextlevel-q4.pl` jest już podpięta (w Menedżerze plików jest `domains/nextlevel-q4.pl`).
Sprawdź w DirectAdmin → **Certyfikat SSL**, że dla domeny jest włączony darmowy certyfikat Let's Encrypt —
aplikacja musi działać pod `https://`.

## 2. Baza danych

DirectAdmin → **Zarządzanie MySQL** → **Utwórz nową bazę danych**:

- nazwa bazy, np. `leaderboard` (panel doda prefiks: `host308836_leaderboard`),
- użytkownik, np. `lb` (→ `host308836_lb`), hasło wygenerowane przez panel — **bez znaków `@ : / ? #`**.

Zapisz pełną nazwę bazy, użytkownika i hasło. Tabel nie trzeba tworzyć — aplikacja zrobi to sama przy pierwszym starcie.

## 3. Wgranie plików

DirectAdmin → **Menedżer plików**:

1. Wejdź do `domains/nextlevel-q4.pl` (tam, gdzie są `public_ftp` i `public_html`).
2. **Prześlij** `q4-leaderboard.zip`, zaznacz go i wybierz **Wypakuj** (Extract).
   Powstanie folder `domains/nextlevel-q4.pl/q4-leaderboard/` (w nim m.in. `server.js`, `package.json`, `.next/`, `public/`).
   Plików aplikacji **nie** wrzucaj do `public_html`.

## 4. Aplikacja Node.js

DirectAdmin → **Setup Node.js App** (zwykle w sekcji „Dodatkowe funkcje” / „Extra Features”) → **Create Application**.
Jeśli nie widzisz tej opcji, napisz do supportu Hostido: „Proszę o włączenie Node.js (Setup Node.js App) dla konta host308836”.

| Pole | Wartość |
|---|---|
| Node.js version | najwyższa dostępna 20.x lub 22.x |
| Application mode | Production |
| Application root | `domains/nextlevel-q4.pl/q4-leaderboard` |
| Application URL | `nextlevel-q4.pl` (bez dopisku po ukośniku) |
| Application startup file | `server.js` |

W sekcji **Environment variables** dodaj (opis wszystkich w `.env.example`):

| Zmienna | Wartość |
|---|---|
| `NODE_ENV` | `production` |
| `DATABASE_URL` | `mysql://host308836_lb:HASLO@localhost:3306/host308836_leaderboard` |
| `APP_URL` | `https://nextlevel-q4.pl` |
| `EVENT_ACCESS_CODE` | kod, który podacie w grupie (np. `NEXTLEVEL-Q4`) |
| `ADMIN_EMAILS` | e-mail(e) organizatorów, oddzielone przecinkami |
| `TERMS_URL` | link do regulaminu |
| `PRIVACY_URL` | link do polityki prywatności |
| `DATA_CONTROLLER` | nazwa i adres administratora danych |
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | login SMTP z Brevo (Ustawienia → SMTP & API) |
| `SMTP_PASS` | klucz SMTP z Brevo |
| `MAIL_FROM` | `Next Level Q4 <ranking@nextlevel-q4.pl>` (domena nadawcy zweryfikowana w Brevo) |

Maile (SMTP) możesz uzupełnić później — bez nich aplikacja działa, tylko nie wyśle linku do resetu hasła.

Następnie:

1. Kliknij **Create**.
2. Kliknij **Run NPM Install** (instaluje biblioteki — może potrwać 1–3 minuty).
3. Kliknij **Restart**.
4. Wejdź na `https://nextlevel-q4.pl` — powinien pokazać się ranking z licznikiem do startu Q4.

## 5. Konto administratora

Wejdź na `https://nextlevel-q4.pl/rejestracja` i zarejestruj się adresem podanym w `ADMIN_EMAILS`
(użyj kodu z `EVENT_ACCESS_CODE`). To konto od razu dostaje rolę administratora i trafia do panelu `/admin`.

W panelu sprawdź **Tygodnie** (domyślnie: tydzień 1 = 1–11.10, kolejne pon–niedz, wpisy do końca tygodnia,
zamknięcie w niedzielę 23:59, ostatni tydzień do 3.01) i **Ustawienia** (nazwa, komunikat, kod dostępu).

## 6. Test maili

Wyloguj się, wejdź w „Nie pamiętam hasła” i poproś o link na swój adres. Jeśli mail nie dochodzi, sprawdź
dane SMTP i czy domena nadawcy (`MAIL_FROM`) jest zweryfikowana w Brevo.

## Aktualizacja aplikacji

1. Zatrzymaj aplikację (Setup Node.js App → Stop).
2. Wgraj nowy `q4-leaderboard.zip` i wypakuj z nadpisaniem plików (dane w bazie i awatary zostają).
3. **Run NPM Install** → **Restart**.

## Problemy

- **Błąd 503 / aplikacja nie startuje** — sprawdź log `stderr.log` w folderze `domains/nextlevel-q4.pl/q4-leaderboard/`.
  Najczęściej: literówka w `DATABASE_URL` albo brak uprawnień użytkownika bazy.
- **„DATABASE_URL is not set”** — zmienne środowiskowe nie zostały zapisane; dodaj je i zrestartuj.
- **Widać starą stronę Hostido zamiast rankingu** — usuń domyślny `index.html` z `public_html` i zrestartuj aplikację.
