"""Load the file-based brand brain (CSV) and render the context strings the judge reads."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BRAIN = Path(__file__).resolve().parents[2] / "brain"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass
class Brain:
    root: Path = DEFAULT_BRAIN
    tables: dict[str, list[dict[str, str]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for p in sorted(self.root.glob("*.csv")):
            self.tables[p.stem] = _rows(p)

    def kv(self, table: str, key_col: str, val_col: str) -> dict[str, str]:
        return {r[key_col]: r[val_col] for r in self.tables.get(table, [])}

    # --- rendered contexts (what the judge sees) -------------------------------------------
    def brand_context(self) -> str:
        core = self.kv("brand-core", "key", "value")
        keys = ["brand_name", "category", "product_one_liner", "market", "big_idea", "positioning",
                "core_promise", "mechanism_fact", "mechanism_hypothesis", "awareness_level",
                "market_saturation", "tone_of_voice", "spokesperson", "hard_rule_1", "hard_rule_2",
                "hard_rule_3", "hard_rule_4"]
        lines = [f"{k}: {core[k]}" for k in keys if k in core]
        aud = [r for r in self.tables.get("audiences", []) if r.get("role") in ("główny", "poboczny")]
        lines.append("audiences:")
        for r in aud:
            lines.append(f"  - [{r['role']}] {r['name']} ({r['age']}): pain={r['pain_points']}; "
                         f"objections={r['objections']}; proof_wanted={r['proof_wanted']}")
        lines.append("belief_chain:")
        for r in self.tables.get("belief-chain", []):
            lines.append(f"  {r['step']}. {r['belief']}")
        return "\n".join(lines)

    def brand_products(self) -> str:
        prod = self.kv("products", "field", "value")
        keys = ["product_name", "set_contents", "material", "reuses_per_patch", "usage", "set_duration",
                "key_zones_for_comms", "price_1_set", "price_2_sets", "price_3_sets", "cost_per_use",
                "delivery", "payments", "returns", "photo_packshot", "photo_on_face"]
        return "\n".join(f"{k}: {prod[k]}" for k in keys if k in prod)

    def brand_rules(self) -> str:
        lines = ["copy_rules:"]
        for r in self.tables.get("copy-rules", []):
            lines.append(f"  {r['rule_id']} [{r['type']}]: {r['check']}")
        lines.append("claims (allowed / banned):")
        for r in self.tables.get("claims", []):
            lines.append(f"  {r['claim_id']} allowed={r['allowed']}: {r['claim']}")
        lines.append("visual_universe:")
        for r in self.tables.get("visual-universe", []):
            lines.append(f"  {r['element']}: {r['rule']}")
        kit = self.kv("brand-kit", "asset", "value")
        for k in ("palette_named", "palette_banned_named", "font_headline", "logo_primary", "packaging"):
            if k in kit:
                lines.append(f"brand_kit.{k}: {kit[k]}")
        return "\n".join(lines)

    def allowed_claims(self) -> list[dict[str, str]]:
        return [r for r in self.tables.get("claims", []) if r["allowed"].lower().startswith("yes")]
