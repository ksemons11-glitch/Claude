"""CLI: python -m gate <command> ...

  check "tekst" [--headline H] [--subcopy S]     deterministic rules on one text
  rules-library                                   rules over brain/creative-library.csv + inspirations.csv
  score-ads ads.json [--judge stub|claude|manual] step 4: one typed answer set per ad, ranked in code
  gate-prompts prompts.json [--judge ...]         step 5: route each prompt generate/review/reject
  qa-output items.json [--judge ...]              step 7: ship/review/reject each generated output
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brain import Brain
from .judge import make_judge
from .rank import rank_ads, route_output, route_prompt
from .rules import check_text
from .writeback import record_rejection


def _load(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("items", [])


def cmd_check(a):
    rep = check_text(a.text, a.headline, a.subcopy)
    print(rep.summary())
    for v in rep.violations:
        print(f"  {v.severity:6} {v.rule_id:12} {v.message}  <- {sorted(set(v.matches))[:5]}")
    return 1 if rep.hard_fail else 0


def cmd_rules_library(a):
    brain = Brain()
    rows = []
    for r in brain.tables.get("creative-library", []):
        rep = check_text(r["body"], r.get("headline") or None)
        rows.append((r["copy_id"], rep))
    for r in brain.tables.get("inspirations", []):
        if r.get("pl_headline") and r["pl_headline"] not in ("—", "TODO"):
            rep = check_text(f'{r["pl_headline"]} {r["pl_subcopy"]}', r["pl_headline"], r["pl_subcopy"])
            rows.append((f'angle#{r["rank"]}', rep))
    fails = 0
    for cid, rep in rows:
        fails += rep.hard_fail
        print(f"{cid:10} {rep.summary()}")
    print(f"\n{len(rows)} items, {fails} hard fails, {len(rows) - fails} pass/warn")
    return 0


def _perf(tier) -> int | None:
    """'Optimized (86)' -> 86 (GetHookd performance tier label)."""
    import re
    m = re.search(r"\((\d+)\)", str(tier or ""))
    return int(m.group(1)) if m else None


def cmd_score_ads(a):
    brain = Brain(); judge = make_judge(a.judge, brain, Path(a.io))
    scored = {}
    for ad in _load(a.path):
        ad_id = str(ad.get("id"))
        try:
            scored[ad_id] = judge.score_ad(ad)
        except FileNotFoundError as e:
            print(f"[manual] {e}", file=sys.stderr)
    evidence = {str(ad.get("id")): (_perf(ad.get("tier")), ad.get("days_active")) for ad in _load(a.path)}
    ranked = rank_ads(scored, top_n=a.top, evidence=evidence)
    for r in ranked:
        s = scored[r.id]
        print(f"{r.id:22} score={r.score:.3f} {'DROPPED ' + r.reason if r.dropped else ''} "
              f"angle={s.angle_strength.level} fit={s.positioning_fit.level} repro={s.reproducibility.level} "
              f"ip={s.borrowed_ip.value}")
    if a.out:
        Path(a.out).write_text(json.dumps([{"id": r.id, "score": r.score, "dropped": r.dropped,
                                            **scored[r.id].model_dump()} for r in ranked], ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_gate_prompts(a):
    brain = Brain(); judge = make_judge(a.judge, brain, Path(a.io))
    results = []
    for p in _load(a.path):
        text = " ".join(str(p.get(k, "")) for k in ("headline", "subcopy", "prompt", "body"))
        rep = check_text(text, p.get("headline"), p.get("subcopy"))
        try:
            g = judge.gate_prompt(p)
        except FileNotFoundError as e:
            print(f"[manual] {e}", file=sys.stderr); continue
        decision, why = route_prompt(g, rep.hard_fail)
        results.append({"id": p.get("id"), "decision": decision, "why": why, "rules": rep.summary(), **g.model_dump()})
        print(f"{str(p.get('id')):16} {decision.upper():9} {why} | rules: {rep.summary()}")
        if decision == "reject" and a.writeback:
            record_rejection(str(p.get("id")), "prompt", f"{why}; {rep.summary()}")
    if a.out:
        Path(a.out).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_qa_output(a):
    brain = Brain(); judge = make_judge(a.judge, brain, Path(a.io))
    for item in _load(a.path):
        try:
            q = judge.qa_output(item)
        except FileNotFoundError as e:
            print(f"[manual] {e}", file=sys.stderr); continue
        decision, why = route_output(q)
        print(f"{str(item.get('id')):16} {decision.upper():7} {why}")
        if decision == "reject" and a.writeback:
            record_rejection(str(item.get("id")), "output", why)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gate", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("text"); c.add_argument("--headline"); c.add_argument("--subcopy"); c.set_defaults(fn=cmd_check)
    sub.add_parser("rules-library").set_defaults(fn=cmd_rules_library)
    for name, fn in (("score-ads", cmd_score_ads), ("gate-prompts", cmd_gate_prompts), ("qa-output", cmd_qa_output)):
        p = sub.add_parser(name); p.add_argument("path")
        p.add_argument("--judge", choices=["stub", "claude", "manual"], default="stub")
        p.add_argument("--io", default="judge-io"); p.add_argument("--out"); p.add_argument("--top", type=int, default=10)
        p.add_argument("--writeback", action="store_true"); p.set_defaults(fn=fn)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
