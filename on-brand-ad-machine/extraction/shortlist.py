"""Step 4 — shortlist: judge answers (extraction/judge-answers.json) -> gate manual judge -> rank_ads (code) -> top 10.

    python3 extraction/shortlist.py          # writes extraction/all-ads.json, shortlist.json, shortlist.md

Ranking coefficients live in gate/gate/rank.py (0.45 angle / 0.40 fit / 0.15 repro; drop if P(borrowed_ip) > 0.6).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "gate"))
from gate.brain import Brain            # noqa: E402
from gate.judge import ManualJudge      # noqa: E402
from gate.rank import BORROWED_IP_DROP, PROVEN_MIN_DAYS, PROVEN_MIN_PERF, WEIGHTS, is_proven, rank_ads  # noqa: E402
import re  # noqa: E402

EXTRACTION = ROOT / "extraction"
SKIP = {"wrinkles-schminkles-test.json", "all-ads.json", "judge-answers.json", "shortlist.json"}


def load_ads() -> list[dict]:
    ads = []
    for f in sorted(EXTRACTION.glob("*.json")):
        if f.name in SKIP:
            continue
        ads.extend(json.loads(f.read_text(encoding="utf-8")).get("ads", []))
    return ads


def main() -> int:
    ads = load_ads()
    answers = json.loads((EXTRACTION / "judge-answers.json").read_text(encoding="utf-8"))
    io = ROOT / "gate" / "judge-io"
    io.mkdir(exist_ok=True)
    for ad_id, ans in answers.items():
        if not ad_id.startswith("_"):
            (io / f"score-{ad_id}.answer.json").write_text(json.dumps(ans, ensure_ascii=False), encoding="utf-8")

    (EXTRACTION / "all-ads.json").write_text(json.dumps({"items": ads}, ensure_ascii=False, indent=1), encoding="utf-8")
    judge = ManualJudge(Brain(), io)
    by_id = {str(a["id"]): a for a in ads}
    scored = {str(a["id"]): judge.score_ad(a) for a in ads}

    def perf(a):
        m = re.search(r"\((\d+)\)", str(a.get("tier") or ""))
        return int(m.group(1)) if m else None
    evidence = {str(a["id"]): (perf(a), a.get("days_active")) for a in ads}
    ranked = rank_ads(scored, top_n=10, evidence=evidence)
    kept = [r for r in ranked if not r.dropped]
    dropped = [r for r in ranked if r.dropped and r.reason == "borrowed_ip"]
    # fresh = good idea by the judge, but Testing-tier and days old: a hypothesis to re-check, not an inspiration
    fresh = [r for r in rank_ads(scored, top_n=len(scored)) if not r.dropped
             and not is_proven(*evidence[r.id]) and r.score >= 0.7]

    # full table (every ad, sorted like rank_ads would) for the write-up
    all_ranked = rank_ads(scored, top_n=len(scored), evidence=evidence)
    rows = []
    for r in all_ranked:
        a, s = by_id[r.id], scored[r.id]
        rows.append({"id": r.id, "brand": a["brand"], "set": a.get("set"), "format": a.get("format"), "tier": a.get("tier"),
                     "performance_score": evidence[r.id][0], "proven": is_proven(*evidence[r.id]),
                     "days_active": a.get("days_active"), "score": r.score, "dropped": r.dropped, "drop_reason": r.reason,
                     "headline": a.get("headline"), "transcript_state": a.get("transcript_state"),
                     "levels": {"angle": s.angle_strength.level, "fit": s.positioning_fit.level,
                                "repro": s.reproducibility.level, "borrowed_ip": s.borrowed_ip.value},
                     "reasons": {"angle": s.angle_strength.reason, "fit": s.positioning_fit.reason,
                                 "repro": s.reproducibility.reason, "borrowed_ip": s.borrowed_ip.reason},
                     "claims": a.get("claims", [])})
    out = {"weights": WEIGHTS, "borrowed_ip_drop": BORROWED_IP_DROP,
           "proven_rule": f"performance_score >= {PROVEN_MIN_PERF} or days_active >= {PROVEN_MIN_DAYS}",
           "judged": len(scored), "top10": [r.id for r in kept], "dropped_borrowed_ip": [r.id for r in dropped],
           "fresh_hypotheses": [r.id for r in fresh], "ads": rows}
    (EXTRACTION / "shortlist.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in kept:
        a = by_id[r.id]
        print(f"{r.id:12} {r.score:.3f}  {str(a.get('tier')):15} {a.get('days_active'):3}d  {a['brand'][:14]:14} {str(a.get('headline'))[:50]}")
    print(f"\n{len(scored)} judged, top {len(kept)} proven, {len(dropped)} dropped for borrowed IP, "
          f"{len(fresh)} fresh hypotheses (unproven, judge >= 0.7): {[r.id for r in fresh]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
