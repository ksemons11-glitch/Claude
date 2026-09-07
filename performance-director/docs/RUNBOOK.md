# Runbook

## Processes
| Process | Command | Notes |
|---|---|---|
| api | `director api` | panel + JSON API, port 8000, needs `APP_AUTH_SECRET`, `APP_ADMIN_PASSWORD` |
| scheduler | `director scheduler` | writes due `job_runs`; several instances are safe |
| worker | `director worker` | claims jobs with leases; scale horizontally |
| one-off | `director run daily --date YYYY-MM-DD --mode live` | manual report |

## Daily checks (`director doctor`)
DB + migrations, timezone, config load, presence of secrets, mode, LLM budget, notification channel, account mapping verification, source freshness, last jobs, last report, connector health.

## Failure handling
| Symptom | What the system does | What you do |
|---|---|---|
| Source down / 5xx / 429 | retry with backoff + Retry-After, max 5; report marked PARTIAL; last good data kept with visible `as_of`; dependent rules disabled | check `Data health`, wait for `retry_daily` (08:30) |
| 401/403 from a source | job fails permanently (`PermanentError`), no retry loop | refresh token/permissions, re-run `director sync` |
| LLM error / budget exhausted | deterministic report, `llm_error` recorded | nothing required; check `LLM_DAILY_BUDGET_PLN` |
| DB down | no report, no changes; jobs stay PENDING | restore DB, workers resume automatically |
| Worker crash mid-job | lease expires -> another worker re-claims (attempt+1) | inspect `job_runs.error_class = LeaseExpired` |
| Report shows DATA_ISSUE | critical reconciliation problem (stale source, incomplete pagination, currency/timezone mismatch) | fix source; a re-run creates revision N+1 |
| Downtime > 1 day | daily jobs catch up (max 3 days), interval jobs run once; no series of stale intraday alerts | verify reports exist for each missed day |

## Backup & restore
- `backup` job runs `pg_dump --format=custom` into `var/backups/` daily. Encrypt at rest on the host (e.g. age/gpg) and copy off-host.
- Restore test (monthly, before production): `createdb director_restore && pg_restore -d director_restore var/backups/<file>.dump`, then `DATABASE_URL=...director_restore director doctor`.

## Monitoring signals
`job_runs` (last_success per job, queue age via `/data-health`), `sync_checkpoints` lag, `data_quality_issues` (unmatched revenue %, mismatches), `reports.llm_error` / tokens / cost, `notification_outbox` failures, `/health/ready` degraded connectors.

## Cost control
LLM runs once per daily report and for significant diagnoses only - never for healthchecks. Hard daily budget `LLM_DAILY_BUDGET_PLN`; over budget -> deterministic report. Evidence bundles are cached in `reports.evidence_bundle`.

## Revisions and corrections
Never overwrite: a re-run writes a new report revision and new `as_of` metric rows. Corrections that do not change conclusions do not trigger notifications (`retry_daily` skips COMPLETE reports).
