# Bezpieczne wdrażanie zmian (Vercel)

Cel: zmiany w kodzie nie trafiają od razu na `nextlevel-q4.pl`. Najpierw powstaje **wersja podglądowa**
(osobny adres, osobna testowa baza), a na stronę wchodzi dopiero po kliknięciu **Promote to Production**.

## Jednorazowa konfiguracja

### 1. GitHub — gałąź produkcyjna
1. Wejdź na https://github.com/ksemons11-glitch/claude.
2. Rozwiń listę gałęzi → **View all branches** → **New branch**.
3. Nazwa: `produkcja`, źródło: `claude/funny-turing-fsl3d7` → **Create branch**.

### 2. Hostido — testowa baza
1. DirectAdmin → **Zarządzanie MySQL** → **Utwórz nową bazę danych**:
   baza `test` (→ `host308836_test`), nowy użytkownik `lbtest` (→ `host308836_lbtest`),
   hasło wygenerowane w panelu **bez znaków `@ : / ? #`**.
2. W tej bazie → **Hosty dostępu** → dodaj `%`.
3. **Produkcyjnej bazy `host308836_leaderboard` nie ruszaj.**

### 3. Vercel — zmienne środowiskowe
Projekt → **Settings → Environment Variables**:
1. Przy istniejącej `DATABASE_URL` → **Edit** → zostaw zaznaczone **tylko Production** (odznacz Preview i Development) → Save.
2. **Add New**: `DATABASE_URL` = `mysql://host308836_lbtest:HASLO@NAZWA_HOSTA:3306/host308836_test`,
   środowisko **tylko Preview** → Save. (`NAZWA_HOSTA` jest ta sama co w produkcyjnym `DATABASE_URL`.)
3. Sprawdź, że pozostałe zmienne (`APP_URL`, `EVENT_ACCESS_CODE`, `ADMIN_EMAILS`, …) mają zaznaczone i Production, i Preview.

### 4. Vercel — gałąź produkcyjna
**Settings → Environments → Production → Branch Tracking** → ustaw `produkcja` → Save.

### 5. Sprawdzenie
- `https://nextlevel-q4.pl` działa jak wcześniej (obecna wersja produkcyjna zostaje bez zmian).
- **Settings → Deployment Protection**: podglądy powinny mieć włączoną ochronę (Standard Protection) —
  wtedy widzi je tylko zalogowany zespół Vercel, nie uczestnicy.

## Na co dzień

### Nowa zmiana → podgląd
Każda zmiana wypchnięta na `claude/funny-turing-fsl3d7` tworzy w **Deployments** wdrożenie typu **Preview**
z własnym adresem (`…vercel.app`). Działa na **testowej bazie** — możesz tam klikać, rejestrować konta
i generować dane testowe bez ryzyka. Konto admina w teście zakładasz osobno (rejestracja adresem z `ADMIN_EMAILS`).

### Publikacja na nextlevel-q4.pl
1. (Opcjonalnie) Panel admina → **Kopie i serwis** → **Utwórz kopię teraz** i włącz **Tylko odczyt**.
2. Vercel → **Deployments** → sprawdzony podgląd → menu **⋯** → **Promote to Production** → potwierdź.
3. Po 1–2 minutach sprawdź stronę, potem w panelu admina wyłącz tryb serwisowy.

### Coś poszło nie tak po publikacji
Vercel → **Deployments** → poprzednie wdrożenie produkcyjne → **⋯** → **Instant Rollback**.
Strona wraca do poprzedniej wersji w kilka sekund. Dane w bazie zostają — w razie potrzeby przywróć kopię
z panelu admina (**Kopie i serwis**).
