# AI E-commerce Performance Director

Observe-only analytics and decision-journal service for four DTC shops (Meta Ads + Baselinker + Nailuks panel).
It pulls data, reconciles it, computes deterministic economics (COD-aware cohorts, attribution, break-even), runs
rule-based diagnostics, optionally asks an LLM for *interpretation only*, and produces a daily / weekly report with
at most five actions. It never changes budgets, prices, ads or orders: `MODE=OBSERVE` has no write path.

Status of every feature (fixture vs live vs needs access): **[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)**.
What the owner must provide for live mode: **[SETUP_REQUIRED.md](SETUP_REQUIRED.md)**.

## Quick start (offline demo, no credentials)

```bash
uv sync --frozen
cp .env.example .env                      # set DATABASE_URL, APP_AUTH_SECRET, APP_ADMIN_PASSWORD
docker compose up -d postgres
uv run director db migrate
uv run director demo seed                  # deterministic fixtures for 4 shops, 45 days, all scenarios
uv run director run daily --date yesterday --mode fixture
uv run director run weekly --mode fixture
uv run director doctor
uv run pytest
uv run director api                        # http://localhost:8000 (login with APP_ADMIN_USER / APP_ADMIN_PASSWORD)
```

`demo seed` writes raw API-shaped fixtures under `var/fixtures/demo/` (Baselinker `getOrders` pages, Meta Graph
insights/structure, Nailuks panel rows, Get Hooked ads). Fixture mode replays them through the *same* normalisers
and pipeline as live data. Set `LLM_PROVIDER=fake` to exercise the LLM contract + validator without a key.

## Live mode

```bash
uv run director connectors discover --read-only   # health + MCP tool schemas (hashed) for every source
uv run director sync --days 90 --read-only        # first import
uv run director run daily --date yesterday --mode live
docker compose up -d api worker scheduler          # continuous operation on the owner's server
```

Configuration: `config/*.yaml` (copy from `*.example.yaml`; `shops`, `policies`, `schedules`, `competitors`,
`costs`). Every loaded YAML is snapshotted into the database so a report can be traced to its configuration.

## Architecture

```
sources -> adapters -> raw batches -> normalisation -> reconciliation (DQ) -> deterministic metrics
        -> rules & evidence -> LLM interpretation (validated) -> report / backlog / decision journal
                                                        -> (disabled) executor: preview -> approve -> verify
```

Processes (one image, `compose.yaml`): `postgres`, `api` (panel + JSON API, authenticated), `scheduler`
(computes due `job_runs`), `worker` (claims jobs with `SELECT ... FOR UPDATE SKIP LOCKED` + leases). The queue is
PostgreSQL; no Redis/Celery/vector DB.

Key modules under `src/director/`: `adapters/` (meta, baselinker, nailuks MCP, gethooked, fixture),
`ingestion/` (raw, loaders, snapshot diff, reconciliation), `metrics/` (economics, ledger, cohorts, attribution,
aggregates), `diagnostics/` (baselines, gates, rules, engine, intraday anomalies), `reasoning/` (provider,
validator, budget), `reports/`, `decisions/`, `creatives/`, `portfolio/`, `promotions/`, `execution/` (off by
default), `jobs/` (queue, scheduler, worker, handlers), `api/`, `cli.py`.

## Principles baked into the code
- Missing data is `MISSING/UNAVAILABLE/NOT_SUPPORTED/UNCONFIGURED`, never zero sales. Zero denominators return
  `null` + reason. Period ratios are ratio-of-sums.
- "Result after variable costs and advertising" is the headline; full operating profit is not claimed. Three
  views: ordered, expected cohort (with interval and LOW_SAMPLE status), realized; cashflow is separate.
- Meta purchases are not multiplied by a COD correction factor; the gap is reported as a measurement hypothesis.
- Ad name is not an identity; creatives are keyed by asset hash / Post ID; unknown orders are never spread by spend.
- The LLM sees an evidence bundle, may recommend "no change", cannot invent numbers or IDs (validator) and never
  decides `execution_allowed` (policy engine does).
- New report revision on every re-run; nothing is overwritten.

## Documentation
`docs/DATA_DICTIONARY.md`, `docs/RUNBOOK.md`, `docs/THREAT_MODEL.md`, `SETUP_REQUIRED.md`, `IMPLEMENTATION_STATUS.md`.
