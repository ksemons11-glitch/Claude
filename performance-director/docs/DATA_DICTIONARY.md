# Data dictionary (key definitions)

All money columns: `NUMERIC(20,6)` + currency; timestamps `timestamptz` (UTC) plus an explicit `business_date` (Europe/Warsaw local day, DST-aware).

## Views of revenue
| View | Definition | Where |
|---|---|---|
| Ordered | gross value of valid orders by the shop's `order_date_basis` (created or confirmed) | `daily_metrics.revenue_ordered`, `orders.gross_amount` |
| Expected (cohort) | probability-weighted revenue, costs and contribution of the acquisition day given the estimated final-state distribution | `cohort_metrics.expected_*`, `daily_metrics.expected_contribution`, `expected_result_after_ads` |
| Realized | contribution of orders already in a final state (DELIVERED/CANCELLED/UNDELIVERED/RETURNED) | `cohort_metrics.realized_contribution` |
| Cashflow | settlements and refunds by settlement/refund date - separate from cohorts | `daily_metrics.settlement_inflow`, `refund_outflow` |

## Metrics (`daily_metrics.metric`)
| Metric | Formula | Null reason |
|---|---|---|
| `mer_ordered` | ordered revenue / all marketing costs (flag `MER_VS_META_ONLY` when only Meta spend is known) | `ZERO_DENOMINATOR` |
| `roas_meta` | Meta purchase value / spend (same window & attribution setting) | |
| `roas_attributed_ordered` | attributed ordered revenue / spend | |
| `cpa_meta` | spend / Meta purchases | `ZERO_PURCHASES_WITH_SPEND` |
| `cpa_attributed` | spend / attributed valid orders (flag `NOT_NEW_CUSTOMER_CAC`) | |
| `aov`, `ctr_link`, `cpc_link`, `cpm` | standard; link clicks = `inline_link_clicks`, never `clicks` | |
| `be_cpa` | mean expected contribution before ads per order (same cohort definition) | `MISSING_COSTS` |
| `be_roas` | AOV / BE CPA, only when BE CPA > 0 | `NON_POSITIVE_BE_CPA` |
| `attribution_coverage_ad_orders` / `_revenue` | share of valid orders / revenue matched at AD level | |
| `*_w3`, `*_w7`, `*_w30` | ratio-of-sums over the preceding N full days (never averages of daily ratios) | |
| `spend_x_target_cpa` | ad spend / configured target CPA (zero-purchase tests) | `NO_DATA` when no target |

## Contribution (cohort) formula
`revenue retained after discounts and refunds + shipping retained - COGS of sold/lost goods (recovered returns keep value; `recovery_rate` models loss) - shipping - return shipping - fulfillment - payment/COD fees - other variable costs - ad spend`. Cost versions are selected by `valid_from/valid_to` and payment kind; each cost is counted once.

## Attribution
`order_attribution.level` AD > ADSET > CAMPAIGN > UNKNOWN; `method` (`utm_ad_id`, `legacy_alias`, `legacy_unique_name`, `utm_adset_id`, `utm_campaign_id`, `unmatched`...); `parser_version`. Legacy template (utm_content = ad.name) and id-based template are both parsed. Unknown orders are never spread by spend.

## Statuses
- Order `status_class`: OPEN, DELIVERED, CANCELLED, UNDELIVERED, RETURNED (from configured status IDs or name heuristics).
- Creative status: DRAFT → TEST → PROMISING → WINNER → SCALE; DECLINING → FATIGUED; LOSER; INCONCLUSIVE/PAUSED.
- Decision status: PROPOSED → APPROVED/REJECTED → EXECUTED → EVALUATING → SUCCESS/INCONCLUSIVE/FAILURE; EXPIRED.
- Job status: PENDING, RUNNING, RETRY, SUCCEEDED, FAILED.
- Report `completeness`: COMPLETE, PARTIAL, FAILED; `status`: NORMAL, WATCH, ACTION_REQUIRED, DATA_ISSUE, FAILED.

## Confidence
`confidence_class` LOW/MEDIUM/HIGH from components data_quality / sample_strength / consistency / confounding; `evidence_score` 0-100 is a deterministic *heuristic evidence quality*, not a probability.
