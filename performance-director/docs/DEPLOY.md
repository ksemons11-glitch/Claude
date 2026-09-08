# DEPLOY — wdrożenie na serwerze (tryb OBSERVE)

Cel: usługa działa 24/7 na VPS, codziennie o 07:30 (Europe/Warsaw) produkuje raport D-1, nic nie zmienia w kontach.
Kolejność jest ważna: najpierw wszystko na fixture, potem odczyt live, potem harmonogram. Autopilot nie jest częścią wdrożenia.

## 0. Wymagania
- VPS Linux (2 vCPU, 4 GB RAM, 40 GB dysku wystarczą), Docker + Docker Compose v2, otwarty tylko port SSH; panel wystawiaj przez reverse proxy z TLS (Caddy/Nginx) albo tunel SSH — nigdy goły port 8000 na świat.
- Dostęp do repozytorium `ksemons11-glitch/Claude`, gałąź `claude/chatgpt-link-session-2dqq1g`, katalog `performance-director/`.
- Sekrety (tylko do `.env` na serwerze, nigdy do repo/czatu): token Baselinker (odczyt), token Meta Marketing API (`ads_read`) + wersja API, opcjonalnie URL/token MCP Nailuks i Get Hooked, opcjonalnie klucz Anthropic.

## 1. Kod i konfiguracja
```bash
git clone -b claude/chatgpt-link-session-2dqq1g https://github.com/ksemons11-glitch/Claude.git
cd Claude/performance-director
cp .env.example .env
for f in shops policies schedules competitors costs; do cp config/$f.example.yaml config/$f.yaml; done
```
Uzupełnij `.env`:
| Zmienna | Wartość |
|---|---|
| `DATABASE_URL` | zostaw domyślną z compose (`postgresql+psycopg://director:director@postgres:5432/director`), ale zmień hasło Postgresa w `compose.yaml` i tu na losowe |
| `APP_AUTH_SECRET` | `openssl rand -hex 32` |
| `APP_ADMIN_PASSWORD` | długie hasło do panelu |
| `APP_API_TOKEN` | `openssl rand -hex 32` (do wywołań API bez logowania) |
| `APP_BASE_URL` | publiczny adres panelu za TLS |
| `MODE=OBSERVE`, `EXECUTION_ENABLED=false`, `KILL_SWITCH=false` | zostaw |
| `BASELINKER_TOKEN`, `META_ACCESS_TOKEN`, `META_API_VERSION` | prawdziwe wartości; wersję API sprawdź w dokumentacji Meta w dniu wdrożenia (np. `v23.0`) |
| `NAILUKS_MCP_URL`, `NAILUKS_MCP_TOKEN` | jeśli panel ma być źródłem kontrolnym |
| `GETHOOKED_MCP_URL` | jeśli jest; inaczej wrzucaj eksporty do `config/market_import/*.json|csv` |
| `LLM_PROVIDER=anthropic`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_DAILY_BUDGET_PLN` | opcjonalnie; model sprawdź w aktualnej dokumentacji Anthropic; budżet 0 = LLM wyłączony, raport i tak powstaje |

Uzupełnij YAML-e (to jest kontrakt, nie placeholdery):
- `config/shops.yaml`: potwierdź `meta_account_id` i `baselinker_shop_id` **po ID** (tabela z notatek jest tylko punktem startu), `order_date_basis` (created/confirmed), `health_urls`, listy ID statusów Baselinkera → `cancelled_statuses`, `returned_statuses`, `delivered_statuses` (ID weź z `getOrderStatusList`, patrz krok 4).
- `config/costs.yaml`: prawdziwe koszty zmienne per produkt (`product_key` = SKU małymi literami). Bez COGS system nie liczy zysku i blokuje skalowanie — to celowe.
- `config/policies.yaml`: `test_loss_cap_pln`, `target_cpa_pln` per produkt, `portfolio_daily_cap_pln`, `cash_reserve_pln`, `cod_settlement_lag_days`. `execution.allowed_accounts` zostaw puste.
- `config/competitors.yaml`: marki w koszykach direct/adjacent/dtc.

## 2. Test offline (zanim dotkniesz prawdziwych źródeł)
```bash
docker compose up -d postgres
docker compose run --rm migrate
docker compose run --rm -e FIXTURE_DIR=var/fixtures/demo api director demo seed
docker compose run --rm -e FIXTURE_DIR=var/fixtures/demo -e LLM_PROVIDER=fake api director run daily --date yesterday --mode fixture
```
Oczekiwane: raport `COMPLETE`, 5 działań, pierwsze to `PAUSE_TEST` dla testowej reklamy, sekcja „czego nie ruszać”. Jeśli to nie działa, nie idź dalej.

## 3. Odkrywanie źródeł (tylko odczyt)
```bash
docker compose run --rm api director connectors discover --read-only
docker compose run --rm api director doctor
```
- `connectors discover` pokazuje health każdego źródła i zapisuje schematy narzędzi MCP (z hashami) do tabeli `connector_capabilities`. Dla Nailuks sprawdź, czy nazwy narzędzi i parametry pasują do heurystyk w `src/director/adapters/nailuks.py` (`TOOL_HINTS`, `DATE_ARG_CANDIDATES`); jeśli nie, dopisz tam prawdziwe nazwy — adapter nie zgaduje parametrów.
- `doctor` musi pokazać `db OK`, brak `FAIL`; `mapping WARN unverified` jest normalne do momentu weryfikacji.

## 4. Weryfikacja kontraktów live (jednorazowo, ręcznie)
Baselinker:
```bash
docker compose run --rm api python - <<'PY'
from director.adapters.baselinker import BaselinkerAdapter; from director.adapters.base import SyncRequest; from director.config import get_settings
s=get_settings(); a=BaselinkerAdapter(s.baselinker_token, s.baselinker_api_url)
print(a.sync(SyncRequest(stream="statuses", account_id="x")).records)          # ID statusów -> wpisz do shops.yaml
from datetime import date, timedelta
env=a.sync(SyncRequest(stream="orders", account_id="x", date_from=date.today()-timedelta(days=3), date_to=date.today()))
print(env.status, len(env.records), env.pagination_complete); print(env.records[0] if env.records else None)  # sprawdź pole `utm`
PY
```
Jeśli `utm` jest puste, ustal, w którym polu zamówienia siedzą UTM-y i rozszerz `extract_utm` w `adapters/baselinker.py`.
Meta: `director sync --days 7 --read-only`, potem w Postgresie `select count(*) from ads; select sum(spend) from ad_insights;` i porównaj ze spendem w Ads Managerze za ten sam okres (tolerancja zaokrągleń). Rozjazd waluty/strefy pojawi się jako `DATA_ISSUE`.

## 5. Import historii i pierwszy raport live
```bash
docker compose run --rm api director sync --days 90 --read-only
docker compose run --rm api director run daily --date yesterday --mode live
docker compose run --rm api director report show
```
Sprawdź na panelu `Data health`: świeżość źródeł, otwarte problemy, pokrycie atrybucji per sklep. Pokrycie poniżej 80% blokuje rekomendacje na poziomie reklamy — to zamierzone.
Oznacz weryfikację mapowania: `update source_accounts set mapping_verified_at=now();` (po ręcznym potwierdzeniu ID).

## 6. Uruchomienie ciągłe
```bash
docker compose up -d api scheduler worker
docker compose logs -f worker
```
Harmonogram w `config/schedules.yaml` (czasy Europe/Warsaw). Możesz mieć wiele workerów i schedulerów — kolejka to Postgres z leasami.
Panel: `APP_BASE_URL` za reverse proxy; logowanie `APP_ADMIN_USER`/`APP_ADMIN_PASSWORD`. API: nagłówek `Authorization: Bearer $APP_API_TOKEN`.

## 7. Backup i monitoring
- Job `backup` robi `pg_dump` do `var/backups/` codziennie o 04:00; skopiuj je off-host i zaszyfruj (np. `age`). Raz w miesiącu test odtworzenia do osobnej bazy (RUNBOOK).
- Zdrowie: `curl -s http://127.0.0.1:8000/health/ready` (pokazuje `degraded` konektory), strona `Data health`, tabela `job_runs`.
- Koszt LLM: `LLM_DAILY_BUDGET_PLN`; po przekroczeniu raport deterministyczny.

## 8. Tydzień obserwacji (Definition of Done produkcji)
Przez co najmniej 7 dni: raport codziennie COMPLETE albo jawnie PARTIAL, liczby uzgodnione z Base/Ads Managerem w tolerancji zaokrągleń, brak fałszywych alarmów intraday, koszty modelu pod kontrolą. Dopiero potem rozmowa o `APPROVAL_REQUIRED` i prawdziwym writerze (nie istnieje w tym repo — wymaga osobnej implementacji i przeglądu `docs/THREAT_MODEL.md`).

## Aktualizacja
```bash
git pull && docker compose build && docker compose run --rm migrate && docker compose up -d api scheduler worker
```
