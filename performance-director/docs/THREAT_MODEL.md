# Threat model

Scope: the Performance Director service (api, scheduler, worker, PostgreSQL) and its integrations (Meta Marketing API, Baselinker, Nailuks MCP, Get Hooked MCP, optional LLM provider).

## Assets
- Credentials: Meta token, Baselinker token, MCP URLs/tokens, LLM key, admin password, session secret.
- Business data: orders (pseudonymised), costs, budgets, decisions, reports.
- Write access to ad accounts (only via the disabled-by-default execution module).

## Trust boundaries
| Boundary | Control |
|---|---|
| Internet -> API | Authentication required for every route except `/health/*`; signed HttpOnly session cookie or bearer token; CSRF token on cookie mutations; login rate limit. No anonymous read access. |
| Service -> sources | Read-only credentials in OBSERVE mode. Writer credentials are a separate secret that is not loaded on the read path. |
| Sources -> service | All source content (ad names, copy, MCP text) is untrusted data. It is never used as instructions; the LLM prompt says so and the validator rejects instruction-like content. |
| LLM -> service | Model output is parsed as JSON and validated: unknown refs/IDs/numbers, disallowed actions, gate contradictions and `execution_allowed=true` are rejected. The model has no tools and no path to write operations. |
| Service -> shops/Meta (writes) | `MODE=OBSERVE` + `EXECUTION_ENABLED=false` by default; a global `KILL_SWITCH` blocks any write; per-request preview -> policy checks -> approval with TTL -> fresh precondition hash -> apply -> verify -> audit. Timeouts never trigger blind retries. Only a MockWriter exists today. |

## Data protection
- Normalisers drop PII (email, phone, names, addresses) before anything is stored; customers are represented by a salted-free SHA-256 pseudonym of email+phone (no reversible data). Raw batches keep the pseudonymised records only.
- Raw retention 90 days, metrics/journal 24 months (configurable). Reports and exports contain aggregates only.
- Secrets come only from the environment; `doctor` and the Settings page print presence, never values. Historical notes containing secrets must not be copied into the repo.
- Backups: daily `pg_dump` job; encryption at rest and restore tests are host responsibilities (see RUNBOOK).

## Abuse cases considered
- Prompt injection through ad copy or MCP output -> validator + no tool access + human approval for any change.
- Many small budget changes bypassing a per-operation limit -> rolling 24h and per-account daily limits.
- Duplicate or replayed jobs -> UNIQUE(job, scheduled_for, scope), leases, idempotent upserts.
- Stale data interpreted as business failure -> DATA_ISSUE status, zero-orders-with-stale-sync rule, gates.
- Schema drift of an MCP tool -> schema hash recorded; changed schema disables only that adapter.

## Out of scope / residual risks
- The host, TLS termination and network perimeter of the VPS.
- Legal compliance of price presentation and claims (explicitly not covered by this system).
- A real Meta writer does not exist yet; adding one requires its own review of this document.
