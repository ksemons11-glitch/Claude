from gate.rank import rank_ads, route_output, route_prompt
from gate.schemas import AdScore, BoolAnswer, OutputQA, PromptGate, ScoreAnswer


def S(level, conf=0.9):
    return ScoreAnswer(level=level, confidence=conf, reason="t")


def B(value, conf=0.9):
    return BoolAnswer(value=value, confidence=conf, reason="t")


def test_rank_weights_and_ip_drop():
    scored = {
        "best": AdScore(angle_strength=S(2), positioning_fit=S(2), reproducibility=S(2), borrowed_ip=B(False)),
        "mid": AdScore(angle_strength=S(1), positioning_fit=S(2), reproducibility=S(0), borrowed_ip=B(False)),
        "ip": AdScore(angle_strength=S(2), positioning_fit=S(2), reproducibility=S(2), borrowed_ip=B(True, 0.8)),
    }
    r = rank_ads(scored, top_n=10)
    assert [x.id for x in r if not x.dropped] == ["best", "mid"]
    assert r[0].score == 1.0 and abs(r[1].score - (0.45 * 0.5 + 0.40 * 1.0)) < 1e-6
    assert any(x.id == "ip" and x.dropped for x in r)


def test_route_prompt():
    clean = PromptGate(rule_conflict=B(False, 0.95), elements_present=B(True, 0.95), claim_risk=S(0, 0.95), completeness=S(2, 0.9))
    assert route_prompt(clean, hard_fail=False)[0] == "generate"
    assert route_prompt(clean, hard_fail=True)[0] == "reject"
    risky = clean.model_copy(update={"claim_risk": S(2, 0.9)})
    assert route_prompt(risky, hard_fail=False)[0] == "reject"
    unsure = clean.model_copy(update={"rule_conflict": B(True, 0.6)})
    assert route_prompt(unsure, hard_fail=False)[0] == "review"


def test_route_output():
    good = OutputQA(logo_correct=B(True, 0.95), palette_on_brand=B(True, 0.9), tone_match=S(2, 0.9),
                    unsupported_claim=B(False, 0.95), zone_shown=B(True, 0.9))
    assert route_output(good)[0] == "ship"
    bad = good.model_copy(update={"unsupported_claim": B(True, 0.9)})
    assert route_output(bad)[0] == "reject"
    meh = good.model_copy(update={"tone_match": S(2, 0.7)})
    assert route_output(meh)[0] == "review"
