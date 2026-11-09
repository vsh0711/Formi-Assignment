"""Call-time optimisation per cohort (C4): *who* gets dialled in which hour. Capacity and windows are the business's.

Why this is more than 'call people when they pick up':
  * The dialler fills each hour's capacity from eligible leads with probability proportional to the cohort's hour weight.
    A single global table therefore changes nothing (every lead scales equally): the lever only exists *between* cohorts.
  * So the partition feature is chosen by **held-out gain**: train weights on odd days, score on even days (and vice
    versa). A feature is adopted only if the lower confidence bound of the held-out gain clears a threshold. This is the
    cohort-size control: a split that does not generalise (too little data per level) does not survive cross-validation.
  * Hour pickup rates are standardised over attempt number (later attempts hit people who already didn't answer), shrunk
    toward the level mean, and weights are floored (>0, since an omitted hour means weight 0 = unused capacity).
  * The gain model re-normalises each hour's fixed capacity across cohorts (D' = capacity * D*w'/sum(D*w')), so it can
    never promise dials that do not exist. It is first-order (eligible pool assumed fixed) and we haircut it by 50%.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict

from . import cfgutil, cohorts as C
from .audit import Audit
from .experiments import Experiments
from .plan import PlanStore
from .store import Store

log = logging.getLogger("controller.schedule")

GAMMA, WMIN, WMAX, ALPHA = 1.0, 0.25, 4.0, 30.0
MIN_GAIN_LCB = 0.01       # adopt only if held-out LCB of the relative gain >= 1%
REALISATION = 0.5          # haircut on the first-order gain used for the impact score
MIN_LEVEL_DIALS, MIN_LEVEL_SHARE = 300, 0.04


class Scheduler:
    def __init__(self, st: Store, audit: Audit, plans: PlanStore, agg):
        self.st, self.audit, self.plans, self.agg = st, audit, plans, agg

    # ------------------------------------------------------------------ entry
    def step(self, wf: str, spec: dict, now: int, live: dict, held: bool):
        if held:
            return
        last = self.st.get(f"sched_eval:{wf}")
        if last is not None and not (now % 1440 == 300 and last != now):
            return
        self.st.put(f"sched_eval:{wf}", now)
        res = self.compute(wf, spec, live, now)
        if res is None:
            return
        if res["adopt"]:
            self._plan(wf, spec, live, now, res)
        else:
            plan = self.plans.get(wf)
            if plan["why"].get("schedule", {}).get("kind") == "schedule" and res.get("reason") != "insufficient data":
                pass  # a previously planned table stays until it is applied or superseded
            self.audit.decision(now, wf, "schedule_hold", "no cohort split generalises", "held-out gain LCB < threshold",
                                res["summary"], "no change", res["reason"])

    # ------------------------------------------------------------------ statistics
    @staticmethod
    def _levels_of(cell: str, feature: str | None) -> str:
        return "all" if feature is None else C.cell_tuple(cell)[C.FEATURES.index(feature)]

    def _tables(self, wf: str, feature: str | None, parity: int | None, lo: int, hi: int):
        """{level: {hour: {att: [dials, k_conn, k_eng]}}} for the window hours."""
        out: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
        for (par, cell, hour, att), v in self.agg.wf("agg_hour", wf).items():
            if (parity is not None and par != parity) or not lo <= hour < hi:
                continue
            a = out[self._levels_of(cell, feature)][hour][att]
            a[0] += v[0]; a[1] += v[1]; a[2] += v[2]
        return out

    @staticmethod
    def _rates(tab: dict, hours: range, mi: int, att_share: dict) -> tuple[dict, dict]:
        """Attempt-standardised, shrunk per-dial rate r[l][h] and dial counts d[l][h]."""
        r: dict = {}
        d: dict = {}
        for lvl, byh in tab.items():
            att_tot: dict = defaultdict(lambda: [0, 0])
            for h, byatt in byh.items():
                for a, v in byatt.items():
                    att_tot[a][0] += v[0]; att_tot[a][1] += v[mi]
            r[lvl], d[lvl] = {}, {}
            for h in hours:
                tot, acc = 0, 0.0
                for a, s in att_share.items():
                    v = byh.get(h, {}).get(a, [0, 0, 0])
                    mean_a = att_tot[a][1] / att_tot[a][0] if att_tot[a][0] else 0.0
                    acc += s * ((v[mi] + ALPHA * mean_a) / (v[0] + ALPHA))
                    tot += v[0]
                r[lvl][h], d[lvl][h] = acc, tot
        return r, d

    @staticmethod
    def _weights(r: dict, d: dict, hours: range) -> dict:
        w: dict = {}
        for lvl in r:
            tot = sum(d[lvl][h] for h in hours)
            mean = sum(d[lvl][h] * r[lvl][h] for h in hours) / tot if tot else 0.0
            w[lvl] = {h: (min(WMAX, max(WMIN, (r[lvl][h] / mean) ** GAMMA)) if mean > 0 else 1.0) for h in hours}
        return w

    @staticmethod
    def _gain(w_new: dict, w_cur: dict, d_test: dict, r_test: dict, hours: range) -> tuple[float, float]:
        """Relative gain of re-weighting, with per-hour capacity renormalised across levels."""
        M = 0.0
        M2 = 0.0
        var = 0.0
        for h in hours:
            Dh = sum(d_test[l][h] for l in d_test)
            if Dh <= 0:
                continue
            raw = {l: d_test[l][h] * w_new[l][h] / w_cur[l][h] for l in d_test}
            z = sum(raw.values())
            if z <= 0:
                continue
            for l in d_test:
                Dn = Dh * raw[l] / z
                rr = r_test[l][h]
                M += d_test[l][h] * rr
                M2 += Dn * rr
                n = max(d_test[l][h], 1)
                var += (Dn - d_test[l][h]) ** 2 * rr * (1 - rr) / n
        if M <= 0:
            return 0.0, 1.0
        return (M2 - M) / M, math.sqrt(var) / M

    def compute(self, wf: str, spec: dict, live: dict, now: int) -> dict | None:
        lo, hi = spec["dialling_window"]
        hours = range(lo, hi)
        primary = spec["objective"]["primary"]
        mi = 1 if primary == "pickup_rate" else 2          # per-dial outcome: connected | engaged (= pickup x engagement)
        total_dials = sum(v[0] for v in self.agg.wf("agg_hour", wf).values())
        if total_dials < 3000:
            return {"adopt": False, "reason": "insufficient data", "summary": {"dials": total_dials}}
        allowed = Experiments.partition_features(live)
        cand: list[str] = [f for f in C.FEATURES if allowed is None or f in allowed]
        # attempt mix used for standardisation
        att: dict = defaultdict(int)
        for (par, cell, hour, a), v in self.agg.wf("agg_hour", wf).items():
            att[a] += v[0]
        s = sum(att.values())
        att_share = {a: n / s for a, n in att.items()}
        live_w = (live.get("schedule") or {}).get("hour_weights") or {}
        results = {}
        for f in cand:
            gains = []
            for tr, te in ((0, 1), (1, 0)):
                t_tr, t_te = self._tables(wf, f, tr, lo, hi), self._tables(wf, f, te, lo, hi)
                r_tr, d_tr = self._rates(t_tr, hours, mi, att_share)
                r_te, d_te = self._rates(t_te, hours, mi, att_share)
                lv = [l for l in r_tr if l in r_te]
                w_new = {l: self._weights({l: r_tr[l]}, {l: d_tr[l]}, hours)[l] for l in lv}
                w_cur = self._current_weights(live, f, lv, hours)
                gains.append(self._gain(w_new, w_cur, {l: d_te[l] for l in lv}, {l: r_te[l] for l in lv}, hours))
            g = (gains[0][0] + gains[1][0]) / 2
            se = math.sqrt(gains[0][1] ** 2 + gains[1][1] ** 2) / 2
            results[f] = {"gain": round(g, 4), "se": round(se, 4), "lcb": round(g - 1.645 * se, 4)}
        best = max(results, key=lambda f: (results[f]["lcb"], f)) if results else None
        summary = {"metric": "connected per dial" if mi == 1 else "engaged per dial", "cv_gain_by_feature": results,
                   "total_dials": total_dials, "threshold_lcb": MIN_GAIN_LCB}
        if best is not None and results[best]["lcb"] >= MIN_GAIN_LCB:
            tabn = self._tables(wf, best, None, lo, hi)
            tot_n = sum(v[0] for byh in tabn.values() for byatt in byh.values() for v in byatt.values())
            n_ok = sum(1 for byh in tabn.values()
                       if sum(v[0] for byatt in byh.values() for v in byatt.values()) >= MIN_LEVEL_DIALS and
                       sum(v[0] for byatt in byh.values() for v in byatt.values()) / max(tot_n, 1) >= MIN_LEVEL_SHARE)
            if n_ok < 2:  # a single-table schedule is a no-op (weights only matter relatively)
                results[best]["lcb"] = -1.0
        if best is None or results[best]["lcb"] < MIN_GAIN_LCB:
            return {"adopt": False, "reason": f"best held-out gain LCB {results.get(best, {}).get('lcb')} < {MIN_GAIN_LCB}",
                    "summary": summary}
        # ---- final weights on all data
        tab = self._tables(wf, best, None, lo, hi)
        r, d = self._rates(tab, hours, mi, att_share)
        w = self._weights(r, d, hours)
        tot = sum(sum(d[l].values()) for l in d)
        keep = [l for l in d if sum(d[l].values()) >= MIN_LEVEL_DIALS and sum(d[l].values()) / tot >= MIN_LEVEL_SHARE]
        rest = [l for l in d if l not in keep]
        cohorts_cfg = []
        tables = {}
        for l in sorted(keep):
            coh = C.Cohort.make({best: [l]})
            cohorts_cfg.append(coh.to_config())
            tables[coh.id] = {str(h): round(w[l][h], 3) for h in hours}
        if rest:  # leftover levels share one 'default' table (or uniform when it is too thin)
            dr = {h: sum(d[l][h] * r[l][h] for l in rest) / max(1, sum(d[l][h] for l in rest)) for h in hours}
            mean = sum(dr.values()) / len(dr)
            tables["default"] = {str(h): round(min(WMAX, max(WMIN, dr[h] / mean)), 3) if mean > 0 else 1.0 for h in hours}
        else:
            tables["default"] = {str(h): 1.0 for h in hours}
        g = results[best]
        return {"adopt": True, "feature": best, "cohorts": cohorts_cfg, "tables": tables, "gain": g,
                "summary": {**summary, "chosen_feature": best, "levels": sorted(keep), "merged_into_default": sorted(rest)},
                "reason": "ok", "primary": primary}

    @staticmethod
    def _current_weights(live: dict, feature: str, levels: list[str], hours: range) -> dict:
        hw = (live.get("schedule") or {}).get("hour_weights") or {}
        cur = {}
        for l in levels:
            cid = C.Cohort.make({feature: [l]}).id if feature else "default"
            t = hw.get(cid) if cid in hw else hw.get("default")
            cur[l] = {h: float((t or {}).get(str(h), 1.0 if not t else 0.0)) or 1e-3 for h in hours}
        return cur

    # ------------------------------------------------------------------ plan
    def _plan(self, wf, spec, live, now, res):
        cur_tables = (live.get("schedule") or {}).get("hour_weights") or {}
        if res["tables"] == cur_tables and not self.plans.get(wf)["schedule"]:
            return
        existing = [c for c in live.get("cohorts", [])]
        have = {c["id"] for c in existing}
        new_c = [c for c in res["cohorts"] if c["id"] not in have]
        cohorts_target = existing + new_c
        g = res["gain"]
        did = self.audit.decision(
            now, wf, "schedule_planned", f"hour weights per {res['feature']} cohort raise {res['summary']['metric']}",
            f"held-out CV gain LCB {g['lcb']:.3f} >= {MIN_GAIN_LCB}", res["summary"], "plan updated",
            f"partition by {res['feature']} ({len(res['cohorts'])} cohorts); expected +{g['gain']:.1%} (LCB {g['lcb']:.1%}) {res['summary']['metric']}")
        why = {"kind": "schedule", "ref": "schedule", "urgent": False, "reach": 1.0, "decision": did,
               "summary": f"call-time weights per {res['feature']} cohort ({len(res['cohorts'])} cohorts, all window hours > 0)",
               "rationale": f"cross-validated: weights learned on alternating days, scored on the others; expected "
                            f"{g['gain']:+.1%} (LCB {g['lcb']:+.1%}) in {res['summary']['metric']}",
               "evidence_text": "2-fold day-parity CV", "lift_rel_lcb": max(0.0, g["lcb"]) * REALISATION,
               "projection": {"metric": res["summary"]["metric"], "cv_gain": g, "realisation_haircut": REALISATION,
                              "levels": res["summary"]["levels"], "method": "capacity-renormalised reweighting"}}
        if new_c or live.get("cohorts") != cohorts_target:
            self.plans.set_cohorts(wf, cohorts_target, {**why, "summary": "define cohorts used by the call-time schedule"})
        self.plans.set_schedule(wf, res["tables"], why)
