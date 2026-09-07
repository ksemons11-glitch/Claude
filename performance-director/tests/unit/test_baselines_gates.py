from decimal import Decimal

from director.config import ThresholdsPolicy
from director.diagnostics.baselines import consecutive_signal, robust_z, wilson_interval
from director.diagnostics.gates import GateContext, blocking, evaluate_gates


def test_robust_z_insufficient_and_zero_mad():
    assert robust_z(5, [1, 2, 3], min_n=7).status == "INSUFFICIENT_BASELINE"
    rz = robust_z(9, [5, 5, 5, 5, 5, 5, 5, 5], min_n=7)
    assert rz.status == "ZERO_MAD_FALLBACK" and rz.z is not None and rz.z > 0
    rz2 = robust_z(20, [10, 12, 11, 13, 9, 10, 12, 11], min_n=7)
    assert rz2.status == "OK" and rz2.z > 3


def test_wilson_interval_for_two_purchases():
    lo, hi = wilson_interval(2, 50)
    assert 0.005 < lo < 0.02 and 0.12 < hi < 0.15
    assert wilson_interval(0, 0) is None


def test_consecutive_signal():
    assert consecutive_signal([False, True, True], 2) and not consecutive_signal([True, False], 2)


def ctx(**kw):
    base = dict(
        sources_fresh=True,
        pagination_complete=True,
        windows_compatible=True,
        economics_known=True,
        attribution_coverage=Decimal("0.9"),
        days_since_last_change=5,
        spend_window=Decimal("500"),
        be_cpa=Decimal("50"),
        purchases_window=12,
        conflicting_experiment=False,
        unexplained_failure=False,
        test_loss_cap_set=True,
        product_available=True,
    )
    base.update(kw)
    return GateContext(**base)


def test_gates_are_action_specific():
    th = ThresholdsPolicy()
    gates = evaluate_gates(ctx(product_available=None, days_since_last_change=1), th)
    assert set(blocking(gates, "PROPOSE_BUDGET_INCREASE")) == {"POST_CHANGE_WINDOW", "PRODUCT_AVAILABLE"}
    assert blocking(gates, "PAUSE_TEST") == []
    assert blocking(gates, "HOLD") == []
    g2 = evaluate_gates(
        ctx(economics_known=False, attribution_coverage=Decimal("0.5"), purchases_window=3), th
    )
    assert {"ECONOMICS_KNOWN", "ATTRIBUTION_COVERAGE", "EXPOSURE_SUFFICIENT"} <= set(
        blocking(g2, "PROPOSE_BUDGET_INCREASE")
    )
    assert blocking(evaluate_gates(ctx(test_loss_cap_set=False), th), "PAUSE_TEST") == ["TEST_LOSS_CAP_SET"]
