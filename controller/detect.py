"""Population-level detectors (README constraint 5: thresholds on populations, never single calls).

Pure functions over the in-memory aggregates -> easy to unit test, deterministic, and their thresholds are the
documented false-positive budget (see SUBMISSION.md section 7).
"""
from __future__ import annotations

import math
from collections import defaultdict

from .stats import binom_sf, norm_sf, two_prop

TICK = 15


def tick_window(agg, wf: str, t0_min: int, t1_min: int) -> dict[tuple, list]:
    """Sum counters per (did, prompt) over ticks fully inside [t0_min, t1_min)."""
    out: dict[tuple, list] = {}
    ticks = agg.ticks.get(wf) or {}
    for t in range(t0_min // TICK, t1_min // TICK + 1):
        for k, v in (ticks.get(t) or {}).items():
            a = out.get(k)
            if a is None:
                out[k] = list(v)
            else:
                for i, x in enumerate(v):
                    a[i] += x
    return out


def by_did(win: dict[tuple, list]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (did, _), v in win.items():
        out[did][0] += v[0]
        out[did][1] += v[1]
    return out


def chi2_homogeneity_p(rows: list[tuple[int, int]]) -> float:
    """p-value for H0: equal pickup across caller IDs (Wilson-Hilferty normal approximation of chi-square)."""
    rows = [(d, c) for d, c in rows if d > 0]
    if len(rows) < 2:
        return 1.0
    D, C = sum(d for d, _ in rows), sum(c for _, c in rows)
    p = C / D
    if p <= 0 or p >= 1:
        return 1.0
    x2 = sum((c - d * p) ** 2 / (d * p * (1 - p)) for d, c in rows)
    k = len(rows) - 1
    z = ((x2 / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return norm_sf(z)


# ----------------------------------------------------------------------------------------------- caller ID
def did_degraded(stats: dict[str, list[int]], min_dials: int = 60, z_crit: float = 3.5, ratio_max: float = 0.6) -> list[dict]:
    """A caller ID is 'degraded' when its pickup is far below the pooled pickup of its peers *in the same ticks*
    (caller ID is randomised independently of the lead, so this is an unconfounded comparison).
    Needs BOTH a significant gap (z >= z_crit) and a material one (ratio <= ratio_max)."""
    out = []
    for d, (nd, cd) in stats.items():
        if nd < min_dials:
            continue
        rn = sum(v[0] for k, v in stats.items() if k != d)
        rc = sum(v[1] for k, v in stats.items() if k != d)
        if rn < min_dials or rc == 0:
            continue
        diff, z = two_prop(rc, rn, cd, nd)  # peers minus d
        pd, pr = cd / nd, rc / rn
        if z >= z_crit and pd <= ratio_max * pr:
            out.append({"did": d, "dials": nd, "pickup": round(pd, 4), "peer_pickup": round(pr, 4),
                        "ratio": round(pd / pr, 3), "z": round(z, 2)})
    return out


def did_target(stats: dict[str, list[int]], live: dict[str, float], options: list[str], *, eta: float,
               floor: float = 0.03, probe: float = 0.05, min_dials: int = 60, gate_p: float = 0.01,
               min_spread: float = 1.08, prior: float = 40.0) -> tuple[dict | None, dict]:
    """Move traffic toward caller IDs that actually connect (equalise observed pickup, which is what a load-/
    reputation-limited number looks like from the outside), keep a floor on every ID so a recovering number is
    noticed, and probe IDs with no recent evidence. Returns (target distribution | None, evidence)."""
    D = sum(stats.get(o, [0, 0])[0] for o in options)
    C = sum(stats.get(o, [0, 0])[1] for o in options)
    ev: dict = {"window_dials": D}
    if D < min_dials * 2 or C == 0:
        return None, {**ev, "reason": "insufficient data"}
    pbar = C / D
    health, unobserved = {}, []
    for o in options:
        d, c = stats.get(o, [0, 0])
        if d < min_dials // 2 and live.get(o, 0.0) <= 1e-9:
            unobserved.append(o)
        health[o] = ((c + prior * pbar) / (d + prior)) / pbar
    p_het = chi2_homogeneity_p([tuple(stats.get(o, [0, 0])) for o in options if stats.get(o, [0, 0])[0] >= min_dials])
    spread = max(health[o] for o in options if stats.get(o, [0, 0])[0] >= min_dials // 2 or live.get(o, 0) > 0) / \
        max(1e-9, min(health[o] for o in options if stats.get(o, [0, 0])[0] >= min_dials // 2 or live.get(o, 0) > 0))
    ev.update({"pickup_by_did": {o: (round(stats.get(o, [0, 0])[1] / stats[o][0], 4) if stats.get(o, [0, 0])[0] else None)
                                 for o in options}, "dials_by_did": {o: stats.get(o, [0, 0])[0] for o in options},
               "health": {o: round(h, 3) for o, h in health.items()}, "homogeneity_p": round(p_het, 5),
               "spread": round(spread, 3), "unobserved": unobserved})
    if not unobserved and (p_het > gate_p or spread < min_spread):
        return None, {**ev, "reason": "no significant difference between caller IDs"}
    x = {o: live.get(o, 0.0) * (health[o] ** eta) for o in options}
    s = sum(x.values())
    x = {o: v / s for o, v in x.items()} if s > 0 else dict(live)
    for o in unobserved:  # never-measured IDs get a small probe share so they can be learned about
        x[o] = max(x.get(o, 0.0), probe)
    x = _apply_floor(x, floor)
    return x, ev


def _apply_floor(x: dict, floor: float) -> dict:
    x = dict(x)
    for _ in range(5):
        s = sum(x.values())
        x = {o: v / s for o, v in x.items()}
        low = [o for o in x if x[o] < floor]
        if not low:
            break
        take = sum(floor - x[o] for o in low)
        hi = [o for o in x if x[o] > floor]
        hs = sum(x[o] for o in hi)
        for o in low:
            x[o] = floor
        for o in hi:
            x[o] -= take * x[o] / hs
    return x


# ----------------------------------------------------------------------------------------------- hallucination
def halluc_check(agg, wf: str, current_prompt: str, now: int, ref_rate: float, *, h: float = 7.5, lookback_h: int = 48,
                 min_conn: int = 100, confirm_p: float = 1.0) -> dict | None:
    """Page's CUSUM on the automated hallucination flag, tested against the same detector's reference rate.
    The detector is imperfect (false positives/negatives), so we never look at single calls: the statistic is a
    log-likelihood ratio of 'flag rate = reference' vs 'flag rate >= max(2.5x, +2pt)', accumulated over connected calls
    and reset at zero (so quiet history never builds credit). An alarm also needs a binomial confirmation on the calls
    since the run started. The alarm is only a *trigger*: the incident flow then confirms with a paid validation run, so a false alarm costs
    ~10 credits, never a prompt change - which is why the threshold can favour speed. Monte-Carlo (SUBMISSION s7): P(false
    alarm / 30 days / workflow) ~15%, median delay ~2.4h at 112 connected calls/hour."""
    p0 = min(max(ref_rate, 1e-3), 0.5)
    p1 = max(2.5 * p0, p0 + 0.02)
    a, b = math.log(p1 / p0), math.log((1 - p1) / (1 - p0))
    ticks = agg.ticks.get(wf) or {}
    S = 0.0
    run_n = run_f = 0
    t0 = (now - lookback_h * 60) // TICK
    for t in range(t0, now // TICK + 1):
        n = f = 0
        for (did, prompt), v in (ticks.get(t) or {}).items():
            if prompt == current_prompt:
                n += v[1]
                f += v[3]
        if n == 0:
            continue
        S = max(0.0, S + f * a + (n - f) * b)
        if S == 0.0:
            run_n = run_f = 0
        else:
            run_n += n
            run_f += f
        if S >= h and run_n >= min_conn:
            p = binom_sf(run_f, run_n, p0)
            if p <= confirm_p:
                return {"prompt": current_prompt, "connected": run_n, "flagged": run_f, "rate": round(run_f / run_n, 4),
                        "reference_rate": round(p0, 4), "p_value": p, "ratio": round((run_f / run_n) / p0, 2),
                        "cusum": round(S, 2), "cusum_threshold": h}
    return None


def prompt_rates(win: dict[tuple, list]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for (did, prompt), v in win.items():
        out[prompt][0] += v[1]
        out[prompt][1] += v[3]
    return {k: (v[0], v[1]) for k, v in out.items()}


# ----------------------------------------------------------------------------------------------- KPI drift
def kpi_drift(agg, wf: str, now: int, *, recent_h: int = 24, ref_h: int = 72, z_crit: float = 4.0,
              rel_min: float = 0.10) -> list[dict]:
    """Pickup / engagement of the last `recent_h` vs the `ref_h` before it. Reported separately, never blended."""
    r = tick_window(agg, wf, now - recent_h * 60, now)
    b = tick_window(agg, wf, now - (recent_h + ref_h) * 60, now - recent_h * 60)
    def tot(w):
        d = c = e = 0
        for v in w.values():
            d += v[0]; c += v[1]; e += v[2]
        return d, c, e
    (rd, rc, re_), (bd, bc, be) = tot(r), tot(b)
    out = []
    if min(rd, bd) >= 300:
        diff, z = two_prop(rc, rd, bc, bd)
        if abs(z) >= z_crit and abs(diff) / max(bc / bd, 1e-9) >= rel_min:
            out.append({"kpi": "pickup_rate", "recent": round(rc / rd, 4), "reference": round(bc / bd, 4), "z": round(z, 2)})
    if min(rc, bc) >= 150:
        diff, z = two_prop(re_, rc, be, bc)
        if abs(z) >= z_crit and abs(diff) / max(be / bc, 1e-9) >= rel_min:
            out.append({"kpi": "engagement_rate", "recent": round(re_ / rc, 4), "reference": round(be / bc, 4), "z": round(z, 2)})
    return out


def guardrail_status(agg, wf: str, now: int, objective: dict, *, recent_h: int = 48, ref_days: int = 8) -> dict | None:
    """Does the workflow still respect its guardrail KPI? `guardrail: {<kpi>_max_drop: x}` is read as an absolute drop of the
    guardrail KPI versus its own recent past. Reported separately from the primary KPI - never blended."""
    g = (objective or {}).get("guardrail") or {}
    if not g:
        return None
    key, thr = next(iter(g.items()))
    kpi = key.replace("_max_drop", "")
    r = tick_window(agg, wf, now - recent_h * 60, now)
    b = tick_window(agg, wf, now - ref_days * 1440, now - recent_h * 60)
    def tot(w):
        d = c = e = 0
        for v in w.values():
            d += v[0]; c += v[1]; e += v[2]
        return d, c, e
    (rd, rc, re_), (bd, bc, be) = tot(r), tot(b)
    if kpi == "pickup_rate":
        rn, rk, bn, bk = rd, rc, bd, bc
    elif kpi == "engagement_rate":
        rn, rk, bn, bk = rc, re_, bc, be
    else:
        return None
    if min(rn, bn) < 300:
        return None
    diff, z = two_prop(rk, rn, bk, bn)
    return {"kpi": kpi, "recent": round(rk / rn, 4), "reference": round(bk / bn, 4), "drop": round(-diff, 4),
            "max_drop": thr, "z": round(z, 2), "breached": (-diff) > thr and z < -3.0}
