# Gate — decision layer for the On-Brand Ad Machine (Jev-compatible, Jev-free)

Three stages from the plan, same questions and answer shapes as the Jev schemas, with a **pluggable judge**:

| Stage | Command | What decides |
|---|---|---|
| Deterministic copy rules | `python -m gate check "…"` / `rules-library` | regex from `brain/copy-rules.csv` + `brain/claims.csv` — `must` = hard fail, no model can override |
| 4. Shortlist competitor ads | `score-ads ads.json` | judge answers 4 typed questions per ad → **rank in code** (0.45 / 0.40 / 0.15, drop `borrowed_ip` > 0.6) |
| 5. Gate prompts before generation | `gate-prompts prompts.json` | rules + judge → `generate` / `review` / `reject` (plan thresholds) |
| 7. QA generated outputs | `qa-output items.json` | judge sees the image (or its description) → `ship` > 0.85 on all / `review` in band / `reject` |

Judges: `--judge claude` (Anthropic SDK, `claude-opus-5`, structured output via `messages.parse`, needs credentials),
`--judge manual` (writes `judge-io/*.request.json`; an in-session reviewer writes `*.answer.json`), `--judge stub` (offline heuristic from the rules).
Swap Jev in later by adding a fourth backend — the questions and shapes are already Jev's.

Every `reject` with `--writeback` appends a labelled row to `brain/campaign-learnings.csv` (the brand-side feedback loop).

```
cd on-brand-ad-machine/gate
pip install -r requirements.txt
python -m pytest -q
python -m gate rules-library
```

Input shapes: `ads.json` = `[{"id", "brand", "headline", "body", "transcript"}]`; `prompts.json` = `[{"id", "angle", "zone", "headline", "subcopy", "visual", "offer_lockup", "cta", "prompt"}]`; `items.json` = `[{"id", "image_path", "description"}]`.

Thresholds (`gate/rank.py`) are the plan's starting guesses — label ~30 prompts, compare, move them.
