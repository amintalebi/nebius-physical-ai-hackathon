"""Small statistics helpers for real-robot evaluation (few trials, so intervals matter)."""

from __future__ import annotations

import math


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a success rate. Safe for n small and p near 0 or 1."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def p_at_least_k_of_3(p: float, k: int) -> float:
    """Chance of >= k successes in the 3 judged trials if each succeeds independently with prob p."""
    from math import comb

    return sum(comb(3, i) * p**i * (1 - p) ** (3 - i) for i in range(k, 4))


def cohen_kappa(a: list[bool], b: list[bool]) -> float:
    """Agreement between two binary labelers beyond chance (Cosmos Reason vs hand labels)."""
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty label lists")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)
