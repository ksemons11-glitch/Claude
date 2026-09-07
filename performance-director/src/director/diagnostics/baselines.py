"""Robust baselines: median/MAD z-scores, Wilson intervals, insufficient-baseline fallbacks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

MAD_SCALE = 0.6745


@dataclass
class RobustZ:
    z: float | None
    median: float | None
    mad: float | None
    n: int
    status: str  # OK | INSUFFICIENT_BASELINE | ZERO_MAD_FALLBACK

    @property
    def usable(self) -> bool:
        return self.z is not None and self.status in ("OK", "ZERO_MAD_FALLBACK")


def robust_z(x: float | Decimal | None, history: list[float | Decimal | None], *, min_n: int = 7) -> RobustZ:
    vals = [float(v) for v in history if v is not None]
    if x is None or len(vals) < min_n:
        return RobustZ(None, median(vals) if vals else None, None, len(vals), "INSUFFICIENT_BASELINE")
    med = median(vals)
    mad = median([abs(v - med) for v in vals])
    xf = float(x)
    if mad == 0:
        # fallback: mean absolute deviation, then relative 10% of the median
        mean_abs = sum(abs(v - med) for v in vals) / len(vals)
        scale = mean_abs if mean_abs > 0 else abs(med) * 0.1
        if scale == 0:
            return RobustZ(
                0.0 if xf == med else math.copysign(99.0, xf - med), med, 0.0, len(vals), "ZERO_MAD_FALLBACK"
            )
        return RobustZ((xf - med) / scale, med, 0.0, len(vals), "ZERO_MAD_FALLBACK")
    return RobustZ(MAD_SCALE * (xf - med) / mad, med, mad, len(vals), "OK")


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    """Wilson score interval for a proportion; None if no trials."""
    if trials <= 0:
        return None
    p = successes / trials
    denom = 1 + z * z / trials
    centre = (p + z * z / (2 * trials)) / denom
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def intervals_overlap(a: tuple[float, float] | None, b: tuple[float, float] | None) -> bool | None:
    if a is None or b is None:
        return None
    return not (a[1] < b[0] or b[1] < a[0])


def consecutive_signal(flags: list[bool], required: int) -> bool:
    """True when the last `required` readings are all flagged."""
    if required <= 0:
        return bool(flags and flags[-1])
    return len(flags) >= required and all(flags[-required:])


def to_float(v: Decimal | float | int | None) -> float | None:
    return None if v is None else float(v)
