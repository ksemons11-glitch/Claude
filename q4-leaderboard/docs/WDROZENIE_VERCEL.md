# Wdrożenie: aplikacja na Vercel, baza i domena na Hostido

Hostido wycofało uruchamianie aplikacji Node.js pod domeną, dlatego aplikacja działa na Vercel
(hosting stworzony dla Next.js), a baza MySQL i domena `nextlevel-q4.pl` zostają na Hostido.
Czas: ok. 20 minut.

## 1. Baza na Hostido — zezwól na połączenia z zewnątrz

Baza `host308836_leaderboard` i użytkownik `host308836_lb` są już utworzone (jeśli nie — utwórz je w
DirectAdmin → **Zarządzanie MySQL**, hasło bez znaków `@ : / ? #`).

1. DirectAdmin → **Zarządzanie MySQL** → kliknij bazę `host308836_leaderboard`.
2. W sekcji **Hosty dostępu** (Access Hosts) dodaj `%` (Vercel łączy się z różnych adresów IP).
3. Zapisz **nazwę hosta serwera MySQL** — zwykle to adres serwera z paska adresu panelu
   (np. `sXX.hostido.net.pl`, bez `https://` i bez `:2222`).

`DATABASE_URL` będzie miał postać:
`mysql://host308836_lb:HASLO@NAZWA_HOSTA:3306/host308836_leaderboard`

> Jeśli Hostido nie pozwala na zdalny dostęp do MySQL (połączenie z Vercel zwraca błąd), użyj darmowej bazy
> w chmurze, np. **Aiven for MySQL** (plan Free, region Europe): skopiuj jej adres do `DATABASE_URL`
> i ustaw `DATABASE_SSL=true`.

## 2. Vercel — import projektu

1. Wejdź na **vercel.com** → **Sign Up** → **Continue with GitHub** (konto `ksemons11-glitch`).
2. **Add New… → Project** → wybierz repozytorium `ksemons11-glitch/claude` → **Import**
   (jeśli go nie widać: „Adjust GitHub App Permissions” i daj dostęp do tego repozytorium).
3. **Root Directory**: kliknij **Edit** i wybierz `q4-leaderboard`. Framework: Next.js (wykryje sam).
4. **Environment Variables** — dodaj:

| Zmienna | Wartość |
|---|---|
| `DATABASE_URL` | `mysql://host308836_lb:HASLO@NAZWA_HOSTA:3306/host308836_leaderboard` |
| `APP_URL` | `https://nextlevel-q4.pl` |
| `EVENT_ACCESS_CODE` | `NEXTLEVEL-Q4` |
| `ADMIN_EMAILS` | `ksemons11@gmail.com` |

   Później (Settings → Environment Variables, potem Redeploy): `TERMS_URL`, `PRIVACY_URL`,
   `DATA_CONTROLLER` i maile Brevo `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_USER`,
   `SMTP_PASS`, `MAIL_FROM`.

5. **Deploy**. Pierwsze wdrożenie może pójść z gałęzi domyślnej repozytorium — dlatego:
6. **Settings → Environments → Production → Branch Tracking**: ustaw gałąź `claude/funny-turing-fsl3d7`
   (tam jest aplikacja), zapisz, a potem **Deployments → Redeploy** najnowszego wdrożenia z tej gałęzi
   (albo scal gałąź do `main` i zostaw domyślne ustawienie).
7. Otwórz adres `https://…vercel.app` z Vercel — ma się pokazać ranking z licznikiem do startu Q4.
   Błąd 500 = zwykle zły `DATABASE_URL` albo brak `%` w hostach dostępu MySQL (log: Deployments → Functions/Logs).

## 3. Domena nextlevel-q4.pl

1. Vercel → projekt → **Settings → Domains** → dodaj `nextlevel-q4.pl` (i zgódź się na `www.nextlevel-q4.pl`).
   Vercel pokaże rekordy DNS do ustawienia.
2. DirectAdmin → **Zarządzanie DNS** dla `nextlevel-q4.pl`:
   - rekord **A** dla `nextlevel-q4.pl.` → wartość podana przez Vercel (zwykle `76.76.21.21`); usuń/zamień stary rekord A domeny,
   - rekord **CNAME** dla `www` → wartość podana przez Vercel (zwykle `cname.vercel-dns.com.`).
3. Po kilku–kilkudziesięciu minutach Vercel pokaże „Valid Configuration” i sam wystawi certyfikat SSL.

## 4. Konto administratora

Wejdź na `https://nextlevel-q4.pl/rejestracja` (albo adres `…vercel.app`, jeśli DNS jeszcze się nie rozszedł)
i zarejestruj się adresem z `ADMIN_EMAILS`, kodem `NEXTLEVEL-Q4`. Konto od razu trafia do panelu `/admin`.

## Koszty

Vercel Hobby jest darmowy, ale według regulaminu przeznaczony do projektów niekomercyjnych. Dla programu
mentoringowego bezpieczniej przejść na **Pro (20 USD/mies.)** — można to zrobić w każdej chwili bez zmian w aplikacji.

## Aktualizacje

Każda zmiana wypchnięta na gałąź produkcyjną w GitHub wdraża się automatycznie.
