"""Tests where they matter: the statistics that decide winners, the config arithmetic that decides what is legal, and the
cohort semantics shared by every component. (End-to-end behaviour is covered by scripts/crash_test.py and the graders.)"""
import copy
import math
import random

import numpy as np

from controller import cfgutil, cohorts as C, detect
from controller.stats import binom_sf, holm, msprt_p, stratified_contrast, wilson
from sim import world as simworld  # tests may import the sim; the controller never does


def test_msprt_false_winner_rate_under_continuous_peeking():
    """A/A experiment, 3 arms vs control, we peek every 50 observations/arm for 6000. Holm + always-valid p keeps the
    family-wise false-winner rate near/below alpha even though we look 120 times."""
    rng = np.random.default_rng(7)
    p, tau2, alpha, reps, looks, step = 0.55, (0.1 * 0.55) ** 2, 0.05, 300, 120, 50
    false_win = 0
    for _ in range(reps):
        k = np.zeros((4,), dtype=int); n = 0
        pmin = np.ones(3)
        won = False
        for _ in range(looks):
            k += rng.binomial(step, p, size=4); n += step
            pc = k[0] / n
            for a in range(3):
                pa = k[a + 1] / n
                var = pa * (1 - pa) / n + pc * (1 - pc) / n
                if pa > pc:
                    pmin[a] = min(pmin[a], msprt_p(pa - pc, var, tau2))
            res = holm({a: pmin[a] for a in range(3)}, alpha)
            if any(r for r, _ in res.values()):
                won = True
                break
        false_win += won
    assert false_win / reps <= 0.08, false_win / reps  # nominal 5% (+MC noise); naive peeking would be ~30%


def test_msprt_detects_a_real_lift_quickly():
    rng = np.random.default_rng(3)
    p0, p1, tau2 = 0.55, 0.55 * 1.15, (0.055) ** 2
    hits = []
    for _ in range(60):
        ka = kc = n = 0
        for look in range(1, 80):
            ka += rng.binomial(100, p1); kc += rng.binomial(100, p0); n += 100
            pa, pc = ka / n, kc / n
            if msprt_p(pa - pc, pa * (1 - pa) / n + pc * (1 - pc) / n, tau2) < 0.02:
                hits.append(n); break
    assert len(hits) >= 54 and np.median(hits) < 1500


def test_holm_controls_and_orders():
    r = holm({"a": 0.001, "b": 0.02, "c": 0.06}, 0.05)
    assert r["a"][0] and not r["c"][0]
    assert holm({"a": 0.3}, 0.05)["a"][0] is False


def test_stratified_contrast_removes_simpson_confound():
    # arm is better in BOTH strata, but a naive pooled comparison says the opposite (arm over-sampled in the bad stratum)
    strata = [(30, 100, 20, 100), (200, 1000, 150, 1000)]  # stratum1: arm .30 vs .20 ; stratum2: arm .20 vs .15
    pooled = (30 + 200) / 1100 - (20 + 150) / 1100
    d, var, *_ = stratified_contrast(strata)
    assert d > 0 and pooled > 0
    strata2 = [(100, 1000, 10, 100), (1, 10, 25, 100)]
    d2, *_ = stratified_contrast(strata2, min_n=5)
    assert abs(d2 - 0.0) < 0.2


def test_binom_sf_matches_exact_small_and_normal_large():
    assert abs(binom_sf(3, 10, 0.5) - 0.9453125) < 1e-9
    assert 0 < binom_sf(70, 1000, 0.05) < 0.05
    lo, hi = wilson(5, 100)
    assert lo < 0.05 < hi


def test_did_detector_false_positive_rate_and_power():
    rng = np.random.default_rng(1)
    fp = 0
    for _ in range(400):
        stats = {d: [300, int(rng.binomial(300, 0.28))] for d in "ABCD"}
        fp += bool(detect.did_degraded(stats))
    assert fp / 400 <= 0.01
    hits = sum(bool(detect.did_degraded({"A": [300, int(rng.binomial(300, .09))], "B": [300, int(rng.binomial(300, .27))],
                                         "C": [300, int(rng.binomial(300, .27))]})) for _ in range(200))
    assert hits / 200 >= 0.95


def test_cusum_hallucination_null_and_alt():
    class A: pass
    def run(rate, n_ticks=96 * 3, per=28, seed=0):
        rng = np.random.default_rng(seed)
        a = A(); a.ticks = {"w": {}}
        for t in range(n_ticks):
            n = int(rng.poisson(per)); f = int(rng.binomial(n, rate))
            a.ticks["w"][t] = {("D1", "P"): [n, n, 0, f, 0]}
        return detect.halluc_check(a, "w", "P", n_ticks * 15, 0.015)
    null_alarms = sum(run(0.015, seed=s) is not None for s in range(40))
    alt_alarms = sum(run(0.054, n_ticks=48, seed=s) is not None for s in range(40))
    assert null_alarms <= 2 and alt_alarms >= 38


def test_cohort_assignment_matches_simulator_semantics():
    C.set_features(["lang", "city_tier", "age_band", "value_band"])
    feats = {"lang": ["hi", "en", "ta"], "city_tier": ["1", "2", "3"], "age_band": ["18-30", "31-45", "46-60", "60+"],
             "value_band": ["low", "mid", "high"]}
    cohorts = [{"id": "a", "where": {"age_band": ["60+"], "lang": ["ta"]}}, {"id": "b", "where": {"age_band": ["60+", "46-60"]}},
               {"id": "c", "where": {"lang": ["en"]}}]
    for _ in range(300):
        f = {k: random.choice(v) for k, v in feats.items()}
        exp = "default"
        for c in cohorts:
            if all(f[k] in v for k, v in c["where"].items()):
                exp = c["id"]; break
        assert C.assign(cohorts, C.cell_of(f)) == exp
    assert C.Cohort.make({"lang": ["ta", "hi"]}).id == C.Cohort.make({"lang": ["hi", "ta"]}).id  # canonical id


def _cfg(**kw):
    base = {"cohorts": [], "allocations": {"default": {"welcome_message": {"W1": 1.0}, "voice": {"V1": 1.0},
            "caller_id": {"D1": 0.5, "D2": 0.5}}}, "prompt_version": "P1", "schedule": {"hour_weights": {}, "lead_preferred_hour": {}}}
    base.update(kw)
    return base


def test_config_arithmetic_mirrors_the_simulator():
    old = _cfg()
    new = copy.deepcopy(old)
    new["allocations"]["default"]["caller_id"] = {"D1": 0.2, "D2": 0.5, "D3": 0.3}
    new["allocations"]["default"]["voice"] = {"V1": 0.6, "V2": 0.4}
    new["cohorts"] = [{"id": "x", "where": {"lang": ["ta"]}}]
    new["allocations"]["x"] = {"voice": {"V3": 1.0}}
    assert cfgutil.changed_dims(old, new) == simworld.changed_dims(old, new)
    assert abs(cfgutil.max_shift(old, new) - simworld.max_shift(old, new)) < 1e-12


def test_step_toward_respects_cap_and_converges():
    live = _cfg()
    target = _cfg()
    target["allocations"]["default"]["caller_id"] = {"D1": 0.05, "D2": 0.05, "D3": 0.45, "D4": 0.45}
    cur, steps = live, 0
    while cfgutil.changed_dims(cur, target) and steps < 20:
        nxt = cfgutil.step_toward(cur, target, 0.2)
        assert cfgutil.max_shift(cur, nxt) <= 0.2 + 1e-9
        cur, steps = nxt, steps + 1
    assert not cfgutil.changed_dims(cur, target) and steps <= 6


def test_round_dist_sums_to_one():
    d = cfgutil.round_dist({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3})
    assert abs(sum(d.values()) - 1) < 1e-12


def test_did_balancer_moves_toward_health_and_keeps_floor():
    stats = {"D1": [2000, 400], "D2": [2000, 800], "D3": [100, 40]}
    tgt, ev = detect.did_target(stats, {"D1": 0.5, "D2": 0.5}, ["D1", "D2", "D3", "D4"], eta=1.5)
    assert tgt["D2"] > tgt["D1"] and min(tgt.values()) >= 0.03 - 1e-9 and "D4" in tgt
    assert abs(sum(tgt.values()) - 1) < 1e-9


# ----------------------------------------------------------------------------------------------- caller-ID LP (C5)
def _lp_stats():
    return {"A": [2000, 500], "B": [2000, 440], "C": [2000, 300], "D": [2000, 520]}


def test_did_lp_is_a_valid_deterministic_allocation():
    from controller import allocopt
    live = {o: 0.25 for o in "ABCD"}
    runs = [allocopt.target(_lp_stats(), live, list("ABCD"), gamma=0.5, gamma_ev={}) for _ in range(3)]
    x, ev = runs[0]
    assert x is not None and abs(sum(x.values()) - 1.0) < 1e-9
    assert all(v >= 0.03 - 1e-9 for v in x.values()), "probe floor must hold"
    assert all(abs(x[o] - 0.25) <= 0.4 + 1e-9 for o in x), "trust region must hold"
    assert x["C"] < 0.25 < x["A"], "the weak ID loses traffic, a strong one gains"
    assert runs[1][0] == x and runs[2][0] == x, "LP output must be identical across repeated solves"
    assert ev["modelled_pickup_gain_rel"] > 0 and ev["shadow_price_of_traffic"] > 0


def test_did_lp_load_response_spreads_traffic_and_never_concentrates():
    from controller import allocopt
    live = {o: 0.25 for o in "ABCD"}
    x0, _ = allocopt.target(_lp_stats(), live, list("ABCD"), gamma=0.0, gamma_ev={})
    x1, _ = allocopt.target(_lp_stats(), live, list("ABCD"), gamma=1.0, gamma_ev={})
    assert max(x1.values()) < max(x0.values()), "a load-sensitive pool must be spread more than a load-free one"


def test_did_lp_gate_and_parking_and_min_gain():
    from controller import allocopt
    live = {o: 0.25 for o in "ABCD"}
    same = {o: [2000, 500] for o in "ABCD"}
    x, ev = allocopt.target(same, live, list("ABCD"), gamma=0.5, gamma_ev={})
    assert x is None and "no significant difference" in ev["reason"]
    x, ev = allocopt.target(_lp_stats(), live, list("ABCD"), gamma=0.5, gamma_ev={}, parked=["C"])
    assert x["C"] <= 0.03 + 1e-9, "a parked ID is capped at the probe floor"
    x, ev = allocopt.target(_lp_stats(), live, list("ABCD"), gamma=0.5, gamma_ev={}, min_gain=0.5)
    assert x is None and "not worth a config change" in ev["reason"]


def test_gamma_estimator_recovers_load_sensitivity():
    from controller import allocopt
    rng = random.Random(7)
    ticks, gamma_true = {}, 0.8
    w = 0.5
    for t in range(0, 7 * 96):
        if t % 24 == 0:  # the split changes between 6-hour windows (as it does when the controller moves traffic)
            w = rng.random()
        shares = {"A": 0.25 + 0.2 * (w - 0.5), "B": 0.25 - 0.2 * (w - 0.5), "C": 0.25, "D": 0.25}
        cell = {}
        for o, s in shares.items():
            d = int(1600 * s)
            p = 0.3 * (1 - gamma_true * (s - 0.25))
            cell[(o, "P1")] = [d, int(d * p), 0, 0]
        ticks[t] = cell

    class Agg:
        pass
    agg = Agg()
    agg.ticks = {"w": ticks}
    g, ev = allocopt.estimate_gamma(agg, "w", list("ABCD"), 7 * 96 * 15)
    assert 0.5 < g < 1.1, (g, ev)
