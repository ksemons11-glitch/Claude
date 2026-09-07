from __future__ import annotations

import hashlib
import json
from typing import Any

TRACKED_FIELDS = (
    "name",
    "configured_status",
    "effective_status",
    "daily_budget",
    "lifetime_budget",
    "budget_type",
    "targeting",
    "post_id",
    "url_tags",
    "destination_url",
)


def attributes_hash(attrs: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(attrs, sort_keys=True, default=str).encode()).hexdigest()


def diff_attributes(before: dict[str, Any] | None, after: dict[str, Any]) -> list[tuple[str, Any, Any]]:
    if before is None:
        return []
    out: list[tuple[str, Any, Any]] = []
    for f in TRACKED_FIELDS:
        if f in before or f in after:
            b, a = before.get(f), after.get(f)
            if b != a:
                out.append((f, b, a))
    return out
