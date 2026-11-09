"""Incident response: caller-ID health (C5) and hallucination spikes (C8).

Both are *detect -> plan -> verify* loops that run on population statistics. They only edit the plan; the governance
executor decides the route (auto-apply where the policy permits, approval otherwise).

Prompt-incident flow (credits are only spent where they change a decision):
  detect (flag-rate z-test vs the same detector's pre-change rate)
    -> candidate #1 = last known-good prompt (its engagement is already measured in production)
    -> validate it (n=1000, 10 credits) against a safety gate; if it passes we STOP: no LLM call is needed
    -> else ask the LLM for alternatives (3 credits), validate each, choose the least restrictive prompt that clears the
       gate (validation measures safety only; stricter prompts cost engagement - 'verbatim script' bots lose callers)
    -> propose with the validation run as evidence, urgent (a hallucinating bot must not wait for a time slot)
    -> verify after apply: flag rate back to reference AND engagement not worse; otherwise escalate / revert.
"""
from __future__ import annotations

import json
import logging
import math

from . import cfgutil, detect
from .audit import Audit
from .plan import PlanStore
from .simclient import Sim, SimError
from .stats import two_prop
from .store import Store
from .util import maybe_crash, minute_to_str

log = logging.getLogger("controller.incident")

VALID_N = 1000
FAIL_GATE = 0.015
INCIDENT_CREDIT_CAP = 60.0
CREDIT_FLOOR = 25.0


class Incidents:
    def __init__(self, st: Store, sim: Sim, audit: Audit, plans: PlanStore, agg):
        self.st, self.sim, self.audit, self.plans, self.agg = st, sim, audit, plans, agg
        self.credits_remaining: float | None = None

    # =================================================================== caller ID (C5)
    def step_did(self, wf: str, spec: dict, now: int, live: dict, held: bool):
        if held or len(spec["options"]["caller_id"]) < 2:
            return
        opts = spec["options"]["caller_id"]
        live_dist = cfgutil.dist(live, "default", "caller_id")
        known_bad = set(self.st.get(f"bad_dids:{wf}", []))
        since = self.st.get(f"bad_dids_since:{wf}", {})
        for d in [d for d in known_bad if now - since.get(d, now) > 48 * 60]:  # parked IDs are re-examined every 2 days
            known_bad.discard(d)
            since.pop(d, None)
            self.st.put(f"bad_dids:{wf}", sorted(known_bad))
            self.st.put(f"bad_dids_since:{wf}", since)
        inc = self._open(wf, "did_degraded")
        # ---- fast path: a degraded number (hours, not days). Short window, strong response, then it STOPS.
        short = detect.by_did(detect.tick_window(self.agg, wf, now - 6 * 60, now))
        flagged = {b["did"]: b for b in detect.did_degraded(short)}
        fresh = [b for d, b in flagged.items() if d not in known_bad]
        if fresh:
            known_bad |= set(flagged)
            for d in flagged:
                since.setdefault(d, now)
            self.st.put(f"bad_dids:{wf}", sorted(known_bad))
            self.st.put(f"bad_dids_since:{wf}", since)
            if inc is None:
                iid = f"{wf}:did:{now}"
                self.st.x("INSERT OR IGNORE INTO incidents(id,wf,kind,status,opened_min,state) VALUES(?,?,?,?,?,?)",
                          (iid, wf, "did_degraded", "open", now, json.dumps({"bad": fresh})))
                inc = self._open(wf, "did_degraded")
            self.audit.decision(now, wf, "incident_detected", f"caller ID {[b['did'] for b in fresh]} degraded",
                                "peer-relative pickup z>=3.5 and ratio<=0.6 over the last 6h", {"bad": fresh, "live": live_dist},
                                "response planned", f"{fresh[0]['did']} pickup {fresh[0]['pickup']:.1%} vs peers {fresh[0]['peer_pickup']:.1%}")
            self.audit.alert(now, "ticket", wf, "caller_id_degraded",
                             f"{fresh[0]['did']} pickup is {fresh[0]['ratio']:.0%} of its peers. Controller is rotating traffic away; "
                             "check the number's spam-reputation with the carrier.")
        # ---- recovery test for numbers we parked: back at >= 85% of peers over >=150 probe dials -> release
        long = detect.by_did(detect.tick_window(self.agg, wf, now - 48 * 60, now))
        for d in sorted(known_bad):
            nd, cd = long.get(d, [0, 0])
            rn = sum(v[0] for k, v in long.items() if k != d)
            rc = sum(v[1] for k, v in long.items() if k != d)
            if nd >= 150 and rn >= 300 and d not in flagged and cd / nd >= 0.85 * (rc / rn):
                known_bad.discard(d)
                self.st.put(f"bad_dids:{wf}", sorted(known_bad))
                self.audit.decision(now, wf, "did_recovered", f"{d} pickup back within 15% of its peers", "recovery probe", 
                                    {"dials": nd, "pickup": round(cd / nd, 4), "peer": round(rc / rn, 4)}, "released to the balancer",
                                    f"{d} may carry traffic again (balancer will ramp it)")
        if known_bad:
            tgt, ev = detect.did_target(short if sum(v[0] for v in short.values()) >= 120 else long, live_dist, opts,
                                        eta=3.0, min_dials=30)
            tgt = dict(tgt or live_dist)
            floor = 0.03
            freed = sum(max(0.0, tgt.get(d, 0.0) - floor) for d in known_bad)
            for d in known_bad:
                tgt[d] = min(tgt.get(d, 0.0), floor)
            good = [o for o in opts if o not in known_bad]
            gs = sum(tgt.get(o, 0.0) for o in good) or 1.0
            tgt = {**{o: tgt.get(o, 0.0) * (1 - sum(tgt[d] for d in known_bad if d in tgt)) / gs for o in good},
                   **{d: tgt[d] for d in known_bad if d in tgt}}
            parked = max(live_dist.get(d, 0.0) for d in known_bad)
            if parked > floor + 0.03:
                self.plans.set_alloc(wf, "default", "caller_id", tgt, {
                    "kind": "did_rotation", "ref": "did", "urgent": True, "safety": True, "severity": 0.5,
                    "reach": 1.0, "decision": None, "summary":
                        f"rotate traffic away from caller ID {', '.join(sorted(known_bad))} (pickup far below the other IDs in the same hours)",
                    "rationale": "caller-ID pickup is statistically and materially below its peers in the same hours",
                    "evidence_text": "z>=3.5, ratio<=0.6, 6h window", "alloc": tgt, "projection": {
                        "metric": "pickup_rate", "note": f"{parked:.0%} of dials are on a degraded ID; moving them to healthy IDs "
                        "lifts pickup toward the peer rate"}})
                return
            # converged: the degraded ID sits at its probe floor
            p = self.plans.get(wf)
            if p["why"].get("alloc:default:caller_id", {}).get("kind") == "did_rotation":
                self.plans.clear(wf, "alloc:default:caller_id")
            if inc is not None:
                self.st.x("UPDATE incidents SET status='closed', closed_min=? WHERE id=?", (now, inc["id"]))
                self.audit.decision(now, wf, "incident_closed", "caller-ID incident contained",
                                    "degraded ID share <= probe floor", {"live": live_dist},
                                    "closed", f"caller-ID incident {minute_to_str(inc['opened'])} -> {minute_to_str(now)} "
                                    f"({now - inc['opened']} min); {sorted(known_bad)} parked at {floor:.0%} probe share")
                self.audit.resolve_alert(now, wf, "caller_id_degraded")
        # ---- slow path: keep traffic spread by observed health (also explores unused IDs safely), at most twice a day
        if (now % 720 == 0 and now - self.st.get(f"did_last:{wf}", -10 ** 9) >= 600) or self.st.get(f"did_first:{wf}") is None:
            self.st.put(f"did_first:{wf}", now)
            long24 = detect.by_did(detect.tick_window(self.agg, wf, now - 24 * 60, now))
            if sum(v[0] for v in long24.values()) < 200:
                long24 = detect.by_did(detect.tick_window(self.agg, wf, now - 7 * 1440, now))
            tgt, ev = detect.did_target(long24, live_dist, opts, eta=1.5)
            if tgt and known_bad:
                for d in known_bad:
                    tgt[d] = min(tgt.get(d, 0.0), 0.03)
                tgt = cfgutil.round_dist(tgt)
            if tgt and cfgutil.tv(live_dist, tgt) >= 0.04:
                self.st.put(f"did_last:{wf}", now)
                self.plans.set_alloc(wf, "default", "caller_id", tgt, {
                    "kind": "did_balance", "ref": "did", "urgent": False, "reach": 1.0, "decision": None,
                    "summary": "spread calls across caller IDs by observed pickup (and probe unused IDs)",
                    "rationale": "caller IDs differ significantly in pickup / some IDs are unmeasured",
                    "evidence_text": f"homogeneity p={ev.get('homogeneity_p')}, spread={ev.get('spread')}",
                    "lift_rel_lcb": 0.0, "exploration": True, "alloc": tgt,
                    "projection": {"metric": "pickup_rate", "evidence": ev}})
                self.audit.decision(now, wf, "did_rebalance", "caller IDs differ in pickup or are unmeasured",
                                    "chi-square homogeneity p<=0.01 & spread>=8%, floors 3%, probe 5%, move>=4pts", ev,
                                    "plan updated", f"caller_id -> {({k: round(v, 3) for k, v in tgt.items()})}")
            elif self.plans.get(wf)["why"].get("alloc:default:caller_id", {}).get("kind") == "did_balance":
                self.plans.clear(wf, "alloc:default:caller_id")

    def _open(self, wf: str, kind: str):
        r = self.st.one("SELECT id, opened_min, state FROM incidents WHERE wf=? AND kind=? AND status='open'", (wf, kind))
        if not r:
            return None
        st = json.loads(r[2])
        st["bad_dids"] = [b["did"] for b in st.get("bad", [])]
        return {"id": r[0], "opened": r[1], "state": st}

    # =================================================================== hallucination (C8)
    def step_prompt(self, wf: str, spec: dict, now: int, live: dict, ver: int, credits: float):
        self.credits_remaining = credits
        cur = live["prompt_version"]
        inc = self.st.one("SELECT id, status, opened_min, state FROM incidents WHERE wf=? AND kind='prompt_halluc' "
                          "AND status!='closed'", (wf,))
        if inc:
            self._advance_incident(wf, spec, now, live, ver, inc)
            return
        ref = self._reference_rate(wf, cur, now)
        hit = detect.halluc_check(self.agg, wf, cur, now, ref)
        if not hit:
            return
        iid = f"{wf}:prompt:{now}"
        bad = set(self.st.get(f"bad_prompts:{wf}", []))
        bad.add(cur)
        self.st.put(f"bad_prompts:{wf}", sorted(bad))
        state = {"phase": "detected", "bad_prompt": cur, "evidence": hit, "validated": {}, "spent": 0.0}
        self.st.x("INSERT INTO incidents(id,wf,kind,status,opened_min,state) VALUES(?,?,?,?,?,?)",
                  (iid, wf, "prompt_halluc", "open", now, json.dumps(state)))
        did = self.audit.decision(
            now, wf, "incident_detected", f"hallucination flag rate on {cur} is {hit['rate']:.1%} vs {hit['reference_rate']:.1%} reference",
            "CUSUM on flag rate (h=8.5) + binomial confirmation p<=1e-3, >=100 connected", hit, "incident opened",
            f"prompt {cur}: {hit['flagged']}/{hit['connected']} calls flagged ({hit['ratio']}x reference)")
        state["decision"] = did
        self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
        tenant = self.st.one("SELECT tenant FROM workflows WHERE wf=?", (wf,))[0]
        self.audit.notice(now, tenant, wf, "incident",
                          f"Prompt {cur} is producing {hit['ratio']}x the usual rate of flagged (possibly hallucinated) answers "
                          f"({hit['rate']:.1%} vs {hit['reference_rate']:.1%}). We are validating a safer prompt and will ask for "
                          "your approval; we are not changing it without it.")
        self.audit.alert(now, "page", wf, "prompt_hallucination",
                         f"{wf}: prompt {cur} flag rate {hit['rate']:.1%} ({hit['ratio']}x). Controller is validating a fix; "
                         "if no proposal is pending within 30 min check credits and approver cap.")
        row = self.st.one("SELECT id, status, opened_min, state FROM incidents WHERE id=?", (iid,))
        self._advance_incident(wf, spec, now, live, ver, row)

    def _reference_rate(self, wf: str, cur: str, now: int) -> float:
        win = detect.tick_window(self.agg, wf, now - 14 * 1440, now)
        rates = detect.prompt_rates(win)
        bad = set(self.st.get(f"bad_prompts:{wf}", []))  # a prompt we flagged must never define "normal"
        others = [(c, f) for p, (c, f) in rates.items() if p != cur and p not in bad]
        c = sum(x[0] for x in others)
        if c >= 300:
            return max(sum(x[1] for x in others) / c, 0.003)
        # same prompt, but before the last 24h
        old = detect.tick_window(self.agg, wf, now - 14 * 1440, now - 24 * 60)
        r = detect.prompt_rates(old).get(cur)
        if r and r[0] >= 300:
            return max(r[1] / r[0], 0.003)
        pooled = self.st.get("platform_flag_rate", 0.02)
        return max(pooled, 0.003)

    # ---- the phases are persisted so a crash resumes exactly where it stopped
    def _advance_incident(self, wf, spec, now, live, ver, row):
        iid, status, opened, state = row[0], row[1], row[2], json.loads(row[3])
        cur = live["prompt_version"]
        phase = state["phase"]
        gov = spec["governance"]
        # the world moved under us (supervisor changed the prompt again): re-assess from scratch
        if phase in ("proposed", "verifying") and cur not in (state.get("chosen"), state["bad_prompt"]):
            state["phase"] = "closed"
            self.st.x("UPDATE incidents SET status='closed', closed_min=?, state=? WHERE id=?", (now, json.dumps(state), iid))
            self.plans.clear(wf, "prompt")
            self.audit.decision(now, wf, "incident_closed", f"prompt is now {cur}, neither the bad one nor our fix", "world moved",
                                {}, "closed; detectors re-evaluate", "incident closed because the prompt changed again")
            return
        if phase == "detected":
            self._choose_fix(wf, spec, now, live, iid, state, gov)
        elif phase == "proposed":
            if cur == state.get("chosen"):
                state["phase"] = "verifying"
                state["applied_min"] = now
                self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
                self.audit.decision(now, wf, "fix_applied", f"prompt {cur} is live", "live config == chosen fix", {"chosen": cur},
                                    "verifying", f"fix {cur} live {minute_to_str(now)}; time since detection {now - opened} min")
            else:
                self._check_rejections(wf, now, state, iid)
        elif phase == "verifying":
            self._verify_fix(wf, spec, now, iid, state, opened)

    def _spend_ok(self, state, cost):
        rem = self.credits_remaining if self.credits_remaining is not None else 0
        return state["spent"] + cost <= INCIDENT_CREDIT_CAP and rem - cost >= 0 and (rem - cost >= CREDIT_FLOOR or not state.get("spent_any"))

    def _validate(self, wf, now, iid, state, prompt, n=VALID_N):
        if prompt in state["validated"]:
            return state["validated"][prompt]
        cost = math.ceil(n / 100)
        if not self._spend_ok(state, cost):
            self.audit.alert(now, "page", wf, "credits_low", f"cannot validate {prompt}: credits {self.credits_remaining} "
                             f"(incident spent {state['spent']}). Top up credits or approve a manual fix.")
            return None
        try:
            r = self.sim.post("/validation/runs", {"workflow_id": wf, "prompt_version": prompt, "n": n})
        except SimError as e:
            self.audit.alert(now, "page", wf, "validation_failed", f"validation of {prompt} failed: {e}")
            return None
        maybe_crash("after_validation_paid")
        self.credits_remaining = r["credits_remaining"]
        state["spent"] += cost
        state["spent_any"] = True
        rec = {"run_id": r["validation_run_id"], "pass_rate": r["pass_rate"], "failures": r["failures"], "n": n}
        state["validated"][prompt] = rec
        self.st.x("INSERT OR IGNORE INTO validations VALUES(?,?,?,?,?,?,?,?)",
                  (rec["run_id"], wf, prompt, n, r["failures"], r["pass_rate"], now, iid))
        self.st.x("INSERT INTO credits(minute,wf,what,cost,remaining,incident_id) VALUES(?,?,?,?,?,?)",
                  (now, wf, f"validation {prompt} n={n}", cost, r["credits_remaining"], iid))
        self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
        return rec

    def _gate(self, rec, gov) -> bool:
        fail = rec["failures"] / rec["n"]
        return rec["pass_rate"] >= gov["min_validation_pass_rate"] + 0.005 and fail <= FAIL_GATE

    def _lkg(self, wf: str, bad: str) -> list[str]:
        """Prompts this workflow used before, newest first, excluding any we have flagged as bad."""
        rows = self.st.q("SELECT version, config FROM cfg_snapshots WHERE wf=? ORDER BY version DESC", (wf,))
        seen, out = set(self.st.get(f"bad_prompts:{wf}", [])) | {bad}, []
        for _, cfg in rows:
            p = json.loads(cfg)["prompt_version"]
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    def _choose_fix(self, wf, spec, now, live, iid, state, gov):
        bad = state["bad_prompt"]
        cands: list[str] = []
        chosen = None
        for p in self._lkg(wf, bad)[:1]:  # candidate #1: last known-good
            rec = self._validate(wf, now, iid, state, p)
            if rec is None:
                return
            ok = self._gate(rec, gov)
            fail = rec["failures"] / rec["n"]
            self.audit.decision(now, wf, "fix_candidate_validated", f"last known-good {p}", f"gate: fail<={FAIL_GATE:.1%}, pass>=min+0.5pt",
                                {"validation": rec, "min": gov["min_validation_pass_rate"]}, "pass" if ok else "fail",
                                f"{p}: pass_rate {rec['pass_rate']:.4f} on n={rec['n']} ({rec['run_id']})")
            cands.append(p)
            if ok:
                chosen = p
        if chosen is None:
            if not self._spend_ok(state, 3):
                self.audit.alert(now, "page", wf, "credits_low", f"no credits left to ask the LLM for alternatives ({self.credits_remaining})")
                return
            try:
                sug = self.sim.post("/llm/suggest-fixes", {"workflow_id": wf, "problem":
                                    f"Prompt {bad} shows a {state['evidence']['rate']:.1%} hallucination-flag rate "
                                    f"(reference {state['evidence']['reference_rate']:.1%}). Suggest safer prompt versions "
                                    "that keep customers engaged."})
            except SimError as e:
                self.audit.alert(now, "page", wf, "llm_failed", f"LLM suggest-fixes failed: {e}")
                return
            self.credits_remaining = sug.get("credits_remaining", self.credits_remaining)
            state["spent"] += 3
            state["spent_any"] = True
            self.st.x("INSERT INTO credits(minute,wf,what,cost,remaining,incident_id) VALUES(?,?,?,?,?,?)",
                      (now, wf, "llm suggest-fixes", 3, self.credits_remaining, iid))
            names = [s["prompt_version"] for s in sug["suggestions"]]
            self.audit.decision(now, wf, "llm_suggestions", "last known-good unusable", "LLM proposes candidates only; "
                                "validation + deterministic rule decide", {"suggestions": sug["suggestions"]},
                                "validate candidates", f"LLM suggested {names}")
            passing = []
            bads = set(self.st.get(f"bad_prompts:{wf}", []))
            for s in sug["suggestions"]:
                p = s["prompt_version"]
                if p in bads or p == live["prompt_version"]:
                    continue
                rec = self._validate(wf, now, iid, state, p)
                if rec is None:
                    return
                ok = self._gate(rec, gov)
                self.audit.decision(now, wf, "fix_candidate_validated", f"LLM suggestion {p}: {s.get('summary', '')}",
                                    f"gate: fail<={FAIL_GATE:.1%}", {"validation": rec}, "pass" if ok else "fail",
                                    f"{p}: pass_rate {rec['pass_rate']:.4f} ({rec['run_id']})")
                if ok:
                    passing.append((rec["failures"] / rec["n"], p))
            if passing:
                # least restrictive prompt that clears the safety gate: validation is blind to engagement and strict
                # scripts lose callers, so do not over-correct. Deterministic tie-break on name.
                chosen = sorted(passing, key=lambda t: (-t[0], t[1]))[0][1]
        state["candidates"] = cands
        if chosen is None:
            self.audit.alert(now, "page", wf, "no_safe_prompt", f"{wf}: no prompt cleared the safety gate; keep supervisor attention "
                             "on this workflow - the controller will not propose an unvalidated prompt.")
            self.audit.decision(now, wf, "no_safe_fix", "no candidate cleared the gate", "never propose without evidence",
                                state["validated"], "escalated to humans", "no validated prompt available")
            self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
            return
        rec = state["validated"][chosen]
        state["chosen"], state["phase"], state["proposed_min"] = chosen, "proposed", now
        self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
        ev = state["evidence"]
        did = self.audit.decision(
            now, wf, "fix_chosen", f"{chosen} cleared the safety gate", "last-known-good first; else least restrictive passing prompt",
            {"validated": state["validated"], "evidence": ev}, f"plan prompt -> {chosen}",
            f"replace {bad} with {chosen} (validation {rec['run_id']} pass_rate {rec['pass_rate']:.4f}); credits spent {state['spent']}")
        sev = min(1.0, (ev["rate"] - ev["reference_rate"]) / 0.05)
        self.plans.set_prompt(wf, chosen, {
            "kind": "incident_fix", "ref": iid, "urgent": True, "safety": True, "severity": sev, "reach": 1.0, "decision": did,
            "summary": f"replace prompt {bad} with {chosen}: {bad} is producing {ev['ratio']}x the normal rate of flagged answers",
            "rationale": f"{bad} flag rate {ev['rate']:.1%} vs reference {ev['reference_rate']:.1%} over {ev['connected']} calls; "
                         f"{chosen} validated at pass_rate {rec['pass_rate']:.4f}",
            "evidence": {"validation_run_id": rec["run_id"]}, "evidence_text": f"validation {rec['run_id']}",
            "projection": {"metric": "hallucination_flag_rate", "current": ev["rate"], "reference": ev["reference_rate"],
                           "validated_failure_rate": round(rec["failures"] / rec["n"], 4)}})

    def _check_rejections(self, wf, now, state, iid):
        if self.st.get(f"evidence_invalid:{wf}"):
            self.st.put(f"evidence_invalid:{wf}", None)
            state["validated"].pop(state.get("chosen"), None)
            state["phase"] = "detected"
            self.st.x("UPDATE incidents SET state=? WHERE id=?", (json.dumps(state), iid))
            self.plans.clear(wf, "prompt")
            self.audit.decision(now, wf, "evidence_refreshed", "approver rejected the validation evidence", "re-validate",
                                {}, "restart fix selection", "validation evidence rejected; re-validating")

    def _verify_fix(self, wf, spec, now, iid, state, opened):
        applied = state.get("applied_min", now)
        if now - applied < 90:
            return
        chosen = state["chosen"]
        win = detect.tick_window(self.agg, wf, applied, now)
        rates = detect.prompt_rates(win).get(chosen)
        if not rates or rates[0] < 150:
            return
        ref = self._reference_rate(wf, chosen, now)
        flag_rate = rates[1] / rates[0]
        # engagement canary: new prompt vs the pre-incident prompt (same detector window logic, separate KPI)
        pre = detect.tick_window(self.agg, wf, state.get("opened_min", opened) - 3 * 1440, opened)
        eng_new = sum(v[2] for (d, p), v in win.items() if p == chosen)
        conn_new = sum(v[1] for (d, p), v in win.items() if p == chosen)
        base_p = state["bad_prompt"]
        old = [(k, v) for k, v in pre.items() if k[1] != chosen and k[1] != base_p]
        e_old, c_old = sum(v[2] for _, v in old), sum(v[1] for _, v in old)
        diff, z = two_prop(eng_new, conn_new, e_old, c_old) if c_old >= 300 and conn_new >= 150 else (0.0, 0.0)
        ok_flags = flag_rate <= max(2 * ref, ref + 0.015)
        ok_eng = not (z <= -2.5 and diff <= -0.03)
        res = {"flag_rate": round(flag_rate, 4), "reference": round(ref, 4), "connected": rates[0], "engagement_new": round(eng_new / conn_new, 4),
               "engagement_before": round(e_old / c_old, 4) if c_old else None, "engagement_z": round(z, 2)}
        state["phase"] = "closed" if (ok_flags and ok_eng) else "failed"
        self.st.x("UPDATE incidents SET status=?, closed_min=?, state=? WHERE id=?",
                  ("closed" if state["phase"] == "closed" else "failed", now, json.dumps(state), iid))
        mttr = applied - opened
        self.audit.decision(now, wf, "fix_verified" if state["phase"] == "closed" else "fix_failed",
                            f"post-apply check of {chosen}", "flag rate <= max(2x ref, ref+1.5pt) and engagement not significantly lower",
                            res, "incident closed" if state["phase"] == "closed" else "escalated",
                            f"{chosen}: flag rate {flag_rate:.1%} (ref {ref:.1%}); applied {mttr} min after detection")
        self.audit.resolve_alert(now, wf, "prompt_hallucination")
        if state["phase"] == "failed":
            self.audit.alert(now, "page", wf, "fix_not_effective",
                             f"{wf}: prompt {chosen} did not restore health ({res}). Review incident {iid}; engagement canary or flags failed.")
