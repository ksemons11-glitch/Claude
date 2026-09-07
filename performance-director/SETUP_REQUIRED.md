# SETUP_REQUIRED — what the owner must provide for live mode

Nothing here blocks the offline demo (`director demo seed` + `director run daily --mode fixture`). Live mode needs:

## 1. Runtime host
An always-on server/VPS with Docker Compose (or Python 3.12 + PostgreSQL 16). A laptop that is off runs nothing. Hosting and model budgets are configuration, not guesses.

## 2. Credentials (environment only, never in the repo)
| Variable | Purpose | Status |
|---|---|---|
| `BASELINKER_TOKEN` | read-only Baselinker API token | required for orders |
| `META_ACCESS_TOKEN`, `META_API_VERSION` | Marketing API read token (ads_read) and the Graph version verified on the day of setup | required for spend/structure |
| `NAILUKS_MCP_URL`, `NAILUKS_MCP_TOKEN` | Nailuks panel MCP endpoint; the private URL from the chat must not appear in code, reports or logs | optional (panel cross-check) |
| `GETHOOKED_MCP_URL`, `GETHOOKED_MCP_TOKEN` | competitor creatives; otherwise drop JSON/CSV into `config/market_import/` | optional |
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_DAILY_BUDGET_PLN` | interpretation model (provider `anthropic`, model id checked in the vendor docs at deployment time); budget 0 disables the LLM | optional (deterministic report without it) |
| `APP_AUTH_SECRET`, `APP_ADMIN_PASSWORD`, `APP_API_TOKEN` | panel/API authentication | required for the API |

## 3. Things to verify live before the first production report
- **Account mapping by ID** (`config/shops.yaml`): the historical table (Pooa/Lumina/Dzieciaki/Lenro ↔ act_… ↔ Base shop IDs) must be confirmed against the live accounts; set `mapping_verified_at` via `director connectors discover` output review. UI names are not identities.
- **Baselinker**: order status IDs → classes (`valid/cancelled/returned/delivered_statuses` per shop); which field carries UTM parameters (`custom_extra_fields`, `extra_field_1/2`, `order_source_info`); whether the returns module (`getOrderReturns`) is enabled; confirm the `id_from` pagination behaviour against the documentation.
- **Meta**: account currency/timezone (mismatch disables daily comparisons), attribution setting to use (`7d_click,1d_view` default), API version, field names in `adapters/meta.py` (written from public docs, not verified live).
- **Nailuks MCP**: real tool names and input schemas (hints: `nailuks_dane`, `nailuks_meta_ads`); definitions of panel “profit”, “real ROAS”, cost sources and sync timestamps. Arguments are only passed when they exist in the discovered schema.
- **Get Hooked**: whether media/transcripts, first/last seen, countries, brands and search exist; brand baskets in `config/competitors.yaml`.
- **UTM template migration**: the id-based template is a plan; do not edit active ads until the parser has been validated on legacy (`utm_content=ad.name`) orders.

## 4. Economics
- Real variable costs in `config/costs.yaml` (COGS per product, shipping, return shipping, fulfillment, COD/payment fees, recovery rate) with validity dates and net/gross basis. Without COGS the system reports “profit/BE unavailable” and blocks scaling recommendations.
- Portfolio limits: `portfolio_daily_cap_pln`, `cash_reserve_pln`, `cod_settlement_lag_days`, per-product `test_loss_cap_pln` and `target_cpa_pln` in `config/policies.yaml`. Missing values stay `null` and are shown as gates.
- Stock / fulfillment constraints (currently unknown → `PRODUCT_AVAILABLE` gate blocks spend increases).

## 5. Notifications
Default in-app. Email/Telegram/Discord adapters exist as `UnconfiguredChannel` until you name and authorize a recipient.

## 6. Execution (later stage, off by default)
`MODE=APPROVAL_REQUIRED`, `EXECUTION_ENABLED=true`, `execution.allowed_accounts` in policies, and a real writer with separate write credentials. None of this is needed for the analytical agent.
