# IMPLEMENTATION_STATUS

Last updated: 2026-09-07. Test suite: `uv run pytest` → 62 passed (unit 25, contracts 9, integration 9, e2e 17+2) against a local PostgreSQL 16.
Legend: **FIXTURE** = works end-to-end on the deterministic demo fixtures; **LIVE-UNVERIFIED** = implemented against the public API
contract but never executed against a real account (no credentials in this environment); **NEEDS ACCESS** = cannot be finished without
owner-provided access/decisions; **NOT BUILT** = intentionally out of scope for this delivery.

## Stage 1 — foundation
| Feature | Status | Evidence |
|---|---|---|
| Repo layout, `pyproject.toml`, `uv.lock` (Python 3.12, FastAPI 0.116, SQLAlchemy 2.0.52, Alembic 1.19, psycopg 3.3, mcp 2.2, anthropic 1.4) | done | `uv sync --frozen` |
| Pydantic contracts (`DataEnvelope`, `MetricValue` null+reason, `RuleResult`, LLM contract) | done | `src/director/contracts/` |
| PostgreSQL schema — 46 tables from §7 + `alerts`, `policy_snapshots`, `historical_observations`; UUID/tenant/timestamps, NUMERIC(20,6), JSONB | done | `migrations/versions/20260907_e15f9e1f2f04_initial_schema.py`; `alembic check` → no drift |
| Job queue: UNIQUE(job, scheduled_for, scope), `SELECT … FOR UPDATE SKIP LOCKED`, leases + heartbeat, retry with backoff/jitter and Retry-After, 401/403 permanent | done | `tests/integration/test_job_queue.py` (2 schedulers, 2 workers, crash re-claim) |
| Scheduler from YAML (Europe/Warsaw, DST-aware, catch-up policy) | done | `test_calendar_scheduler.py` |
| Docker Compose (postgres, migrate, api, scheduler, worker), Dockerfile | done, image build not executed here (no Docker daemon) | `compose.yaml` |
| Auth: signed session cookie + bearer token, CSRF, login rate limit, no anonymous access | done | API smoke run in session |

## Stage 2 — sources
| Adapter | Status | Notes |
|---|---|---|
| Baselinker (`getOrders` 100/page via `id_from`, `getOrderStatusList`, `getOrderReturns`, re-fetch open orders by ID) | LIVE-UNVERIFIED; FIXTURE | contract test: 257 orders with identical timestamps, restart from cursor, 429 retry, auth error permanent; PII dropped, UTM extracted from documented free-form fields |
| Meta Marketing API (account, structure incl. creative/url_tags, ad/day insights, hourly, window reach) | LIVE-UNVERIFIED; FIXTURE | budgets from minor units, CBO/ABO detection, link vs all clicks, attribution key on rows, `paging.next` followed untouched; API version must be set by owner |
| Nailuks MCP (`tools/list` pagination, schema hash, allowlist, argument filtering against schema) | NEEDS ACCESS (URL/token); FIXTURE for panel rows | tool names `nailuks_dane`/`nailuks_meta_ads` are hints only; unmapped required args → NOT_SUPPORTED with instructions |
| Get Hooked (MCP search or manual JSON/CSV import) | NEEDS ACCESS; FIXTURE + manual import path | no connector → UNAVAILABLE, no fictitious trends (e2e scenario 14) |
| Store health (GET status/content/latency) | done | never places orders |
| Raw batches (request hash, checksum, retention), checkpoints, snapshot diff → `structure_changes` (`derivation=snapshot_diff`) | done | FIXTURE |
| Reconciliation (Base vs panel counts/revenue, Meta vs panel spend, currency/timezone, freshness, pagination, duplicates) → `data_quality_issues` with dedupe/auto-resolve | done | FIXTURE |

## Stage 3 — economics
| Feature | Status |
|---|---|
| Metric definitions §8 (MER with “względem Meta” label, ROAS/CPA variants, BE CPA/ROAS, ratio-of-sums windows 3/7/30, zero denominators → null+reason, no ∞ percent) | done, unit-tested |
| Cost ledger (cost versions by date/payment kind, each cost once, recovery on returns, partial refunds, bundles) | done, unit-tested |
| COD cohort model (final-state distribution from mature cohorts with censoring, prior-smoothed, interval + LOW_SAMPLE) | done; **model is a starting heuristic** — calibrate on ≥30 days of real mature cohorts |
| Attribution: id-based + legacy (`utm_content=ad.name`) UTM, match order AD→ADSET→CAMPAIGN→UNKNOWN, unexpanded macros, stale IDs, coverage by orders and revenue | done, unit + e2e |
| Cashflow view separate from cohort view | done (settlements table exists; no settlement source implemented → inflow is 0 until one is configured) |

## Stage 4 — decisions & reports
| Feature | Status |
|---|---|
| Rules: data issue, missing costs, single-day deviation (robust z / MAD), 5-day decline with CPM/CTR/CVR hypotheses, Meta-vs-ledger gap (no 1.4 multiplier), cooldown after change (per entity chain), zero-purchase test vs explicit loss cap, creative concentration, strong day | done; e2e scenarios 1–6, 17, 18 |
| Gates (§11) action-specific; confidence classes + deterministic 0–100 “heuristic evidence quality” | done |
| Evidence bundle → LLM (Anthropic SDK provider, model from env) → validator (unknown refs/IDs/numbers, gate contradictions, injection markers, `execution_allowed` overridden) → one repair → deterministic fallback; daily PLN budget | done; Anthropic provider **LIVE-UNVERIFIED** (no key); FakeProvider exercised |
| Daily report (Markdown+HTML, COMPLETE/PARTIAL, ≤5 actions, “do not touch”, missing data, revisions never overwrite) | done, FIXTURE |
| Weekly report (maturity note, per-shop delta, concentration, decisions, plan 7d) | done, FIXTURE |
| Decision journal lifecycle, evaluations 24h/72h/7d with confounders (COD immaturity, price experiment overlap, spend shift), rejection ≠ failure, expiry | done; e2e scenarios 5, 22 |
| Intraday detection (same-hour cumulative vs comparable days, freshness, min volume, 2 consecutive reads, dedupe/cooldown/escalation, recovery) + store health alerts | done; exercised in fixture mode (no false alarm on low volume) |
| Notifications outbox (dedupe, retry, delivered only on channel confirmation); in-app channel | done; email/Telegram/Discord = `UnconfiguredChannel` until a recipient is authorized |

## Stage 5–6 — creatives, market, portfolio, offers
| Feature | Status |
|---|---|
| Creative identity (asset hash → Post ID → ad), placements, concentration collapsing duplicate placements | done; e2e scenario 9, 17 |
| Concept/variant model, status machine columns | schema + identity done; **LLM classification of concepts NOT BUILT** (manual/heuristic `concept_hint` only) |
| Market signals: trend score with documented weights, PARTIAL without comparison sample, unique variations after dedupe, creative gap, no ROAS claims | done; e2e scenarios 14–16 |
| Weekly creative plan / briefs (capacity-bound, no fabricated proof) | done (basic) |
| Portfolio marginal allocation with caps, cash reserve, stock/fulfillment blocks, bounded experiment when no curve | done, unit-tested; not yet wired into the daily report |
| Promotions: offer versions schema, scenario simulator (margin/BE CPA), price/copy/CTA/landing consistency checks, no derived “price before promo” | done, unit-tested; no UI for creating offers yet (DB/CLI only) |

## Stage 7–8 — operations & execution
| Feature | Status |
|---|---|
| CLI: `db migrate`, `demo seed`, `run daily/weekly/intraday/review-decisions`, `connectors discover`, `sync`, `doctor`, `costs import`, `report show`, `decisions list/approve/reject`, `scheduler`, `worker`, `api` | done |
| API §19: `/health/live|ready`, `/api/reports`, `/api/reports/{id}`, `/api/shops/{key}/metrics`, `/api/structure`, `/api/creatives`, `/api/decisions`, `/api/data-quality`, `POST /api/jobs/run` (rate-limited), `POST /api/recommendations/{id}/accept`, `POST /api/action-requests/{id}/approve`, `POST /api/settings/policies` (records proposal; YAML stays the source of truth) | done |
| Panel: Overview, Stores, Account structure, Creatives, Experiments/Decisions, Market, Promotions, Data health, Settings, Notifications, Reports; OBSERVE badge + last sync visible | done (Jinja, no frontend framework) |
| Backup job (`pg_dump`) | done; encryption/off-host copy/restore test are host tasks (RUNBOOK) |
| Execution module: preview → policy checks (per-op %, per-account daily %, rolling 24h, portfolio cap, cooldown, allowed accounts, kill switch, mode) → approval TTL → precondition hash → apply → control read → audit; timeout → UNKNOWN, never blind retry | done with **MockWriter only**; **no real Meta writer** (by design); disabled by default (`MODE=OBSERVE`, `EXECUTION_ENABLED=false`) |

## Acceptance scenarios (§20)
| # | Scenario | Where |
|---|---|---|
| 1 | weak day of a winner → HOLD | e2e |
| 2 | 5-day decline → DIAGNOSE with evidence | e2e |
| 3 | Meta understated → measurement hypothesis, no 1.4 | e2e |
| 4 | stale sync → DATA_ISSUE | e2e (simulated outage) |
| 5 | budget change yesterday → cooldown, not FAILURE | e2e |
| 6 | zero purchases over explicit cap → PAUSE_TEST recommendation, no write | e2e |
| 7, 8 | late return / partial refund, bundle, recovery | unit (`test_ledger_cohorts.py`) |
| 9 | duplicate asset + legacy UTM | unit + e2e |
| 10 | ≥250 orders, same timestamps, restart | contract (`test_baselinker_contract.py`) |
| 11 | two schedulers/workers, crash, retry | integration |
| 12 | DST 23/25 h | unit |
| 13 | LLM hallucination / injection blocked | unit (`test_validator.py`) |
| 14, 15, 16 | Get Hooked unavailable; trend without ROAS claim; 14 ads / 3 concepts | e2e |
| 17 | 74–89 % concentration → backlog, winner kept | e2e |
| 18 | no COGS → BE unavailable, scaling gate | e2e |
| 19 | state change after approval / timeout | integration (`test_executor.py`) |
| 20 | revision + as_of, no look-ahead | e2e |
| 21 | CBO vs ABO budgets not summed | e2e |
| 22 | price experiment overlap → INCONCLUSIVE | e2e |

Replay: the demo is a **retrospective** backfill (all history computed at one `as_of`), not a faithful replay of historical
decisions. `series(..., as_of=)` and per-row `as_of` make a true replay possible once live data accumulates.

## Not done / needs the owner
- Live verification of every adapter contract, account mapping by ID, status-ID → class mapping, UTM field location (SETUP_REQUIRED.md).
- Real costs, test loss caps, portfolio caps, stock/fulfillment signals (gates stay blocking until configured).
- LLM key + model choice; Get Hooked / Nailuks access; notification channel authorization.
- Production readiness: real adapter checks, monitoring, backup restore test, ≥1 week of OBSERVE operation. The demo does not prove profit; nobody executed the recommendations.
