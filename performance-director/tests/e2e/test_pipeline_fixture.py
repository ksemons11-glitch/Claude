"""End-to-end acceptance scenarios (§20) run through the real pipeline on the deterministic demo fixtures.
Each test asserts the *behaviour* (what the report recommends / refuses), not exact synthetic numbers."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, update

from director import pipeline
from director.config import Mode, Settings, load_config
from director.db.models import (
    Campaign,
    Decision,
    Experiment,
    MarketAd,
    Recommendation,
    Report,
    Shop,
    SyncCheckpoint,
)
from director.decisions import journal
from director.demo.seed import generate
from director.diagnostics.engine import diagnose
from director.services import build_services

pytestmark = pytest.mark.db
END = date(2026, 9, 6)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def fixture_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("fixtures")
    generate(d, end_day=END)
    return d


@pytest.fixture()
def svc(db_url: str, fixture_dir: Path, session_factory):
    settings = Settings(
        database_url=db_url,
        config_dir=ROOT / "config",
        llm_provider="fake",
        mode=Mode.OBSERVE,
        app_auth_secret="x",
    )
    s = build_services(settings, fixture_dir=fixture_dir)
    s.set_clock(lambda: datetime(2026, 9, 7, 5, 30, tzinfo=UTC))
    return s


def _run(svc, day: date = END) -> Report:
    rid = pipeline.run_daily(svc, day)
    with svc.session_factory() as s:
        return s.get(Report, rid)


def _rules(report: Report) -> list[dict]:
    return report.body["diagnosis"]


def _actions(report: Report) -> list[dict]:
    return report.body["actions"]


def test_full_daily_run_produces_complete_report_with_max_5_actions(svc):
    rep = _run(svc)
    assert rep.completeness == "COMPLETE" and rep.status in ("WATCH", "ACTION_REQUIRED")
    assert len(_actions(rep)) <= 5 and rep.body["missing"] == ["MISSING_COSTS"]
    assert rep.llm_used is True and rep.model_name == "fake-1"
    shops = {r["shop_key"]: r for r in rep.body["shops"]}
    assert (
        shops["talio"]["expected_result_after_ads"] is None
        and shops["talio"]["uncertainty"] == "MISSING_COSTS"
    )  # scenario 18
    assert shops["veluskin"]["mer_label"] == "MER względem Meta"
    for row in rep.body["shops"]:
        assert row["evidence"]["orders"].startswith("metric:orders:shop:")


def test_scenario_1_single_weak_day_of_winner_is_hold_not_pause(svc):
    rep = _run(svc)
    velu = [r for r in _rules(rep) if r["entity_ref"] == "shop:veluskin"]
    assert any(r["candidate_action"] == "HOLD" and "Jednodniowa" in r["hypothesis"] for r in velu)
    assert not any(
        a["action_type"] in ("PAUSE_TEST", "PROPOSE_BUDGET_DECREASE") and "veluskin" in a["entity_ref"]
        for a in _actions(rep)
    )


def test_scenario_2_five_day_decline_yields_diagnosis_with_evidence(svc):
    rep = _run(svc)
    decline = [r for r in _rules(rep) if r["entity_ref"] == "shop:eloria" and "5 kolejnych dni" in r["fact"]]
    assert decline, [r["fact"] for r in _rules(rep) if r["entity_ref"] == "shop:eloria"]
    assert decline[0]["candidate_action"] == "DIAGNOSE" and "CTR" in decline[0]["hypothesis"]
    assert {
        "metric:roas_attributed_ordered:shop:eloria:2026-09-06",
        "metric:ctr_link:shop:eloria:2026-09-06",
    } <= set(decline[0]["evidence_refs"])


def test_scenario_3_meta_understated_is_measurement_hypothesis_without_multiplier(svc):
    rep = _run(svc)
    gap = [r for r in _rules(rep) if r["entity_ref"] == "shop:talio" and "Meta raportuje" in r["fact"]]
    assert (
        gap
        and "NIE stosować stałego przelicznika" in gap[0]["hypothesis"]
        and gap[0]["candidate_action"] == "DIAGNOSE"
    )
    body = rep.body
    assert "1,4" not in str(body["headline"]) and "1.4" not in str(body["headline"])


def test_scenario_4_stale_sync_becomes_data_issue_not_business_failure(svc):
    _run(svc)
    with svc.session_factory() as s:  # last successful order sync was days ago ...
        s.execute(update(SyncCheckpoint).values(last_success_at=datetime(2026, 9, 1, tzinfo=UTC)))
        s.commit()
    svc.adapters.baselinker.fail_streams = {
        "orders",
        "returns",
        "statuses",
        "open_orders",
    }  # ... and the source is down now
    rep = _run(svc)
    assert rep.status == "DATA_ISSUE" and rep.completeness == "PARTIAL"
    assert any("baselinker:orders:UNAVAILABLE" in m for m in rep.body["missing"])
    facts = [r for r in _rules(rep) if r["candidate_action"] == "INVESTIGATE_DATA"]
    assert facts and "nie orzekamy awarii biznesowej" in facts[0]["hypothesis"]
    assert not any(
        a["action_type"] in ("DIAGNOSE", "PROPOSE_BUDGET_DECREASE", "PROPOSE_BUDGET_INCREASE")
        for a in _actions(rep)
    )
    svc.adapters.baselinker.fail_streams = set()


def test_scenario_5_budget_change_yesterday_is_cooldown_and_never_a_failure(svc):
    rep = _run(svc)
    cool = [r for r in _rules(rep) if r["entity_ref"] == "campaign:120210000000000122"]
    assert cool and cool[0]["candidate_action"] == "HOLD" and "cooldown" in cool[0]["hypothesis"]
    # a decision executed on that change evaluated at 24h is INCONCLUSIVE (immature), never FAILURE
    with svc.session_factory() as s:
        d = Decision(
            entity_ref="campaign:120210000000000122",
            action_type="PROPOSE_BUDGET_INCREASE",
            reason="CBO 200->260",
            data_as_of=svc.now(),
            proposed_at=svc.now(),
            status="EVALUATING",
            verified_executed_at=datetime(2026, 9, 6, 8, 0, tzinfo=UTC),
            primary_metric="expected_result_after_ads",
        )
        s.add(d)
        s.flush()
        ev = journal.evaluate(
            s, d, horizon_hours=24, now=svc.now(), shop_key="czesio", tz_name="Europe/Warsaw"
        )
        assert ev.verdict == "INCONCLUSIVE" and "COD_COHORT_IMMATURE" in ev.confounders and d.outcome is None


def test_scenario_6_zero_purchases_over_explicit_loss_cap_is_pause_recommendation_not_execution(svc):
    rep = _run(svc)
    pause = [a for a in _actions(rep) if a["action_type"] == "PAUSE_TEST"]
    assert (
        pause and pause[0]["entity_ref"] == "ad:120210000000000323" and pause[0]["execution_allowed"] is False
    )
    assert pause[0]["rank"] == 1  # FAILURE_LOSS class ranks first
    assert "test_loss_cap" in pause[0]["fact"]
    with svc.session_factory() as s:
        recs = (
            s.execute(select(Recommendation).where(Recommendation.action_type == "PAUSE_TEST"))
            .scalars()
            .all()
        )
        assert recs and all(r.execution_allowed is False for r in recs)
        decisions = s.execute(select(Decision).where(Decision.action_type == "PAUSE_TEST")).scalars().all()
        assert decisions and all(
            d.status == "PROPOSED" for d in decisions
        )  # journal entry, no external write


def test_scenario_9_duplicate_asset_counts_once_and_legacy_utm_matches(svc):
    rep = _run(svc)
    with svc.session_factory() as s:
        from director.db.models import Creative, OrderAttribution

        czesio = s.execute(select(Shop).where(Shop.shop_key == "czesio")).scalar_one()
        creatives = s.execute(select(Creative).where(Creative.shop_id == czesio.id)).scalars().all()
        assert len(creatives) == 3  # 4 ads, two share vid_cz_por
        methods = {m for (m,) in s.execute(select(OrderAttribution.method).distinct())}
        assert (
            "legacy_ambiguous_same_campaign" in methods
            or "legacy_unique_name" in methods
            or "legacy_alias" in methods
        )
        assert "utm_ad_id" in methods
    eloria = next(r for r in rep.body["shops"] if r["shop_key"] == "eloria")
    assert eloria["coverage_ad_orders"] is not None


def test_scenario_14_and_16_market_scan_unavailable_or_imported(svc, fixture_dir):
    from director.creatives.market import compute_signals, market_concept_counts
    from director.ingestion.sync import sync_market

    rid = pipeline.run_weekly(svc, END)
    with svc.session_factory() as s:
        rep = s.get(Report, rid)
        assert rep.completeness == "PARTIAL" and any(
            "market scan" in m for m in rep.missing
        )  # nothing scanned yet -> no fictitious trends
        sync_market(s, svc, observed_on=END)
        s.commit()
        assert market_concept_counts(s) == {
            "morning-routine-speed": 5,
            "dermatologist-proof": 4,
            "kids-no-tears": 4,
        }  # 14 ads / 3 concepts, 12 unique media
        assert (
            s.execute(select(MarketAd)).scalars().all().__len__() == 13
        )  # duplicate media deduped within scan
        signals = compute_signals(s, window_end=END)
        assert signals and all(s_["coverage"] in ("FULL", "PARTIAL") for s_ in signals)
        assert all("brak dowodu rentowności" in s_["note"] for s_ in signals)  # scenario 15


def test_scenario_17_concentration_alert_without_switching_off_winner(svc):
    rep = _run(svc)
    conc = [
        r
        for r in _rules(rep)
        if r["entity_ref"].startswith("creative:") and "veluskin" in " ".join(r["evidence_refs"])
    ]
    assert conc and conc[0]["candidate_action"] == "BACKLOG_CONCEPT"
    assert any("veluskin" in x and "nie wyłączać" in x for x in rep.body["do_not_touch"])
    assert not any(a["action_type"] == "PAUSE_TEST" and "veluskin" in a["entity_ref"] for a in _actions(rep))


def test_scenario_18_missing_costs_block_scaling_gate(svc):
    _run(svc)
    with svc.session_factory() as s:
        talio = s.execute(select(Shop).where(Shop.shop_key == "talio")).scalar_one()
        cfg = load_config(ROOT / "config")
        ctx, _ = diagnose(s, shop=talio, day=END, as_of=svc.now(), policies=cfg.policies)
        from director.diagnostics.gates import blocking, evaluate_gates

        gates = evaluate_gates(ctx.gate_context(), cfg.policies.thresholds)
        assert "ECONOMICS_KNOWN" in blocking(gates, "PROPOSE_BUDGET_INCREASE")
        assert ctx.metrics["be_cpa"].reason == "MISSING_COSTS"


def test_scenario_20_rerun_creates_new_revision_and_respects_as_of(svc):
    r1 = _run(svc)
    r2 = _run(svc)
    assert (r1.revision, r2.revision) == (1, 2) and r2.revision_reason
    with svc.session_factory() as s:
        assert s.get(Report, r1.id) is not None  # history kept
        from director.metrics.aggregates import series

        early = series(
            s,
            scope="shop",
            key="veluskin",
            metric="orders",
            dates=[END],
            as_of=datetime(2026, 9, 1, tzinfo=UTC),
        )
        assert early == [None]  # nothing known before as_of -> no look-ahead leakage


def test_scenario_21_cbo_budget_is_not_summed_with_adsets(svc):
    _run(svc)
    with svc.session_factory() as s:
        cbo = s.execute(select(Campaign).where(Campaign.external_id == "120210000000000122")).scalar_one()
        abo = s.execute(select(Campaign).where(Campaign.external_id == "120210000000000121")).scalar_one()
        assert (
            cbo.budget_type == "CBO"
            and cbo.daily_budget == Decimal("260")
            and abo.budget_type == "ABO"
            and abo.daily_budget is None
        )
        from director.db.models import AdSet

        cbo_sets = s.execute(select(AdSet).where(AdSet.campaign_id == cbo.id)).scalars().all()
        assert all(a.daily_budget is None for a in cbo_sets)  # budgets live on the campaign only


def test_scenario_22_price_experiment_overlap_confounds_evaluation(svc):
    _run(svc)
    with svc.session_factory() as s:
        shop = s.execute(select(Shop).where(Shop.shop_key == "veluskin")).scalar_one()
        s.add(
            Experiment(
                shop_id=shop.id,
                hypothesis="cena 129 -> 119",
                scope={},
                kind="PRICE",
                primary_metric="cvr",
                status="RUNNING",
            )
        )
        d = Decision(
            entity_ref="shop:veluskin",
            action_type="PROPOSE_BUDGET_INCREASE",
            reason="skalowanie",
            data_as_of=svc.now(),
            proposed_at=svc.now(),
            status="EVALUATING",
            verified_executed_at=datetime(2026, 8, 29, 8, 0, tzinfo=UTC),
            primary_metric="expected_result_after_ads",
        )
        s.add(d)
        s.flush()
        ev = journal.evaluate(
            s, d, horizon_hours=168, now=svc.now(), shop_key="veluskin", tz_name="Europe/Warsaw"
        )
        assert (
            ev.verdict == "INCONCLUSIVE"
            and "PRICE_EXPERIMENT_OVERLAP" in ev.confounders
            and d.status == "INCONCLUSIVE"
        )


def test_observe_mode_has_no_write_path(svc):
    """No adapter in the set exposes a write method; execution module is disabled."""
    for name in ("meta", "baselinker", "nailuks", "gethooked"):
        adapter = getattr(svc.adapters, name)
        assert not any(
            m.startswith(("update", "create", "delete", "pause", "write", "set_")) for m in dir(adapter)
        )
    assert svc.settings.mode == Mode.OBSERVE and svc.settings.execution_enabled is False


def test_decision_journal_lifecycle_and_rejection_is_not_failure(svc):
    rep = _run(svc)
    with svc.session_factory() as s:
        rec = s.execute(select(Recommendation).where(Recommendation.report_id == rep.id)).scalars().first()
        d = s.execute(select(Decision).where(Decision.recommendation_id == rec.id)).scalar_one()
        journal.reject(s, d, actor="owner", now=svc.now(), correlation_id="c", reason="nie teraz")
        assert d.status == "REJECTED" and d.outcome is None
        d2 = journal.propose(s, rec, now=svc.now() - timedelta(days=4), data_as_of=svc.now())
        d2.expires_at = svc.now() - timedelta(hours=1)
        assert journal.expire_stale(s, now=svc.now()) >= 1 and d2.status == "EXPIRED"
