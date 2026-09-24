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
from gate.rank import BORROWED_IP_DROP, WEIGHTS, rank_ads  # noqa: E402

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
    ranked = rank_ads(scored, top_n=10)
    kept = [r for r in ranked if not r.dropped]
    dropped = [r for r in ranked if r.dropped]

    # full table (every ad, sorted like rank_ads would) for the write-up
    all_ranked = rank_ads(scored, top_n=len(scored))
    rows = []
    for r in all_ranked:
        a, s = by_id[r.id], scored[r.id]
        rows.append({"id": r.id, "brand": a["brand"], "set": a.get("set"), "format": a.get("format"), "tier": a.get("tier"),
                     "days_active": a.get("days_active"), "score": r.score, "dropped": r.dropped,
                     "headline": a.get("headline"), "transcript_state": a.get("transcript_state"),
                     "levels": {"angle": s.angle_strength.level, "fit": s.positioning_fit.level,
                                "repro": s.reproducibility.level, "borrowed_ip": s.borrowed_ip.value},
                     "reasons": {"angle": s.angle_strength.reason, "fit": s.positioning_fit.reason,
                                 "repro": s.reproducibility.reason, "borrowed_ip": s.borrowed_ip.reason},
                     "claims": a.get("claims", [])})
    out = {"weights": WEIGHTS, "borrowed_ip_drop": BORROWED_IP_DROP, "judged": len(scored),
           "top10": [r.id for r in kept], "dropped_borrowed_ip": [r.id for r in dropped], "ads": rows}
    (EXTRACTION / "shortlist.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in kept:
        a = by_id[r.id]
        print(f"{r.id:12} {r.score:.3f}  {a['brand'][:20]:20} {str(a.get('headline'))[:60]}")
    print(f"\n{len(scored)} judged, top {len(kept)}, {len(dropped)} dropped for borrowed IP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
