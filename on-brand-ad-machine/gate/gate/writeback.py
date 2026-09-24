"""Write-back loop: every rejection becomes a labelled row in brain/campaign-learnings.csv."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from .brain import DEFAULT_BRAIN


def record_rejection(item_id: str, stage: str, reason: str, brain_root: Path = DEFAULT_BRAIN) -> None:
    path = brain_root / "campaign-learnings.csv"
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f)); fields = list(rows[0].keys())
    rows.append({"date": date.today().isoformat(),
                 "learning": f"[gate/{stage}] odrzucono {item_id}: {reason}",
                 "implication": "Nie generować tego wariantu; poprawić prompt/kąt zgodnie z regułą",
                 "source": "gate", "status": "rejected"})
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_ALL); w.writeheader(); w.writerows(rows)
