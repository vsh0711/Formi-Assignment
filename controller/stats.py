"""Deterministic statistics. No randomness anywhere in here: same counts in -> same decision out.

Winner selection uses *always-valid* p-values (mixture sequential probability ratio test, Johari et al. 2017) so
we may look at the data every few hours without inflating the false-winner rate, then Holm across the family of
arms. Point estimates never decide anything on their own.
"""
from __future__ import annotations

import math


def msprt_p(delta: float, var: float, tau2: float) -> float:
    """Always-valid two-sided p-value for H0: true difference = 0, given estimate `delta` with variance `var`.
    Gaussian mixing prior N(0, tau2). Lambda = sqrt(V/(V+t2)) * exp(t2*d^2 / (2V(V+t2))); p = min(1, 1/Lambda)."""
    if var <= 0:
        return 1.0
    log_l = 0.5 * math.log(var / (var + tau2)) + (tau2 * delta * delta) / (2.0 * var * (var + tau2))
    return 1.0 if log_l <= 0 else math.exp(-log_l)


def holm(pvals: dict, alpha: float) -> dict:
    """Holm-Bonferroni step-down. Returns {key: (rejected, adjusted_p)}."""
    items = sorted(pvals.items(), key=lambda kv: (kv[1], str(kv[0])))
    m, out, stop = len(items), {}, False
    run = 0.0
    for i, (k, p) in enumerate(items):
        adj = min(1.0, (m - i) * p)
        run = max(run, adj)
        rej = (not stop) and run <= alpha
        if not rej:
            stop = True
        out[k] = (rej, run)
    return out


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2))


def two_prop(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float]:
    """(diff p1-p2, z) using unpooled SE with add-half smoothing so tiny cells cannot produce zero variance."""
    if n1 <= 0 or n2 <= 0:
        return 0.0, 0.0
    p1, p2 = k1 / n1, k2 / n2
    q1, q2 = (k1 + 0.5) / (n1 + 1), (k2 + 0.5) / (n2 + 1)
    se = math.sqrt(q1 * (1 - q1) / n1 + q2 * (1 - q2) / n2)
    return p1 - p2, (p1 - p2) / se if se > 0 else 0.0


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k), X~Bin(n,p). Exact for small n, normal approx with continuity correction for large n."""
    if k <= 0:
        return 1.0
    if n <= 0:
        return 1.0
    p = min(max(p, 1e-9), 1 - 1e-9)
    if n <= 400:
        # sum of the upper tail via log-pmf recurrence
        lp = n * math.log1p(-p)
        pm, tot = math.exp(lp), 0.0
        for i in range(0, n + 1):
            if i >= k:
                tot += pm
            if i < n:
                pm *= (n - i) / (i + 1) * p / (1 - p)
        return min(1.0, tot)
    mu, sd = n * p, math.sqrt(n * p * (1 - p))
    return norm_sf((k - 0.5 - mu) / sd)


def stratified_contrast(strata: list[tuple[int, int, int, int]], min_n: int = 20):
    """Inverse-variance pooled difference of proportions across strata.
    strata: [(k_a, n_a, k_c, n_c)]. Returns (delta, var, n_a, n_c, used_strata) or None.
    Stratifying by (config version, cohort) keeps the comparison valid even though allocations change over time."""
    num = den = 0.0
    na = nc = used = 0
    for ka, n_a, kc, n_c in strata:
        if n_a < min_n or n_c < min_n:
            continue
        qa, qc = (ka + 0.5) / (n_a + 1), (kc + 0.5) / (n_c + 1)
        v = qa * (1 - qa) / n_a + qc * (1 - qc) / n_c
        w = 1.0 / v
        num += w * (ka / n_a - kc / n_c)
        den += w
        na += n_a
        nc += n_c
        used += 1
    if den <= 0:
        return None
    return num / den, 1.0 / den, na, nc, used
