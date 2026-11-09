"""Variant experimentation on welcome message and voice (C6) with promotion, decay detection and rollback (C7).

Design in one paragraph
-----------------------
Welcome and voice are randomised *independently per call* by the dialler, so one crossed (factorial) experiment
estimates both main effects from the same calls. Allocation is control-heavy (~40%) with the candidates sharing the
rest. Each candidate is compared to the incumbent *within strata of (config version, cohort)*, because allocations
change over time and a pooled comparison across versions is confounded (Simpson). Strata are combined by inverse
variance. Sequential decisions use mixture-SPRT always-valid p-values, so peeking every few hours does not inflate the
false-winner rate; Holm across arms controls the family. Segment (cohort) findings are tested ONCE, at conclusion,
as a fixed-sample look with Holm over the pre-registered family of single-feature segments; harm to a segment vetoes
a promotion on a looser (safety-first) threshold. A promoted winner keeps a control holdout so decay is measurable.
Only what actually ran is evidence: every count comes from call events carrying the variant that was dialled.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

from . import cfgutil, cohorts as C
from .audit import Audit
from .plan import PlanStore
from .stats import holm, msprt_p, norm_sf, stratified_contrast
from .store import Store

EXP_DIMS = ("welcome_message", "voice")

P = {  # pre-registered parameters (also written into each experiment's `prereg` row)
    "control_share": 0.50, "holdout": 0.25, "stage1_holdout": 0.50, "stage2_after_min": 1440, "mon_buckets": 3, "alpha_win": 0.05, "alpha_seg": 0.05, "alpha_harm_drop": 0.01,
    "veto_z": 1.28, "veto_abs": 0.02, "tau_rel": 0.10, "n_min": 250, "n_seg_min": 200, "min_lift_rel": 0.02, "min_seg_lift_rel": 0.05,
    "max_days": 5.0, "min_days_left": 2.5, "min_conn_per_day": 120, "eval_every_min": 180,
    "mon_min_arm": 300, "mon_min_ctrl": 100, "decay_frac": 0.5, "mon_consecutive": 2, "drop_abs": 0.03,
    "max_override_cohorts": 4,
}


def _sums(cells: dict, metric: str, pred=None) -> tuple[int, int]:
    k = n = 0
    for cell, v in cells.items():
        if pred is not None and not pred(cell):
            continue
        if metric == "eng":
            k += v[2]; n += v[1]
        else:
            k += v[1]; n += v[0]
    return k, n


def build_strata(agg, wf: str, dim: str, min_day: int) -> dict:
    """{(ver, cohort): {option: {cell: [dials, conn, eng]}}} from the stratified sufficient statistics."""
    out: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, 0, 0])))
    for (day, ver, cohort, cell, d, opt), v in agg.wf("agg_cell", wf).items():
        if d != dim or day < min_day:
            continue
        a = out[(ver, cohort)][opt][cell]
        a[0] += v[0]; a[1] += v[1]; a[2] += v[2]
    return out


def contrast(strata: dict, arm: str, ctrl: str, metric: str, pred=None, min_n: int = 20):
    lst = []
    for by_opt in strata.values():
        A, Cc = by_opt.get(arm), by_opt.get(ctrl)
        if not A or not Cc:
            continue
        ka, na = _sums(A, metric, pred)
        kc, nc = _sums(Cc, metric, pred)
        lst.append((ka, na, kc, nc))
    return stratified_contrast(lst, min_n)


def arm_rates(strata: dict, opt: str, metric: str = "eng") -> tuple[int, int]:
    k = n = 0
    for by_opt in strata.values():
        if opt in by_opt:
            a, b = _sums(by_opt[opt], metric)
            k += a; n += b
    return k, n


class Experiments:
    def __init__(self, st: Store, agg, audit: Audit, plans: PlanStore):
        self.st, self.agg, self.audit, self.plans = st, agg, audit, plans

    # ------------------------------------------------------------------ persistence
    def active(self, wf: str, dim: str):
        r = self.st.one("SELECT id,status,control,arms,prereg,started_min,promo_min,state FROM experiments "
                        "WHERE wf=? AND dim=? AND status!='closed' ORDER BY rowid DESC LIMIT 1", (wf, dim))
        return self._row(r) if r else None

    def _row(self, r):
        st = json.loads(r[7])
        return {"id": r[0], "status": r[1], "control": r[2], "arms": json.loads(r[3]), "prereg": json.loads(r[4]),
                "started_min": r[5], "promo_min": r[6], "state": st, "updated": st.get("closed_min")}

    def all_for(self, wf: str) -> list[dict]:
        return [self._row(r) for r in self.st.q(
            "SELECT id,status,control,arms,prereg,started_min,promo_min,state FROM experiments WHERE wf=?", (wf,))]

    def _save(self, e: dict, wf: str, dim: str, now: int):
        self.st.x("INSERT INTO experiments(id,wf,dim,status,control,arms,prereg,started_min,promo_min,state,updated_min)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,"
                  "arms=excluded.arms,promo_min=excluded.promo_min,state=excluded.state,updated_min=excluded.updated_min",
                  (e["id"], wf, dim, e["status"], e["control"], json.dumps(e["arms"]), json.dumps(e["prereg"]),
                   e["started_min"], e["promo_min"], json.dumps(e["state"], sort_keys=True), now))

    def _history(self, wf: str, dim: str) -> list[dict]:
        return [e for e in self.all_for(wf) if e["id"].startswith(f"{wf}:{dim}:")]

    def _pmin(self, exp_id: str, arm: str, seg: str, kind: str, p: float) -> float:
        """Running minimum of the always-valid p-value (a valid p-value at every look)."""
        r = self.st.one("SELECT p_min,looks FROM exp_pvals WHERE exp_id=? AND arm=? AND seg=? AND kind=?",
                        (exp_id, arm, seg, kind))
        pm = min(p, r[0]) if r else p
        self.st.x("INSERT INTO exp_pvals VALUES(?,?,?,?,?,1) ON CONFLICT(exp_id,arm,seg,kind) DO UPDATE SET "
                  "p_min=?, looks=looks+1", (exp_id, arm, seg, kind, pm, pm))
        return pm

    # ------------------------------------------------------------------ main entry
    def step(self, wf: str, spec: dict, now: int, live: dict, live_since: int, end_minute: int, blocked: set[str],
             incident_open: bool):
        """Advance every experiment of one workflow. `blocked` = dims held by a supervisor edit."""
        if spec["objective"]["primary"] != "engagement_rate":
            return  # welcome/voice act after pickup: they cannot move a pickup-primary KPI (see SUBMISSION assumption A5)
        days_left = (end_minute - now) / 1440
        for dim in EXP_DIMS:
            if len(spec["options"].get(dim, [])) < 2 or dim in blocked:
                continue
            e = self.active(wf, dim)
            if e is None:
                if not incident_open:
                    self._maybe_start(wf, spec, dim, now, live, days_left)
            elif e["status"] == "running":
                self._eval_running(wf, spec, dim, e, now, live, live_since, days_left)
            elif e["status"] == "promoting":
                self._check_live(wf, dim, e, now, live, live_since)
            elif e["status"] == "monitoring":
                self._monitor(wf, spec, dim, e, now, live, live_since)

    # ------------------------------------------------------------------ start
    def _baseline_eng(self, wf: str, now: int) -> tuple[float, float]:
        d = self.agg.wf("agg_day", wf)
        conn = eng = 0
        for (day,), v in d.items():
            if day >= now // 1440 - 7:
                conn += v[2]; eng += v[3]
        n_days = max(1, len({k[0] for k in d if k[0] >= now // 1440 - 7}))
        return (eng / conn if conn else 0.5), conn / n_days

    def _maybe_start(self, wf, spec, dim, now, live, days_left):
        hist = self._history(wf, dim)
        tested = {a for h in hist for a in h["arms"]} | {h["control"] for h in hist}
        black = {a for h in hist for a in h["state"].get("blacklist", [])}
        if days_left < P["min_days_left"] + (1.0 if hist else 0.0):
            return
        # a previous round's plan must be fully live (and a cooldown passed) before the next test starts: otherwise the
        # new test would overwrite, say, a pending revert to the incumbent
        if not self._live_matches(live, self.plans.get(wf)["alloc"], dim):
            return
        if hist and now - max(h.get("updated", 0) or 0 for h in hist) < 720:
            return
        base_eng, conn_day = self._baseline_eng(wf, now)
        if conn_day < P["min_conn_per_day"]:
            return
        cur = cfgutil.dist(live, "default", dim)
        control = max(cur, key=lambda o: (cur[o], o))
        cands = [o for o in spec["options"][dim] if o != control and o not in black and o not in tested]
        if hist and not cands:
            return  # every option has been through an experiment: settled
        if not hist:
            cands = [o for o in spec["options"][dim] if o != control]
        cands = cands[:4]
        if not cands:
            return
        k = len(cands)
        cs = P["control_share"] if k > 1 else 0.5
        alloc = {control: cs, **{o: (1 - cs) / k for o in cands}}
        n = len(hist) + 1
        eid = f"{wf}:{dim}:{n}"
        prereg = {**P, "baseline_eng": round(base_eng, 4), "tau": round(P["tau_rel"] * base_eng, 4),
                  "metric": "engagement_rate (engaged / connected)", "guardrail": spec["objective"].get("guardrail"),
                  "family": f"{k} arms vs incumbent {control}; Holm across arms; always-valid (mSPRT) p-values",
                  "allocation": alloc}
        e = {"id": eid, "status": "running", "control": control, "arms": cands, "prereg": prereg,
             "started_min": now, "promo_min": None,
             "state": {"live_min": None, "alloc": alloc, "dropped": [], "blacklist": sorted(black), "last_eval": -1,
                       "bad_streak": 0}}
        self._save(e, wf, dim, now)
        did = self.audit.decision(
            now, wf, "experiment_started", f"dimension {dim} has untested options {cands}", "pre-registered design",
            prereg, "plan updated",
            f"{dim}: incumbent {control} vs {cands}; control share {cs:.0%}; mSPRT+Holm, alpha {P['alpha_win']}",
            experiment_id=eid)
        self.plans.set_alloc(wf, "default", dim, alloc, {
            "kind": "experiment_start", "ref": eid, "urgent": False, "decision": did, "reach": 1.0,
            "summary": f"start a {k + 1}-arm {dim} test ({control} stays at {cs:.0%})",
            "exploration": True, "alloc": alloc})

    # ------------------------------------------------------------------ live-matching helpers
    def _live_matches(self, live: dict, plan_alloc: dict, dim: str) -> bool:
        for coh, dims in plan_alloc.items():
            if dim in dims and cfgutil.tv(cfgutil.dist(live, coh, dim), dims[dim]) > 1e-3:
                return False
        return True

    def _check_live(self, wf, dim, e, now, live, live_since):
        plan = self.plans.get(wf)
        if self._live_matches(live, plan["alloc"], dim):
            e["status"] = "monitoring"
            e["promo_min"] = live_since
            e["state"].update({"bad_streak": 0, "mon_since_ver": None})
            self._save(e, wf, dim, now)
            self.audit.decision(now, wf, "promotion_live", f"approved allocation for {dim} is live",
                                "plan == live config", {"live_since": live_since}, "monitoring started",
                                f"{dim}: promoted allocation live; decay monitor armed vs {e['state']['holdout']} holdout",
                                experiment_id=e["id"])

    # ------------------------------------------------------------------ running experiment
    def _eval_running(self, wf, spec, dim, e, now, live, live_since, days_left):
        st = e["state"]
        plan = self.plans.get(wf)
        if st["live_min"] is None:
            if not self._live_matches(live, plan["alloc"], dim):
                return  # permission not (yet) given: the arms have not run, so there is nothing to learn from
            st["live_min"] = live_since
            self._save(e, wf, dim, now)
        if now - st["last_eval"] < P["eval_every_min"] and now % 1440 != 0:
            return
        st["last_eval"] = now
        pr = e["prereg"]
        strata = build_strata(self.agg, wf, dim, e["started_min"] // 1440)
        ctrl = e["control"]
        tau2 = pr["tau"] ** 2
        look: dict = {}
        pvals_win: dict = {}
        for a in e["arms"]:
            if a in st["dropped"]:
                continue
            r = contrast(strata, a, ctrl, "eng")
            if r is None:
                continue
            delta, var, na, nc, used = r
            if na < P["n_min"] or nc < P["n_min"]:
                look[a] = {"n_arm": na, "n_ctrl": nc, "status": "collecting"}
                continue
            p_inst = msprt_p(delta, var, tau2)
            kc, nc_all = arm_rates(strata, ctrl)
            pc = kc / nc_all if nc_all else pr["baseline_eng"]
            if delta > 0:
                pw = self._pmin(e["id"], a, "ALL", "win", p_inst)
                pvals_win[a] = pw
                ph = 1.0
            else:
                pw = 1.0
                pvals_win[a] = 1.0
                ph = self._pmin(e["id"], a, "ALL", "harm", p_inst)
            se = math.sqrt(var)
            look[a] = {"delta": round(delta, 4), "rel": round(delta / max(pc, 1e-9), 4), "se": round(se, 4),
                       "lcb": round(delta - 1.645 * se, 4), "n_arm": na, "n_ctrl": nc, "strata": used,
                       "p_now": round(p_inst, 5), "p_win_min": round(pw, 5), "p_harm_min": round(ph, 5),
                       "ctrl_rate": round(pc, 4)}
        # ---- harm-stop: stop feeding a clearly worse arm (cheap, reversible, loosens exposure)
        to_drop = [a for a, v in look.items() if v.get("p_harm_min", 1) <= P["alpha_harm_drop"] and
                   v.get("delta", 0) <= -P["drop_abs"]]
        # ---- futility: an arm whose 90% upper bound cannot reach a useful lift is not worth more traffic. Dropping it
        # only re-allocates exposure (it never declares a winner), so it does not touch the false-winner budget.
        for a, v in look.items():
            if a not in to_drop and "delta" in v and v["n_arm"] >= 2 * P["n_min"] and \
                    v["delta"] + 1.28 * v["se"] < P["min_lift_rel"] * v["ctrl_rate"]:
                to_drop.append(a)
        # ---- decay while still in test: pooled-over-time estimates average a fading novelty effect with its good days,
        # so also look at the last ~36h on its own. An arm that is not beating control *now* gets no more traffic.
        decaying = []
        for a in e["arms"]:
            if a in st["dropped"] or a in to_drop or a not in look or "delta" not in look[a]:
                continue
            rc = self._recent(wf, dim, a, ctrl, now, 6)
            if rc and rc[2] >= 150 and rc[3] >= 150 and rc[0] + 1.28 * rc[1] < 0 < look[a]["delta"]:
                look[a]["recent"] = {"delta": round(rc[0], 4), "se": round(rc[1], 4), "n_arm": rc[2], "n_ctrl": rc[3]}
                decaying.append(a)
                to_drop.append(a)
        # ---- winners
        winners = {}
        if pvals_win:
            res = holm({a: p for a, p in pvals_win.items() if a in look and "delta" in look[a]}, P["alpha_win"])
            for a, (rej, adj) in res.items():
                v = look[a]
                v["holm_adj_p"] = round(adj, 5)
                if rej and v["delta"] > 0 and v["rel"] >= P["min_lift_rel"] and a not in decaying:
                    winners[a] = v
        elapsed_d = (now - (st["live_min"] or now)) / 1440
        timeup = elapsed_d >= P["max_days"] or days_left < 1.0
        snapshot = {"look": look, "winners": list(winners), "elapsed_days": round(elapsed_d, 2)}
        if winners:
            best = max(winners, key=lambda a: (winners[a]["lcb"], a))
            guard = self._guardrail_ok(strata, best, ctrl, spec)
            recent = self._recency_ok(wf, dim, best, ctrl, now, winners[best]["delta"])
            snapshot.update({"best": best, "guardrail": guard, "recency": recent})
            if guard["ok"] and recent["ok"]:
                self._conclude(wf, spec, dim, e, now, strata, best, look, snapshot, live)
                return
            self.audit.decision(now, wf, "winner_blocked", f"{best} cleared the significance bar on {dim}",
                                "guardrail/recency gate", snapshot, "not promoted",
                                f"{best} held back: guardrail_ok={guard['ok']} recency_ok={recent['ok']}",
                                experiment_id=e["id"])
        if timeup:
            self._conclude(wf, spec, dim, e, now, strata, None, look, snapshot, live)
            return
        if to_drop:
            new_arms = [a for a in e["arms"] if a not in st["dropped"] and a not in to_drop]
            st["dropped"] += to_drop
            st["blacklist"] = sorted(set(st.get("blacklist", [])) | set(decaying))
            if new_arms:
                # freed traffic goes back to the incumbent, NOT to the surviving arms: a survivor that has not been promoted
                # yet may itself be fading, and exposure to unproven arms must only ever shrink
                prev = st["alloc"]
                alloc = {o: prev[o] for o in new_arms}
                alloc[ctrl] = 1.0 - sum(alloc.values())
                st["alloc"] = alloc
                did = self.audit.decision(now, wf, "arm_dropped", f"{to_drop} not worth more traffic on {dim} "
                                          f"(decaying now: {decaying})",
                                          f"harm (always-valid p<={P['alpha_harm_drop']}, lift<=-{P['drop_abs']}) | futility (90% UB < min lift) | decay (last 36h lift<0)",
                                          snapshot, "plan updated", f"stop exposing {to_drop} ({dim}); remaining {new_arms}",
                                          experiment_id=e["id"])
                self.plans.set_alloc(wf, "default", dim, alloc, {
                    "kind": "arm_drop", "ref": e["id"], "urgent": False, "decision": did, "reach": 1.0,
                    "summary": f"stop {', '.join(to_drop)} ({dim}) - not beating {ctrl}" + (f" (fading: {', '.join(decaying)})" if decaying else ""), "alloc": alloc,
                    "exploration": False})
            else:
                self._conclude(wf, spec, dim, e, now, strata, None, look, snapshot, live)
                return
        self._save(e, wf, dim, now)
        if now % 1440 == 0:  # one compact heartbeat per day keeps the audit readable
            self.audit.decision(now, wf, "experiment_look", f"daily look on {dim}", "always-valid monitoring", snapshot,
                                "continue", f"{dim}: no winner yet", experiment_id=e["id"])

    def _recent(self, wf: str, dim: str, arm: str, ctrl: str, now: int, n_buckets: int):
        """(delta, se, n_arm, n_ctrl) of engagement, arm vs control, over the last n 6-hour buckets (strata by version/cohort)."""
        b_from = now // 360 - n_buckets + 1
        strata: dict = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
        for (b6, ver, coh, d, opt), v in self.agg.wf("agg_arm6", wf).items():
            if d != dim or b6 < b_from or opt not in (arm, ctrl):
                continue
            a = strata[(ver, coh)][opt]
            a[0] += v[0]; a[1] += v[1]; a[2] += v[2]
        lst = [(by[arm][2], by[arm][1], by[ctrl][2], by[ctrl][1]) for by in strata.values() if arm in by and ctrl in by]
        r = stratified_contrast(lst, 20)
        if r is None:
            return None
        return r[0], math.sqrt(r[1]), r[2], r[3]

    def _guardrail_ok(self, strata, arm, ctrl, spec) -> dict:
        r = contrast(strata, arm, ctrl, "conn")
        if r is None:
            return {"ok": True, "note": "no pickup contrast yet"}
        delta, var, na, nc, _ = r
        ucb = delta + 1.28 * math.sqrt(var)
        return {"ok": ucb > -0.01, "pickup_delta": round(delta, 4), "pickup_ucb90": round(ucb, 4)}

    def _recency_ok(self, wf, dim, arm, ctrl, now, pooled_delta) -> dict:
        """Novelty / decay guard. Fading effects look great averaged over their good days, so before promoting the data must
        still show the lift *recently*: last ~36h >= 50% of the pooled lift AND last ~12h >= 25% of it (when there are enough
        calls to say anything - otherwise no evidence contradicts the winner)."""
        out = {"ok": True, "rule": "36h lift >= 50% of pooled and 12h lift >= 25% of pooled", "pooled_delta": round(pooled_delta, 4)}
        r36 = self._recent(wf, dim, arm, ctrl, now, 6)
        if r36 is not None and r36[2] >= 150 and r36[3] >= 150:
            out["recent36_delta"] = round(r36[0], 4)
            out["ok"] = r36[0] >= 0.5 * pooled_delta
        r12 = self._recent(wf, dim, arm, ctrl, now, 2)
        if r12 is not None and r12[2] >= 100 and r12[3] >= 100:
            out["recent12_delta"] = round(r12[0], 4)
            out["ok"] = out["ok"] and r12[0] >= 0.25 * pooled_delta
        return out

    # ------------------------------------------------------------------ conclusion (+ segment analysis)
    def _conclude(self, wf, spec, dim, e, now, strata, winner, look, snapshot, live):
        ctrl = e["control"]
        seg = self._segments(wf, spec, dim, e, strata, winner, ctrl, live)
        snapshot["segments"] = seg["summary"]
        h = P["stage1_holdout"]   # staged promotion: 50/50 first; the step to 75/25 must be earned (see _monitor)
        plan_alloc = {}
        if winner:
            plan_alloc["default"] = {winner: 1 - h, ctrl: h}
        else:
            plan_alloc["default"] = {ctrl: 1.0}
        for cid, arm in seg["overrides"].items():
            plan_alloc[cid] = {arm: 1 - h, ctrl: h} if arm != ctrl else {ctrl: 1.0}
        needs_cohorts = list(seg["cohort_defs"].values())
        e["state"].update({"winner": winner, "alloc": plan_alloc, "holdout": h, "stage": 1, "overrides": seg["overrides"],
                           "L0": look.get(winner, {}).get("delta") if winner else None,
                           "L0_rel": look.get(winner, {}).get("rel") if winner else None,
                           "blacklist": sorted(set(e["state"].get("blacklist", [])) | set(e["state"]["dropped"]))})
        if winner is None and not seg["overrides"]:
            e["status"] = "closed"
            e["state"]["result"] = "no_winner"
            e["state"]["closed_min"] = now
            self._save(e, wf, dim, now)
            did = self.audit.decision(now, wf, "no_winner", f"{dim} test reached its budget without a winner",
                                      "pre-registered stopping rule", snapshot, "revert to incumbent",
                                      f"{dim}: no arm beat {ctrl} at alpha {P['alpha_win']}; returning to {ctrl}",
                                      experiment_id=e["id"])
            self.plans.set_alloc(wf, "default", dim, {ctrl: 1.0}, {
                "kind": "experiment_end", "ref": e["id"], "urgent": False, "decision": did, "reach": 1.0,
                "summary": f"end {dim} test, keep {ctrl} (no arm was better)", "exploration": False})
            return
        e["status"] = "promoting"
        self._save(e, wf, dim, now)
        lift = look.get(winner, {}).get("rel") if winner else None
        did = self.audit.decision(
            now, wf, "winner_declared" if winner else "segment_winners",
            f"{dim}: {winner or 'segment-specific arms'} cleared the pre-registered bar",
            f"Holm-adjusted always-valid p<={P['alpha_win']}, lift>={P['min_lift_rel']:.0%}, guardrail+recency+segment-veto",
            snapshot, "promotion planned", f"{dim}: promote {winner or seg['overrides']} (holdout {h:.0%} on {ctrl})",
            experiment_id=e["id"])
        reach = 1.0
        for cid, dims in plan_alloc.items():
            if cid == "default" and winner is None:  # only segment findings: everyone else returns to the incumbent
                self.plans.set_alloc(wf, cid, dim, dims, {
                    "kind": "experiment_end", "ref": e["id"], "urgent": False, "decision": did, "reach": 1.0, "exploration": False,
                    "summary": f"end {dim} test: keep {ctrl} for everyone outside the cohorts below"})
                continue
            self.plans.set_alloc(wf, cid, dim, dims, {
                "kind": "promotion", "ref": e["id"], "urgent": False, "decision": did, "reach": reach,
                "summary": f"promote {winner if cid == 'default' else seg['overrides'].get(cid)} for {dim} "
                           f"({'everyone' if cid == 'default' else cid}); keep {h:.0%} holdout on {ctrl}",
                "lift_rel_lcb": (look[winner]["lcb"] / max(look[winner]["ctrl_rate"], 1e-9)) if winner else None,
                "lift_rel": lift, "exploration": False})
        if needs_cohorts:
            self._merge_cohorts(wf, needs_cohorts, did, e["id"])

    def _merge_cohorts(self, wf: str, new_defs: list[dict], decision_id: int, exp_id: str):
        self.plans.add_cohort_defs(wf, new_defs)

    @staticmethod
    def partition_features(live: dict) -> list[str] | None:
        """None = no cohorts exist yet (any single feature may become the partition). Otherwise the one feature all
        existing cohorts split on - new cohorts must use it so first-match membership stays disjoint and consistent."""
        feats = set()
        for c in live.get("cohorts", []):
            feats |= set(c["where"])
        if not feats:
            return None
        return sorted(feats) if len(feats) == 1 else []

    # ---- segment analysis: one fixed-sample look, Holm over the pre-registered family
    def _segments(self, wf, spec, dim, e, strata, winner, ctrl, live) -> dict:
        levels = self._levels(wf)
        allowed = self.partition_features(live)
        if allowed is not None:
            levels = {f: v for f, v in levels.items() if f in allowed}
        arms = [a for a in e["arms"] if a not in e["state"]["dropped"]]
        tests = {}   # (arm, feature, level) -> (delta, se, n_a, n_c)
        for f, vals in levels.items():
            for v in vals:
                coh = C.Cohort.make({f: [v]})
                for a in arms:
                    r = contrast(strata, a, ctrl, "eng", pred=coh.matches)
                    if r is None or r[2] < P["n_seg_min"] or r[3] < P["n_seg_min"]:
                        continue
                    tests[(a, f, v)] = (r[0], math.sqrt(r[1]), r[2], r[3])
        pv = {}
        for key, (d, se, na, nc) in tests.items():
            z = d / se if se > 0 else 0.0
            pv[key] = 2 * norm_sf(abs(z))
        benefit_candidates = {k: p for k, p in pv.items() if tests[k][0] > 0}
        rej = holm(benefit_candidates, P["alpha_seg"]) if benefit_candidates else {}
        findings: dict[str, dict] = defaultdict(dict)   # feature -> level -> arm (best lcb among Holm-rejected)
        vetoes: dict[str, set] = defaultdict(set)
        for k, (ok, adj) in rej.items():
            a, f, v = k
            d, se, na, nc = tests[k]
            if ok and d >= P["min_seg_lift_rel"] * 0.55:   # practical significance: >=5% of a ~55% engagement rate
                cur = findings[f].get(v)
                lcb = d - 1.645 * se
                if cur is None or lcb > cur[1]:
                    findings[f][v] = (a, lcb)
        if winner:
            for (a, f, v), (d, se, na, nc) in tests.items():
                if a == winner and d / se <= -P["veto_z"] and d <= -P["veto_abs"]:
                    vetoes[f].add(v)
        score = {f: len(findings.get(f, {})) + len(vetoes.get(f, ())) for f in levels}
        best_f = max(score, key=lambda f: (score[f], f)) if score and max(score.values()) > 0 else None
        overrides, defs = {}, {}
        if best_f:
            items = []
            for v, (a, lcb) in findings.get(best_f, {}).items():
                if a != winner:
                    items.append((v, a))
            for v in vetoes.get(best_f, ()):
                items.append((v, ctrl))
            for v, a in sorted(items)[:P["max_override_cohorts"]]:
                coh = C.Cohort.make({best_f: [v]})
                overrides[coh.id] = a
                defs[coh.id] = coh.to_config()
        summary = {"tests": len(tests), "benefit_findings": {f: {v: a for v, (a, _) in d.items()} for f, d in findings.items() if d},
                   "harm_vetoes": {f: sorted(s) for f, s in vetoes.items() if s}, "partition_feature": best_f,
                   "overrides": overrides, "alpha": P["alpha_seg"], "n_seg_min": P["n_seg_min"]}
        return {"overrides": overrides, "cohort_defs": defs, "summary": summary}

    def _levels(self, wf: str) -> dict[str, list[str]]:
        seen: dict[str, set] = {f: set() for f in C.FEATURES}
        cells = {k[3] for k in self.agg.wf("agg_cell", wf)}
        for cell in cells:
            t = C.cell_tuple(cell)
            for i, f in enumerate(C.FEATURES):
                seen[f].add(t[i])
        return {f: sorted(v) for f, v in seen.items()}

    # ------------------------------------------------------------------ monitoring: decay & harm after promotion
    def _monitor(self, wf, spec, dim, e, now, live, live_since):
        st = e["state"]
        if now - st.get("last_mon", -10 ** 9) < 180 and now % 1440 != 0:
            return
        st["last_mon"] = now
        ctrl, h = e["control"], st.get("holdout", P["holdout"])
        b_now = now // 360
        b_from = max(b_now - (P["mon_buckets"] - 1), (e["promo_min"] or now) // 360)  # last 18h, never before it went live
        rows = self.agg.wf("agg_arm6", wf)
        strata: dict = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
        for (b6, ver, coh, d, opt), v in rows.items():
            if d != dim or b6 < b_from:
                continue
            a = strata[(ver, coh)][opt]
            a[0] += v[0]; a[1] += v[1]; a[2] += v[2]
        out = {}
        bad = False
        reasons = []
        promoted = {"default": st.get("winner")} if st.get("winner") else {}
        for cid, arm in st.get("overrides", {}).items():
            if arm != ctrl:
                promoted[cid] = arm
        for cid, arm in promoted.items():
            if not arm:
                continue
            lst = []
            own = set(st.get("overrides", {}))
            for (ver, coh), by in strata.items():
                in_scope = (coh not in own) if cid == "default" else (coh == cid)
                if not in_scope or arm not in by or ctrl not in by:
                    continue
                lst.append((by[arm][2], by[arm][1], by[ctrl][2], by[ctrl][1]))
            r = stratified_contrast(lst, 20)
            if r is None or r[2] < P["mon_min_arm"] or r[3] < P["mon_min_ctrl"]:
                out[cid] = {"status": "insufficient recent data"}
                continue
            d, var, na, nc, _ = r
            se = math.sqrt(var)
            L0 = st.get("L0") if cid == "default" else None
            harm = d <= -0.01 and d / se <= -2.0
            decayed = L0 is not None and L0 > 0 and (d + 1.28 * se) < P["decay_frac"] * L0
            out[cid] = {"arm": arm, "lift_24h": round(d, 4), "se": round(se, 4), "n_arm": na, "n_hold": nc,
                        "promised_lift": L0, "harm": harm, "decayed": decayed}
            if harm or decayed:
                bad = True
                reasons.append(f"{cid}:{arm} {'harmful' if harm else 'decayed'} (24h lift {d:+.3f} vs promised {L0})")
        st["bad_streak"] = st.get("bad_streak", 0) + 1 if bad else 0
        if bad and st["bad_streak"] >= P["mon_consecutive"]:
            self._rollback(wf, dim, e, now, out, reasons)
        elif (not bad and st.get("stage") == 1 and e["promo_min"] is not None and
              now - e["promo_min"] >= P["stage2_after_min"] and out and
              all(v.get("lift_24h") is not None and v["lift_24h"] >= P["decay_frac"] * (st.get("L0") or 0.0) for v in out.values())):
            self._stage2(wf, dim, e, now, out)
        else:
            self._save(e, wf, dim, now)
            if now % 1440 == 0 or bad:
                self.audit.decision(now, wf, "monitor", f"post-promotion check on {dim}",
                                    "24h lift vs holdout (decay/harm rules)", out,
                                    "WATCH (1 more bad look triggers rollback)" if bad else "ok",
                                    f"{dim}: " + ("; ".join(reasons) if bad else "promoted variant still beats the holdout"),
                                    experiment_id=e["id"])

    def _stage2(self, wf, dim, e, now, evidence):
        """The promoted variant has held its lift against a 50% holdout for 24h: now (and only now) widen it to 75/25."""
        st, ctrl, h = e["state"], e["control"], P["holdout"]
        plan_alloc = {}
        if st.get("winner"):
            plan_alloc["default"] = {st["winner"]: 1 - h, ctrl: h}
        for cid, arm in st.get("overrides", {}).items():
            plan_alloc[cid] = {arm: 1 - h, ctrl: h} if arm != ctrl else {ctrl: 1.0}
        st.update({"stage": 2, "holdout": h, "alloc": plan_alloc})
        e["status"] = "promoting"
        self._save(e, wf, dim, now)
        did = self.audit.decision(now, wf, "promotion_stage2", f"{dim}: promoted variant held its lift for 24h at 50/50",
                                  "staged promotion: widen only after confirmation", evidence, "plan updated",
                                  f"widen {dim} winner to {1 - h:.0%} (holdout {h:.0%})", experiment_id=e["id"])
        for cid, dims in plan_alloc.items():
            if cid == "default" and not st.get("winner"):
                continue
            self.plans.set_alloc(wf, cid, dim, dims, {
                "kind": "promotion", "ref": e["id"], "urgent": False, "decision": did, "reach": 1.0,
                "summary": f"widen the {dim} winner from 50% to {1 - h:.0%} ({cid if cid != 'default' else 'everyone'}) - it held its lift for 24h",
                "lift_rel_lcb": (st.get("L0_rel") or 0.0) * 0.5, "exploration": False})

    def _rollback(self, wf, dim, e, now, evidence, reasons):
        ctrl = e["control"]
        st = e["state"]
        bl = set(st.get("blacklist", []))
        if st.get("winner"):
            bl.add(st["winner"])
        bl |= {a for a in st.get("overrides", {}).values() if a != ctrl}
        st["blacklist"] = sorted(bl)
        st["result"] = "rolled_back"
        st["closed_min"] = now
        e["status"] = "closed"
        self._save(e, wf, dim, now)
        did = self.audit.decision(now, wf, "rollback_planned", f"{dim}: " + "; ".join(reasons),
                                  f"{P['mon_consecutive']} consecutive looks with harm or decay", evidence,
                                  "plan reverted to incumbent (urgent)",
                                  f"roll {dim} back to {ctrl}; blacklist {sorted(bl)}", experiment_id=e["id"])
        plan = self.plans.get(wf)
        for cid in list(plan["alloc"]):
            if dim in plan["alloc"][cid] and cid != "default":
                self.plans.clear(wf, f"alloc:{cid}:{dim}")
        self.plans.set_alloc(wf, "default", dim, {ctrl: 1.0}, {
            "kind": "rollback", "ref": e["id"], "urgent": True, "decision": did, "reach": 1.0,
            "summary": f"roll back {dim} to {ctrl}: " + "; ".join(reasons), "exploration": False, "safety": True})
        self.st.x("INSERT INTO autonomy(wf,dim,level,since_min,reason) VALUES(?,?,0,?,?) ON CONFLICT(wf,dim) DO UPDATE SET "
                  "level=0, since_min=excluded.since_min, reason=excluded.reason",
                  (wf, dim, now, "autonomy revoked: promoted variant had to be rolled back"))
