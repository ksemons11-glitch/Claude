# Wdrożenie na Hostido (nextlevel-q4.pl)

Czas: ok. 20–30 minut. Potrzebujesz dostępu do panelu Hostido (cPanel) i pliku `q4-leaderboard.zip`.

## 1. Domena

W panelu Hostido upewnij się, że domena `nextlevel-q4.pl` jest podpięta do konta hostingowego
(Domeny → Domeny dodatkowe / Addon Domains) i ma włączony darmowy certyfikat SSL
(SSL/TLS Status → „Run AutoSSL”). Aplikacja musi działać pod `https://`.

## 2. Baza danych

cPanel → **Bazy danych MySQL** (MySQL Database Wizard):

1. Utwórz bazę, np. `konto_leaderboard`.
2. Utwórz użytkownika z mocnym hasłem, np. `konto_lb`.
3. Nadaj mu **wszystkie uprawnienia** do tej bazy.

Zapisz: nazwę bazy, użytkownika i hasło. Tabel nie trzeba tworzyć — aplikacja zrobi to sama przy pierwszym starcie.

## 3. Wgranie plików

cPanel → **Menedżer plików**:

1. W katalogu domowym (np. `/home/konto/`) wgraj `q4-leaderboard.zip` i wybierz **Wypakuj**.
   Powstanie folder `/home/konto/q4-leaderboard/` (w nim m.in. `server.js`, `package.json`, `.next/`, `public/`).
2. Utwórz pusty folder na awatary **poza** folderem aplikacji: `/home/konto/leaderboard-uploads`
   (dzięki temu zdjęcia nie znikną przy aktualizacji aplikacji).

## 4. Aplikacja Node.js

cPanel → **Setup Node.js App** → **Create Application**:

| Pole | Wartość |
|---|---|
| Node.js version | najwyższa dostępna 20.x lub 22.x |
| Application mode | Production |
| Application root | `q4-leaderboard` |
| Application URL | `nextlevel-q4.pl` |
| Application startup file | `server.js` |

W sekcji **Environment variables** dodaj (wartości wg `.env.example`):

| Zmienna | Przykład |
|---|---|
| `NODE_ENV` | `production` |
| `DATABASE_URL` | `mysql://konto_lb:HASLO@localhost:3306/konto_leaderboard` |
| `APP_URL` | `https://nextlevel-q4.pl` |
| `EVENT_ACCESS_CODE` | kod, który podacie w grupie (np. `NEXTLEVEL-Q4`) |
| `ADMIN_EMAILS` | e-mail(e) organizatorów, oddzielone przecinkami |
| `UPLOAD_DIR` | `/home/konto/leaderboard-uploads` |
| `TERMS_URL` | link do regulaminu |
| `PRIVACY_URL` | link do polityki prywatności |
| `DATA_CONTROLLER` | nazwa i adres administratora danych |
| `CONTACT_EMAIL` | e-mail kontaktowy |
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | login SMTP z Brevo (Ustawienia → SMTP & API) |
| `SMTP_PASS` | klucz SMTP z Brevo |
| `MAIL_FROM` | `Next Level Q4 <ranking@nextlevel-q4.pl>` (domena nadawcy zweryfikowana w Brevo) |

> Jeśli hasło do bazy zawiera znaki `@ : / ? #`, zamień je w `DATABASE_URL` na kody URL (`@` → `%40`, `#` → `%23` itd.) albo ustaw hasło bez tych znaków.

Następnie:

1. Kliknij **Create**.
2. Kliknij **Run NPM Install** (instaluje biblioteki — może potrwać 1–3 minuty).
3. Kliknij **Restart**.
4. Wejdź na `https://nextlevel-q4.pl` — powinien pokazać się ranking z licznikiem do startu Q4.

## 5. Konto administratora

Wejdź na `https://nextlevel-q4.pl/rejestracja` i zarejestruj się adresem podanym w `ADMIN_EMAILS`
(użyj kodu z `EVENT_ACCESS_CODE`). To konto od razu dostaje rolę administratora i trafia do panelu `/admin`.

W panelu sprawdź **Tygodnie** (domyślnie: tydzień 1 = 1–11.10, kolejne pon–niedz, termin wpisów w sobotę 23:59,
zamknięcie w niedzielę 23:59, ostatni tydzień do 3.01) i **Ustawienia** (nazwa, komunikat, kod dostępu).

## 6. Test maili

Wyloguj się, wejdź w „Nie pamiętam hasła” i poproś o link na swój adres. Jeśli mail nie dochodzi, sprawdź
dane SMTP i czy domena nadawcy (`MAIL_FROM`) jest zweryfikowana w Brevo.

## Aktualizacja aplikacji

1. Zatrzymaj aplikację (Setup Node.js App → Stop).
2. Wgraj nowy `q4-leaderboard.zip` i wypakuj z nadpisaniem plików (dane w bazie i awatary zostają).
3. **Run NPM Install** → **Restart**.

## Problemy

- **Błąd 503 / aplikacja nie startuje** — Setup Node.js App → otwórz aplikację i sprawdź log (`stderr.log` w folderze aplikacji).
  Najczęściej: literówka w `DATABASE_URL` albo brak uprawnień użytkownika bazy.
- **„DATABASE_URL is not set”** — zmienne środowiskowe nie zostały zapisane; dodaj je i zrestartuj.
- **Awatary znikają po aktualizacji** — `UPLOAD_DIR` wskazuje do wnętrza folderu aplikacji; ustaw folder poza nim.
