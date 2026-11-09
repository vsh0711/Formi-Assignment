"""Caller-ID traffic allocation as a small linear program (C5).

The decision: what share x_o of dials should each caller ID o carry?  The simulator randomises the caller ID per call, so
per-ID pickup in the same hours is an unconfounded measurement, and a *loaded* number loses pickup (carrier reputation /
concurrency).  That makes the share problem a concave resource-allocation problem, not "send everything to the best ID":

    maximise   sum_o  x_o * p_o(x_o)          expected connected calls per dial
    where      p_o(x) = h_o * (1 - gamma * (x - 1/n))      load response (gamma estimated from our own history)
    subject to sum_o x_o = 1
               x_o >= floor_o                  probe floor (a recovering / unmeasured ID must stay observable)
               |x_o - x0_o| <= trust           trust region around the live split (estimates are noisy)
               x_o <= ub_o                     parked IDs are capped at the probe floor

x*p(x) is concave, so a piecewise-linear (K-segment) model is an exact-in-the-limit LP: the solver fills the cheap
segments first and the optimum equalises *marginal* pickup across IDs - not average pickup, which is what the old
"x ~ live * health^eta" heuristic approximated.  h_o is a pessimistic (lower-confidence) health, so the plan is robust to
estimation noise.  The LP is solved with HiGHS (SciPy), single-threaded and deterministic; its dual on the budget
constraint is the *shadow price of a point of traffic* and is stored in the audit row.

Winner selection is untouched: nothing here declares a winner, this only decides how to spread traffic.
"""
from __future__ import annotations

import math

import numpy as np

from .detect import TICK, chi2_homogeneity_p

GAMMA_FLOOR = 0.3  # robustness: never plan as if a loaded number were free (a noisy fit near 0 would concentrate traffic)
MAX_SHARE = 0.6    # no single caller ID carries more than this share (more than 3/4 for a 2-ID pool): load protection
K = 10  # segments per ID (share resolution 0.1 of the budget for the piecewise-linear response)


def estimate_gamma(agg, wf: str, options: list[str], now: int, *, exclude=(), window_h: int = 6, days: int = 7,
                   default: float = 0.5, min_share_sd: float = 0.03) -> tuple[float, dict]:
    """Load sensitivity gamma from the controller's own history: within-ID (fixed-effects) weighted regression of relative
    pickup on share deviation across 6-hour windows.  Returns (gamma in [0, 1.5], evidence).  If shares never varied, the
    effect is not identified and the documented default is used."""
    ticks = agg.ticks.get(wf) or {}
    opts = [o for o in options if o not in set(exclude)]
    n = len(opts)
    if n < 2:
        return default, {"gamma": default, "source": "default (fewer than 2 usable IDs)"}
    per = {o: [] for o in opts}  # (share, rel_pickup, weight) per window
    t_hi = now // TICK
    step = window_h * 60 // TICK
    for w in range(days * 24 // window_h):
        hi, lo = t_hi - w * step, t_hi - (w + 1) * step
        d = {o: 0 for o in opts}
        c = {o: 0 for o in opts}
        for t in range(lo, hi):
            for (did, _), v in (ticks.get(t) or {}).items():
                if did in d:
                    d[did] += v[0]
                    c[did] += v[1]
        D, C = sum(d.values()), sum(c.values())
        if D < 150 * n or C == 0:
            continue
        P = C / D
        for o in opts:
            if d[o] >= 30:
                per[o].append((d[o] / D, (c[o] / d[o]) / P, d[o]))
    sxx = sxy = 0.0
    sds = []
    for o in opts:
        rows = per[o]
        if len(rows) < 4:
            continue
        W = sum(r[2] for r in rows)
        ms = sum(r[0] * r[2] for r in rows) / W
        my = sum(r[1] * r[2] for r in rows) / W
        sds.append(math.sqrt(sum(r[2] * (r[0] - ms) ** 2 for r in rows) / W))
        for s, y, wt in rows:
            sxx += wt * (s - ms) ** 2
            sxy += wt * (s - ms) * (y - my)
    if not sds or max(sds) < min_share_sd or sxx <= 0:
        return default, {"gamma": default, "source": "default (traffic shares have not varied enough to identify load response)"}
    g = -sxy / sxx
    g_hat = g
    g = min(1.5, max(GAMMA_FLOOR, g))
    return g, {"gamma": round(g, 3), "gamma_fitted": round(g_hat, 3), "source": "fixed-effects regression of relative pickup on share over 6h windows, floored at the robust minimum",
               "ids": len(sds), "share_sd": round(max(sds), 3)}


def solve(h: dict, x0: dict, options: list[str], *, gamma: float, floor: float, ub: dict, trust: float) -> tuple[dict | None, dict]:
    """Solve the allocation LP.  h = pessimistic relative health at the reference share 1/n; returns (x, solver evidence)."""
    from scipy.optimize import linprog
    n = len(options)
    sref = 1.0 / n
    w = 1.0 / K
    c = np.zeros(n * K)
    lo = np.zeros(n)
    hi = np.ones(n)
    for i, o in enumerate(options):
        u = ub.get(o, 1.0)
        lo[i] = min(max(floor, x0.get(o, 0.0) - trust), u)
        hi[i] = max(lo[i], min(u, x0.get(o, 0.0) + trust))
        for k in range(K):
            s_mid = (k + 0.5) * w
            marg = h[o] * (1.0 - gamma * (2.0 * s_mid - sref))
            marg += 1e-7 * (1.0 if s_mid <= x0.get(o, 0.0) else 0.0)  # deterministic tie-break toward the live split
            c[i * K + k] = -marg  # linprog minimises
    A_eq = np.zeros((1, n * K))
    A_eq[0, :] = 1.0
    b_eq = [1.0]
    A_ub, b_ub = [], []
    for i in range(n):
        row = np.zeros(n * K)
        row[i * K:(i + 1) * K] = 1.0
        A_ub.append(row)
        b_ub.append(hi[i])
        A_ub.append(-row)
        b_ub.append(-lo[i])
    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub), A_eq=A_eq, b_eq=b_eq,
                  bounds=[(0.0, w)] * (n * K), method="highs-ds")
    if res.status != 0:
        return None, {"solver_status": int(res.status), "message": str(res.message)[:120]}
    y = res.x.reshape(n, K)
    x = {o: float(y[i].sum()) for i, o in enumerate(options)}
    binding = []
    for i, o in enumerate(options):
        if abs(x[o] - lo[i]) < 1e-6:
            binding.append(f"{o}:floor/lower")
        elif abs(x[o] - hi[i]) < 1e-6:
            binding.append(f"{o}:upper/trust")
    live_obj = sum(x0.get(o, 0.0) * h[o] * (1.0 - gamma * (x0.get(o, 0.0) - sref)) for o in options)
    new_obj = sum(x[o] * h[o] * (1.0 - gamma * (x[o] - sref)) for o in options)
    return x, {"solver": "HiGHS dual simplex (scipy.optimize.linprog)", "solver_status": 0,
               "objective_new": round(new_obj, 5), "objective_live": round(live_obj, 5),
               "modelled_pickup_gain_rel": round(new_obj / live_obj - 1.0, 4) if live_obj > 0 else None,
               "shadow_price_of_traffic": round(float(-res.eqlin.marginals[0]), 5), "binding": sorted(binding)}


def target(stats: dict[str, list[int]], live: dict[str, float], options: list[str], *, gamma: float, gamma_ev: dict,
           floor: float = 0.03, probe: float = 0.05, min_dials: int = 60, gate_p: float = 0.01, min_spread: float = 1.08,
           prior: float = 40.0, z: float = 1.0, trust: float = 0.4, parked=(), min_gain: float = 0.0) -> tuple[dict | None, dict]:
    """Drop-in replacement of detect.did_target: same gate (heterogeneity must be real), LP target instead of the
    multiplicative heuristic.  Returns (target distribution | None, evidence)."""
    D = sum(stats.get(o, [0, 0])[0] for o in options)
    C = sum(stats.get(o, [0, 0])[1] for o in options)
    ev: dict = {"window_dials": D, "model": "lp", "gamma": gamma_ev}
    if D < min_dials * 2 or C == 0:
        return None, {**ev, "reason": "insufficient data"}
    pbar = C / D
    n = len(options)
    sref = 1.0 / n
    h, unobserved = {}, []
    for o in options:
        d, cc = stats.get(o, [0, 0])
        if d < min_dials // 2 and live.get(o, 0.0) <= 1e-9:
            unobserved.append(o)
        p_hat = (cc + prior * pbar) / (d + prior)
        se = math.sqrt(max(p_hat * (1 - p_hat), 1e-9) / (d + prior))
        p_lcb = max(1e-6, p_hat - z * se)
        # undo the load response at the live share so h is the pickup at the neutral reference share
        h[o] = (p_lcb / pbar) / max(0.2, 1.0 - gamma * (live.get(o, 0.0) - sref))
    seen = [o for o in options if stats.get(o, [0, 0])[0] >= min_dials // 2 or live.get(o, 0) > 0]
    healths = {o: ((stats.get(o, [0, 0])[1] + prior * pbar) / (stats.get(o, [0, 0])[0] + prior)) / pbar for o in options}
    p_het = chi2_homogeneity_p([tuple(stats.get(o, [0, 0])) for o in options if stats.get(o, [0, 0])[0] >= min_dials])
    spread = max(healths[o] for o in seen) / max(1e-9, min(healths[o] for o in seen))
    ev.update({"pickup_by_did": {o: (round(stats[o][1] / stats[o][0], 4) if stats.get(o, [0, 0])[0] else None) for o in options},
               "dials_by_did": {o: stats.get(o, [0, 0])[0] for o in options},
               "health_lcb": {o: round(h[o], 3) for o in options}, "homogeneity_p": round(p_het, 5),
               "spread": round(spread, 3), "unobserved": unobserved})
    if not unobserved and (p_het > gate_p or spread < min_spread):
        return None, {**ev, "reason": "no significant difference between caller IDs"}
    cap = max(MAX_SHARE, min(0.75, 1.0 / n + 0.25))
    ub = {o: (floor if o in parked else cap) for o in options}
    x, sev = solve(h, live, options, gamma=gamma, floor=floor, ub=ub, trust=trust)
    if x is None:
        return None, {**ev, **sev, "reason": "solver did not return an optimum"}
    ev.update(sev)
    if not unobserved and (sev.get("modelled_pickup_gain_rel") or 0.0) < min_gain:
        return None, {**ev, "reason": f"modelled pickup gain below {min_gain:.0%}: not worth a config change"}
    if unobserved:  # unmeasured IDs need a learning share even when the model prefers other IDs
        for o in unobserved:
            x[o] = max(x[o], probe)
        s = sum(x.values())
        x = {o: v / s for o, v in x.items()}
    return x, ev
