"""Rule library. Rules are pure functions over a ShopContext; they never touch the LLM.
Each returns a RuleResult or None. Priority classes: FAILURE_LOSS > RISK > PROFIT > EXPLORATION."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from director.config import PoliciesConfig
from director.contracts.common import ConfidenceClass, MetricValue, Severity
from director.contracts.rules import Gate, RuleResult
from director.diagnostics.baselines import consecutive_signal, robust_z
from director.diagnostics.confidence import Components, confidence_class, evidence_score, sample_level
from director.diagnostics.gates import GateContext, blocking, evaluate_gates

RULES_VERSION = "1"


@dataclass
class EntityContext:
    ref: str  # ad:<ext>
    name: str
    metrics: dict[str, MetricValue]
    spend_since_start: Decimal
    purchases_since_start: int
    days_running: int
    product_key: str | None
    creative_key: str | None = None
    daily_history: dict[str, list[Decimal | None]] = field(default_factory=dict)
    days_since_change: int | None = None  # for this ad's own ad/adset/campaign chain


@dataclass
class ShopContext:
    shop_key: str
    day: date
    metrics: dict[str, MetricValue]  # D-1 shop metrics
    history: dict[str, list[Decimal | None]]  # metric -> values for preceding 28 days (oldest first)
    windows: dict[str, MetricValue]  # *_w3/_w7/_w30
    entities: list[EntityContext]
    dq_critical: list[str]
    dq_watch: list[str]
    sources_fresh: bool
    pagination_complete: bool
    windows_compatible: bool
    days_since_last_change: int | None
    recent_changes: list[dict[str, Any]]
    active_experiments: list[dict[str, Any]]
    concentration: dict[str, Any]
    orders_yesterday: int
    policies: PoliciesConfig
    target_cpa: Decimal | None
    test_loss_cap: Decimal | None
    stock_known: bool | None = None

    def m(self, name: str) -> Decimal | None:
        mv = self.metrics.get(name)
        return mv.value if mv else None

    def gate_context(self, entity: EntityContext | None = None) -> GateContext:
        be = self.m("be_cpa")
        dsl = entity.days_since_change if entity is not None else self.days_since_last_change
        return GateContext(
            sources_fresh=self.sources_fresh,
            pagination_complete=self.pagination_complete,
            windows_compatible=self.windows_compatible,
            economics_known=self.metrics.get("expected_contribution", MetricValue(metric="x")).available,
            attribution_coverage=self.m("attribution_coverage_ad_orders"),
            days_since_last_change=dsl,
            spend_window=self.windows.get("spend_w7", MetricValue(metric="x")).value,
            be_cpa=be,
            purchases_window=int(self.windows.get("purchases_meta_w7", MetricValue(metric="x")).value or 0),
            conflicting_experiment=bool(self.active_experiments),
            unexplained_failure=bool(self.dq_critical),
            test_loss_cap_set=self.test_loss_cap is not None,
            product_available=self.stock_known,
        )


def _components(ctx: ShopContext, *, consistency: str, confounding: str | None = None) -> Components:
    dq = "LOW" if ctx.dq_critical else ("MEDIUM" if ctx.dq_watch else "HIGH")
    sample = sample_level(ctx.orders_yesterday, ctx.policies.thresholds.low_sample_orders)
    conf = confounding or (
        "LOW"
        if (
            ctx.days_since_last_change is not None
            and ctx.days_since_last_change < ctx.policies.thresholds.min_full_days_since_change
        )
        or ctx.active_experiments
        else "HIGH"
    )
    return Components(dq, sample, consistency, conf)


def _result(
    ctx: ShopContext,
    rule_id: str,
    entity_ref: str,
    *,
    severity: Severity,
    fact: str,
    hypothesis: str,
    action: str,
    evidence: list[str],
    comps: Components,
    priority: str,
    impact: str = "LOW",
    urgency: str = "LOW",
    effort: str = "LOW",
    observed: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    gates: list[Gate] | None = None,
    window: str = "D-1",
) -> RuleResult:
    gates = gates if gates is not None else []
    return RuleResult(
        rule_id=rule_id,
        rule_version=RULES_VERSION,
        entity_ref=entity_ref,
        business_date=ctx.day,
        metric_window=window,
        baseline=baseline or {},
        observed=observed or {},
        evidence_refs=evidence,
        severity=severity,
        fact=fact,
        hypothesis=hypothesis,
        missing_data=missing or [],
        candidate_action=action,
        gates=gates,
        blocking_gates=blocking(gates, action),
        confidence=confidence_class(comps),
        confidence_components=comps.as_dict(),
        evidence_score=evidence_score(comps),
        priority_class=priority,
        impact=impact,
        urgency=urgency,
        effort=effort,
    )


def _fmt(v: Any) -> str:
    try:
        d = Decimal(str(v))
        return f"{d.normalize():f}" if d == d.to_integral() else f"{d:.2f}"
    except Exception:  # noqa: BLE001
        return str(v)


def _ev(
    ctx: ShopContext, metric: str, scope: str = "shop", key: str | None = None, day: date | None = None
) -> str:
    return f"metric:{metric}:{scope}:{key or ctx.shop_key}:{(day or ctx.day).isoformat()}"


# ------------------------------------------------------------------------------------------ rules


def rule_data_issue(ctx: ShopContext) -> RuleResult | None:
    if not ctx.dq_critical:
        return None
    zero_orders = ctx.orders_yesterday == 0
    fact = f"Krytyczne problemy danych: {', '.join(ctx.dq_critical)}" + (
        " - zamówienia = 0 przy nieaktualnym sync" if zero_orders else ""
    )
    comps = Components("LOW", "LOW", "LOW", "LOW")
    return _result(
        ctx,
        "R_DATA_ISSUE",
        f"shop:{ctx.shop_key}",
        severity=Severity.CRITICAL,
        fact=fact,
        hypothesis="Brak aktualnych danych z integracji; nie orzekamy awarii biznesowej ani pogorszenia reklam",
        action="INVESTIGATE_DATA",
        evidence=[f"dq:{k}" for k in ctx.dq_critical],
        comps=comps,
        priority="FAILURE_LOSS",
        impact="HIGH",
        urgency="HIGH",
        effort="MEDIUM",
        missing=ctx.dq_critical,
    )


def rule_missing_costs(ctx: ShopContext) -> RuleResult | None:
    mv = ctx.metrics.get("expected_contribution")
    if mv is None or mv.available:
        return None
    comps = Components("MEDIUM", "HIGH", "HIGH", "HIGH")
    return _result(
        ctx,
        "R_MISSING_COSTS",
        f"shop:{ctx.shop_key}",
        severity=Severity.WATCH,
        fact="Brak kosztów produktu: wynik po kosztach i BE CPA niedostępne",
        hypothesis="Konfiguracja kosztów niekompletna",
        action="HOLD",
        evidence=[_ev(ctx, "expected_contribution"), _ev(ctx, "be_cpa")],
        comps=comps,
        priority="RISK",
        impact="MEDIUM",
        urgency="MEDIUM",
        missing=["COGS"],
        gates=evaluate_gates(ctx.gate_context(), ctx.policies.thresholds),
    )


def rule_single_day_deviation(ctx: ShopContext) -> RuleResult | None:
    """One weak (or strong) day of an otherwise stable shop -> HOLD/WATCH, never a switch-off."""
    metric = (
        "expected_result_after_ads"
        if ctx.metrics.get("expected_result_after_ads", MetricValue(metric="x")).available
        else "revenue_ordered"
    )
    x = ctx.m(metric)
    hist = ctx.history.get(metric, [])
    rz = robust_z(x, hist, min_n=ctx.policies.thresholds.min_baseline_days)
    if not rz.usable or rz.z is None:
        return None
    th = ctx.policies.thresholds
    if abs(rz.z) < float(th.robust_z_watch):
        return None
    # do not fire if the deviation is already a multi-day trend (handled by rule_sustained_decline)
    below = [(v is not None and rz.median is not None and float(v) < rz.median) for v in hist[-3:]] + [
        rz.z < 0
    ]
    consecutive = consecutive_signal(below, 3)
    if consecutive:
        return None
    direction = "słabszy" if rz.z < 0 else "mocniejszy"
    comps = _components(ctx, consistency="LOW")
    sev = Severity.WATCH if abs(rz.z) >= float(th.robust_z_critical) else Severity.INFO
    return _result(
        ctx,
        "R_SINGLE_DAY_DEVIATION",
        f"shop:{ctx.shop_key}",
        severity=sev,
        fact=f"Dzień {ctx.day} {direction} od mediany 28 dni ({metric}: {_fmt(x)} vs mediana {rz.median:.2f}, robust z={rz.z:.1f})",
        hypothesis="Jednodniowa zmienność; brak potwierdzenia trendu",
        action="HOLD",
        evidence=[_ev(ctx, metric)],
        comps=comps,
        priority="EXPLORATION",
        impact="MEDIUM",
        observed={"value": str(x), "z": round(rz.z, 2)},
        baseline={"median": rz.median, "mad": rz.mad, "n": rz.n, "status": rz.status},
    )


def rule_sustained_decline(ctx: ShopContext) -> RuleResult | None:
    metric = "roas_attributed_ordered"
    hist = ctx.history.get(metric, [])
    x = ctx.m(metric)
    if x is None or len(hist) < 12:
        return None
    base = hist[:-4]
    rz = robust_z(x, base, min_n=ctx.policies.thresholds.min_baseline_days)
    if not rz.usable or rz.median is None:
        return None
    last5 = hist[-4:] + [x]
    below = [(v is not None and float(v) < rz.median * 0.85) for v in last5]
    if not all(below):
        return None
    ctr_hist, cpm_hist = ctx.history.get("ctr_link", []), ctx.history.get("cpm", [])
    ctr_now, cpm_now = ctx.m("ctr_link"), ctx.m("cpm")
    ctr_z = robust_z(ctr_now, ctr_hist[:-4], min_n=ctx.policies.thresholds.min_baseline_days)
    cpm_z = robust_z(cpm_now, cpm_hist[:-4], min_n=ctx.policies.thresholds.min_baseline_days)
    if (
        ctr_z.usable
        and ctr_z.z is not None
        and ctr_z.z < -1.5
        and (not cpm_z.usable or abs(cpm_z.z or 0) < 1.5)
    ):
        hyp = "Spadek atrakcyjności kreacji (CTR spada przy stabilnym CPM); sprawdź exposure, mix odbiorców, konkurujące kreacje, URL i ofertę"
    elif cpm_z.usable and cpm_z.z is not None and cpm_z.z > 1.5:
        hyp = "Droższa aukcja lub zmiana mixu ruchu (CPM wzrósł); sprawdź placement, targeting, budżet, sezon, rozkład urządzeń"
    else:
        hyp = "Problem strony/oferty albo jakości ruchu (CPC stabilny, zamówienia na klik spadają); potwierdź sesjami, checkoutem, płatnościami, zmianami ceny"
    comps = _components(ctx, consistency="HIGH")
    gates = evaluate_gates(ctx.gate_context(), ctx.policies.thresholds)
    return _result(
        ctx,
        "R_SUSTAINED_DECLINE",
        f"shop:{ctx.shop_key}",
        severity=Severity.WATCH,
        fact=f"{metric} poniżej 85% mediany bazowej ({rz.median:.2f}) przez 5 kolejnych dni; dziś {_fmt(x)}",
        hypothesis=hyp,
        action="DIAGNOSE",
        evidence=[_ev(ctx, metric), _ev(ctx, "ctr_link"), _ev(ctx, "cpm")],
        comps=comps,
        priority="PROFIT",
        impact="HIGH",
        urgency="MEDIUM",
        effort="MEDIUM",
        observed={"last5": [str(v) for v in last5], "ctr_z": ctr_z.z, "cpm_z": cpm_z.z},
        baseline={"median": rz.median, "n": rz.n},
        gates=gates,
        window="5D",
    )


def rule_meta_vs_ledger_gap(ctx: ShopContext) -> RuleResult | None:
    meta_p = ctx.windows.get("purchases_meta_w7", MetricValue(metric="x")).value
    attributed = ctx.windows.get("attributed_orders_w7", MetricValue(metric="x")).value
    roas_meta_hist = ctx.history.get("roas_meta", [])
    roas_led = ctx.history.get("roas_attributed_ordered", [])
    if meta_p is None or attributed is None or attributed == 0:
        return None
    gap = (attributed - meta_p) / attributed
    if gap < Decimal("0.20"):
        return None
    led_z = robust_z(
        ctx.m("roas_attributed_ordered"), roas_led[:-1], min_n=ctx.policies.thresholds.min_baseline_days
    )
    stable = (not led_z.usable) or abs(led_z.z or 0) < 1.5
    _ = roas_meta_hist
    comps = _components(ctx, consistency="MEDIUM")
    return _result(
        ctx,
        "R_META_VS_LEDGER_GAP",
        f"shop:{ctx.shop_key}",
        severity=Severity.INFO if stable else Severity.WATCH,
        fact=f"Meta raportuje {_fmt(meta_p)} zakupów (7 dni) wobec {_fmt(attributed)} przypisanych zamówień w panelu/Base ({gap:.0%} luki)"
        + ("; wynik kohort stabilny" if stable else ""),
        hypothesis="Pomiar/atrybucja (COD, lag, UTM, konfiguracja pixel). NIE stosować stałego przelicznika 1,25-1,40 - hipoteza wymaga weryfikacji per sklep",
        action="DIAGNOSE",
        evidence=[
            _ev(ctx, "purchases_meta_w7"),
            _ev(ctx, "attributed_orders_w7"),
            _ev(ctx, "roas_attributed_ordered"),
        ],
        comps=comps,
        priority="EXPLORATION",
        impact="MEDIUM",
        observed={"gap": str(gap)},
        window="7D",
    )


def rule_recent_change_cooldown(ctx: ShopContext) -> RuleResult | None:
    if (
        ctx.days_since_last_change is None
        or ctx.days_since_last_change >= ctx.policies.thresholds.min_full_days_since_change
    ):
        return None
    ch = ctx.recent_changes[0] if ctx.recent_changes else {}
    comps = _components(ctx, consistency="LOW", confounding="LOW")
    return _result(
        ctx,
        "R_RECENT_CHANGE_COOLDOWN",
        ch.get("entity_ref", f"shop:{ctx.shop_key}"),
        severity=Severity.INFO,
        fact=f"Zmiana {ch.get('field', '?')} {_fmt(ch.get('before'))} → {_fmt(ch.get('after'))} zaobserwowana {ch.get('observed_to', '')[:10]}; {ctx.days_since_last_change} pełnych dni od zmiany",
        hypothesis="Za wcześnie na ocenę skutku; decyzja pozostaje w oknie cooldown i nie jest oceniana jako porażka",
        action="HOLD",
        evidence=[f"structure_change:{ch.get('id', '')}"],
        comps=comps,
        priority="EXPLORATION",
        impact="LOW",
        urgency="LOW",
        gates=evaluate_gates(ctx.gate_context(), ctx.policies.thresholds),
    )


def rule_test_loss_cap(ctx: ShopContext) -> list[RuleResult]:
    out: list[RuleResult] = []
    for e in ctx.entities:
        if e.purchases_since_start > 0 or e.spend_since_start <= 0:
            continue
        pp = ctx.policies.product(ctx.shop_key, e.product_key or ctx.shop_key) or ctx.policies.product(
            ctx.shop_key, ctx.shop_key
        )
        cap = pp.test_loss_cap_pln if pp else None
        tcpa = (pp.target_cpa_pln if pp else None) or ctx.target_cpa
        mult = (e.spend_since_start / tcpa) if tcpa else None
        base_fact = (
            f"{e.name}: {e.spend_since_start:.0f} PLN wydane, 0 zakupów przez {e.days_running} dni"
            + (f" (= {mult:.1f}× docelowego CPA)" if mult is not None else "")
        )
        if cap is not None and e.spend_since_start > cap:
            comps = _components(ctx, consistency="HIGH", confounding="HIGH")
            out.append(
                _result(
                    ctx,
                    "R_TEST_LOSS_CAP_EXCEEDED",
                    e.ref,
                    severity=Severity.CRITICAL,
                    fact=base_fact + f"; przekroczony test_loss_cap {cap} PLN",
                    hypothesis="Test nie generuje zakupów; limit strat przekroczony niezależnie od etykiety WINNER/LOSER",
                    action="PAUSE_TEST",
                    evidence=[
                        f"metric:spend_x_target_cpa:ad:{e.ref.split(':', 1)[1]}:{ctx.day.isoformat()}",
                        f"policy:test_loss_cap:{ctx.shop_key}",
                    ],
                    comps=comps,
                    priority="FAILURE_LOSS",
                    impact="MEDIUM",
                    urgency="HIGH",
                    effort="LOW",
                    observed={"spend": str(e.spend_since_start), "cap": str(cap)},
                    gates=evaluate_gates(ctx.gate_context(e), ctx.policies.thresholds),
                )
            )
        elif mult is not None and mult >= ctx.policies.thresholds.spend_multiple_of_target_cpa_alert:
            comps = _components(ctx, consistency="MEDIUM")
            out.append(
                _result(
                    ctx,
                    "R_ZERO_PURCHASES_SPEND_MULTIPLE",
                    e.ref,
                    severity=Severity.WATCH,
                    fact=base_fact
                    + (
                        "; brak jawnego test_loss_cap → brak automatycznej rekomendacji zatrzymania"
                        if cap is None
                        else ""
                    ),
                    hypothesis="Test bez zakupów; obserwować do limitu strat",
                    action="WATCH",
                    evidence=[f"metric:spend_x_target_cpa:ad:{e.ref.split(':', 1)[1]}:{ctx.day.isoformat()}"],
                    comps=comps,
                    priority="RISK",
                    impact="LOW",
                    urgency="MEDIUM",
                    observed={"spend": str(e.spend_since_start), "multiple": str(mult)},
                    missing=[] if cap is not None else ["test_loss_cap"],
                )
            )
    return out


def rule_concentration(ctx: ShopContext) -> RuleResult | None:
    share = ctx.concentration.get("top_share")
    if share is None or share < ctx.policies.thresholds.concentration_alert_share:
        return None
    attributed_w7 = ctx.windows.get("attributed_orders_w7", MetricValue(metric="x")).value
    if attributed_w7 is None or attributed_w7 < ctx.policies.thresholds.min_purchases_for_cpa_compare:
        return None  # too few attributed orders to call it concentration
    second = ctx.concentration.get("second_share") or Decimal(0)
    comps = _components(ctx, consistency="HIGH")
    return _result(
        ctx,
        "R_CREATIVE_CONCENTRATION",
        f"creative:{ctx.concentration['top_creative']}",
        severity=Severity.WATCH,
        fact=f"{share:.0%} przypisanego przychodu (7 dni) pochodzi z jednej kreacji; druga kreacja {second:.0%}; brak niezależnego winnera",
        hypothesis="Koncentracja ryzyka na jednym koncepcie",
        action="BACKLOG_CONCEPT",
        evidence=[f"concentration:{ctx.shop_key}:{ctx.day.isoformat()}"],
        comps=comps,
        priority="RISK",
        impact="MEDIUM",
        urgency="LOW",
        effort="MEDIUM",
        observed={
            k: str(v) for k, v in ctx.concentration.items() if k in ("top_share", "second_share", "creatives")
        },
    )


def rule_strong_day(ctx: ShopContext) -> RuleResult | None:
    metric = "expected_result_after_ads"
    x = ctx.m(metric)
    rz = robust_z(x, ctx.history.get(metric, []), min_n=ctx.policies.thresholds.min_baseline_days)
    if not rz.usable or rz.z is None or rz.z < float(ctx.policies.thresholds.robust_z_critical):
        return None
    comps = _components(ctx, consistency="LOW")
    return _result(
        ctx,
        "R_STRONG_DAY",
        f"shop:{ctx.shop_key}",
        severity=Severity.INFO,
        fact=f"Bardzo mocny dzień ({metric}={_fmt(x)}, z={rz.z:.1f})",
        hypothesis="Pojedynczy silny wynik; alert obserwacji, nie automatyczne skalowanie",
        action="WATCH",
        evidence=[_ev(ctx, metric)],
        comps=comps,
        priority="EXPLORATION",
    )


ALL_RULES = [
    rule_data_issue,
    rule_missing_costs,
    rule_recent_change_cooldown,
    rule_single_day_deviation,
    rule_sustained_decline,
    rule_meta_vs_ledger_gap,
    rule_concentration,
    rule_strong_day,
]


def run_rules(ctx: ShopContext) -> list[RuleResult]:
    out: list[RuleResult] = []
    for r in ALL_RULES:
        res = r(ctx)
        if res:
            out.append(res)
    out.extend(rule_test_loss_cap(ctx))
    if ctx.dq_critical:  # data issue suppresses performance verdicts but keeps loss-cap and cooldown facts
        out = [
            r
            for r in out
            if r.rule_id
            in ("R_DATA_ISSUE", "R_TEST_LOSS_CAP_EXCEEDED", "R_RECENT_CHANGE_COOLDOWN", "R_MISSING_COSTS")
        ]
    return out


PRIORITY_ORDER = {"FAILURE_LOSS": 0, "RISK": 1, "PROFIT": 2, "EXPLORATION": 3}
LEVEL_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
CONF_ORDER = {ConfidenceClass.HIGH: 0, ConfidenceClass.MEDIUM: 1, ConfidenceClass.LOW: 2}


def prioritize(results: list[RuleResult]) -> list[RuleResult]:
    return sorted(
        results,
        key=lambda r: (
            PRIORITY_ORDER[r.priority_class],
            LEVEL_ORDER[r.impact],
            LEVEL_ORDER[r.urgency],
            CONF_ORDER[r.confidence],
            -LEVEL_ORDER[r.effort],
        ),
    )
