"""Governance client (C9): the ONLY component that changes a workflow's config, and only via /approvals or a
policy-permitted auto-apply. Planners edit the *plan*; this executor diffs plan vs live config.

Proposal state machine (local mirror of the simulator's lifecycle, persisted in SQLite):

   intent --POST--> pending --approver--> approved --apply--> applied
      |                |  \\                  |  \\
      |                |   +--> rejected     |   +--> lapsed   (apply window missed -> re-plan with fresh data)
      |                +------> expired      +------> stale    (config moved: supervisor edit / our own auto-apply)
      +--> failed (422/403)                  superseded (an urgent change replaced it)

Crash safety: the `intent` row (with a deterministic proposal_id) is written BEFORE the HTTP call. After a restart
the same id is re-sent: 409 duplicate_proposal_id means "it already happened", and we link it by listing
/approvals (or /config/history for auto-apply). Nothing is ever applied twice, no pending approval is forgotten.
"""
from __future__ import annotations

import copy
import json
import logging
import math

import yaml

from . import cfgutil
from .audit import Audit
from .plan import PlanStore, dim_of, target_config
from .simclient import Sim, SimError
from .store import Store
from .util import maybe_crash, minute_to_str, short_hash

log = logging.getLogger("controller.gov")

CUSTOMER_FACING = ("welcome_message", "voice", "prompt_version")
INITIAL_AUTONOMY = {"schedule": 1, "caller_id": 1, "cohorts": 1, "welcome_message": 0, "voice": 0, "prompt_version": 0}
BACKOFF_MIN = [0, 180, 1440, 2880]  # re-propose delay after the n-th failed attempt of the same content
BACKOFF_URGENT = [0, 30, 120, 240]
STEP_COOLDOWN_MIN = 30              # between consecutive bounded auto-apply steps
IN_FLIGHT = ("intent", "pending", "approved")


class Prefs:
    """Stakeholder preferences that are *not* part of the simulator contract (memos), kept out of the logic."""

    def __init__(self, path: str | None):
        self.d = {"defaults": {}, "tenants": {}}
        if path:
            try:
                self.d = yaml.safe_load(open(path)) or self.d
            except FileNotFoundError:
                log.warning("prefs file %s not found; using contract defaults", path)

    def get(self, tenant: str, key: str, default=None):
        t = (self.d.get("tenants") or {}).get(tenant, {})
        if key in t:
            return t[key]
        return (self.d.get("defaults") or {}).get(key, default)


def next_working(t: int, hours: list[int]) -> int:
    lo, hi = hours
    day, mod = divmod(t, 1440)
    if mod < lo * 60:
        return day * 1440 + lo * 60
    if mod >= hi * 60:
        return (day + 1) * 1440 + lo * 60
    return t


class Governance:
    def __init__(self, st: Store, sim: Sim, audit: Audit, plans: PlanStore, prefs: Prefs, agg):
        self.st, self.sim, self.audit, self.plans, self.prefs, self.agg = st, sim, audit, plans, prefs, agg
        self.counters = {"proposals": 0, "auto_applies": 0, "applies": 0, "conflicts": 0, "retries": 0}

    # =================================================================== autonomy
    def autonomy(self, wf: str, dim: str) -> int:
        r = self.st.one("SELECT level FROM autonomy WHERE wf=? AND dim=?", (wf, dim))
        return r[0] if r else INITIAL_AUTONOMY.get(dim, 0)

    def grant(self, now: int, wf: str, dim: str, reason: str):
        self.st.x("INSERT INTO autonomy(wf,dim,level,since_min,reason) VALUES(?,?,1,?,?) ON CONFLICT(wf,dim) DO UPDATE SET "
                  "level=1, since_min=excluded.since_min, reason=excluded.reason", (wf, dim, now, reason))
        self.audit.decision(now, wf, "autonomy_granted", f"{dim}: {reason}", "earned-autonomy ladder", {},
                            "level 1 (auto-apply within policy)", f"{dim} may now be auto-applied (bounded by policy)")

    # =================================================================== proposals bookkeeping
    def _rows(self, wf: str, statuses: tuple) -> list[dict]:
        q = ",".join("?" * len(statuses))
        cols = ("proposal_id", "route", "kind", "status", "urgent", "base_version", "approval_id", "created_min",
                "submitted_min", "decided_min", "expires_min", "apply_by_min", "applied_version", "dims",
                "attempt_key", "attempt", "payload", "reasons", "impact")
        return [dict(zip(cols, r)) for r in self.st.q(
            f"SELECT {','.join(cols)} FROM proposals WHERE wf=? AND status IN ({q}) ORDER BY created_min", (wf, *statuses))]

    def _set(self, pid: str, now: int, **kw):
        sets = ",".join(f"{k}=?" for k in kw)
        self.st.x(f"UPDATE proposals SET {sets}, updated_min=? WHERE proposal_id=?", (*kw.values(), now, pid))

    def _requests_24h(self, wf: str, now: int) -> int:
        r = self.st.one("SELECT COUNT(*) FROM proposals WHERE wf=? AND route='approval' AND created_min>?",
                        (wf, now - 1440))
        return r[0]

    # =================================================================== the per-workflow cycle
    def reconcile(self, wf: str, spec: dict, now: int):
        """FIRST thing every cycle, before any planner runs: finish what was in flight (re-send write-ahead intents, poll
        approvals, apply what was approved). Doing this before planning is what makes a restarted cycle replay exactly
        like an uninterrupted one."""
        live = self.sim.get(f"/workflows/{wf}/config")
        self._reconcile(wf, spec, now, live["version"], live["config"])

    def cycle(self, wf: str, spec: dict, now: int, end_min: int):
        live = self.sim.get(f"/workflows/{wf}/config")
        ver, cfg = live["version"], live["config"]
        plan = self.plans.get(wf)
        target = target_config(cfg, plan)
        dims = cfgutil.changed_dims(cfg, target)
        inflight = self._rows(wf, IN_FLIGHT)
        if not dims:
            for p in inflight:
                if p["route"] == "approval" and p["status"] in ("pending", "intent"):
                    pass  # let it resolve; nothing new to add
            return
        thash = short_hash(target)
        urgent_dims = [d for d in dims if self._urgent(plan, d)]
        gov = spec["governance"]
        # --- An approval already in flight pins the base version: ANY other change (even our own auto-apply) would make
        #     it stale. So while one is in flight we only ever wait - unless a safety change must pre-empt a routine one.
        for p in inflight:
            if p["route"] != "approval":
                continue
            if p["base_version"] != ver:
                self._set(p["proposal_id"], now, status="stale")
                self.counters["conflicts"] += 1
                self.audit.decision(now, wf, "proposal_stale", f"config moved v{p['base_version']}->v{ver} while "
                                    f"{p['proposal_id']} was {p['status']}", "base_version must equal live version",
                                    {"live_version": ver}, "marked stale; will re-plan from fresh base",
                                    "proposal can no longer be applied (stale base)", proposal_id=p["proposal_id"])
                continue
            if p["attempt_key"] == thash:
                return  # waiting for the approver
            if urgent_dims and not json.loads(p["payload"]).get("urgent_dims"):
                self._set(p["proposal_id"], now, status="superseded")
                self.audit.decision(now, wf, "proposal_superseded", f"urgent change {urgent_dims} while "
                                    f"{p['proposal_id']} pending", "safety actions pre-empt routine ones",
                                    {"urgent_dims": urgent_dims}, "old proposal withdrawn locally",
                                    "pending routine proposal replaced by an urgent one", proposal_id=p["proposal_id"])
            else:
                return  # finish the pending request first, then re-plan from the fresh base
        # --- choose route. Safety changes that need a human go first (an auto-step would stale the request).
        pol = gov["auto_apply"]
        auto_dims, appr_dims = [], []
        for d in dims:
            ok = (pol.get("enabled") and d in pol.get("allowed_dims", []) and d != "prompt_version")
            if ok and d in ("welcome_message", "voice") and self.autonomy(wf, d) < 1 and not self._safety(plan, d):
                ok = False  # autonomy not yet earned for customer-facing dims: ask a human first
            if ok and d in ("cohorts",) and self.autonomy(wf, d) < 1:
                ok = False
            (auto_dims if ok else appr_dims).append(d)
        urgent_appr = [d for d in appr_dims if d in urgent_dims]
        if urgent_appr:
            self._maybe_propose(wf, spec, now, ver, cfg, target, appr_dims, plan, urgent_dims, thash)
        elif auto_dims:
            self._auto_step(wf, spec, now, ver, cfg, target, auto_dims, plan, pol)
        elif appr_dims:
            self._maybe_propose(wf, spec, now, ver, cfg, target, appr_dims, plan, urgent_dims, thash)

    # ------------------------------------------------------------------ helpers over the plan
    @staticmethod
    def _keys_for(plan: dict, dim: str) -> list[str]:
        return [k for k in plan["why"] if dim_of(k) == dim]

    def _urgent(self, plan: dict, dim: str) -> bool:
        return any(plan["why"][k].get("urgent") for k in self._keys_for(plan, dim))

    def _safety(self, plan: dict, dim: str) -> bool:
        return any(plan["why"][k].get("safety") for k in self._keys_for(plan, dim))

    # =================================================================== auto-apply (bounded steps)
    def _partial(self, live: dict, target: dict, dims: list[str]) -> dict:
        cfg = copy.deepcopy(live)
        if "cohorts" in dims:
            cfg["cohorts"] = copy.deepcopy(target["cohorts"])
        keys = {"default"} | set(target["allocations"]) | set(live["allocations"])
        for d in cfgutil.AGENT_DIMS:
            if d in dims:
                for k in keys:
                    if k in target["allocations"] and d in target["allocations"][k]:
                        cfg["allocations"].setdefault(k, {})[d] = copy.deepcopy(target["allocations"][k][d])
                    elif k != "default" and k in cfg["allocations"]:
                        cfg["allocations"][k].pop(d, None)
        if "prompt_version" in dims:
            cfg["prompt_version"] = target["prompt_version"]
        if "schedule" in dims:
            cfg["schedule"] = copy.deepcopy(target["schedule"])
        return cfgutil.clean(cfg)

    def _auto_step(self, wf, spec, now, ver, live, target, auto_dims, plan, pol):
        urgent = [d for d in auto_dims if self._urgent(plan, d)]
        dims = urgent or auto_dims
        # cooldown is derived from the proposals table (not from a side-effect we might lose in a crash window)
        last = (self.st.one("SELECT MAX(decided_min) FROM proposals WHERE wf=? AND route='auto' AND status='applied'", (wf,)) or [None])[0]
        last = -10 ** 9 if last is None else last
        if now - last < (STEP_COOLDOWN_MIN if urgent else 60):
            return
        part = self._partial(live, target, dims)
        cap = float(pol.get("max_shift", 0))
        stepped = cfgutil.step_toward(live, part, cap) if cap > 0 else part
        if cfgutil.max_shift(live, stepped) > cap + 1e-9:
            stepped = part  # (only reachable when cap == 0 and an allocation changes: policy will reject, we log it)
        sdims = cfgutil.changed_dims(live, stepped)
        if not sdims:
            return
        # pre-announce for tenants that asked to be told before a running campaign changes
        notice = self.prefs.get(spec["tenant_id"], "notice_minutes", 0) if not urgent else 0
        whys = [plan["why"][k] for d in sdims for k in self._keys_for(plan, d)]
        summary = self._summary(whys, sdims)
        if notice and any(d in CUSTOMER_FACING for d in sdims):
            ak = f"{wf}:{short_hash(stepped)}"
            r = self.st.one("SELECT effective_min FROM notices WHERE wf=? AND kind='pre-announce' AND text LIKE ?",
                            (wf, f"%[{ak}]%"))
            if not r:
                self.audit.notice(now, spec["tenant_id"], wf, "pre-announce", f"[{ak}] Planned (auto) change: {summary}",
                                  now + notice)
                return
            if now < r[0]:
                return
        pid = f"{wf}-auto-v{ver}-{short_hash(stepped)}"
        row = self.st.one("SELECT status FROM proposals WHERE proposal_id=?", (pid,))
        if row and row[0] in ("applied", "failed"):
            return
        if not row:
            self.st.x("INSERT INTO proposals(proposal_id,wf,route,kind,status,urgent,base_version,created_min,dims,"
                      "attempt_key,attempt,payload,impact,updated_min) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, wf, "auto", ",".join(sorted({w.get('kind', '?') for w in whys})), "intent",
                       1 if urgent else 0, ver, now, json.dumps(sdims), short_hash(target), 0,
                       json.dumps({"config": stepped, "whys": whys, "summary": summary}), None, now))
        maybe_crash("after_intent_before_post")
        rationale = self._rationale(whys)
        evidence = {"decision_ids": [w.get("decision") for w in whys], "dims": sdims}
        try:
            res = self.sim.put(f"/workflows/{wf}/config", {"proposal_id": pid, "base_version": ver,
                                                         "proposed_config": stepped, "rationale": rationale,
                                                         "evidence": evidence})
            maybe_crash("after_post_before_commit")
            self._record_auto(wf, spec["tenant_id"], pid, now, res["version"], whys, sdims, cap, ver, summary)
        except SimError as e:
            self._handle_put_error(wf, pid, now, ver, e)

    def _record_auto(self, wf, tenant, pid, now, version, whys, sdims, cap, ver, summary, recovered=False):
        """Everything that must be true once an auto-apply happened, in ONE transaction (also used by crash recovery)."""
        with self.st.tx():
            self._set(pid, now, status="applied", applied_version=version, decided_min=now)
            if not self.st.one("SELECT 1 FROM decisions WHERE proposal_id=? AND kind='auto_applied'", (pid,)):
                self.audit.decision(now, wf, "auto_applied", whys[0].get("summary", "plan change") if whys else "plan change",
                                    f"policy.auto_apply allows {sdims}; shift<={cap}" + (" [recorded after restart]" if recovered else ""),
                                    {"whys": whys, "from": ver}, f"applied v{version}", summary, proposal_id=pid, version=version,
                                    parent_id=whys[0].get("decision") if whys else None)
                self.audit.notice(now, tenant, wf, "applied", f"v{version}: {summary}")
        self.counters["auto_applies"] += 1

    def _handle_put_error(self, wf, pid, now, ver, e: SimError):
        if e.code == "duplicate_proposal_id":  # an earlier attempt (before a crash) succeeded
            hist = self.sim.get(f"/workflows/{wf}/config/history")
            hit = next((h for h in hist if h["proposal_id"] == pid), None)
            if hit:
                row = self.st.one("SELECT payload, dims, base_version FROM proposals WHERE proposal_id=?", (pid,))
                payload = json.loads(row[0]) if row else {}
                tenant = self.st.one("SELECT tenant FROM workflows WHERE wf=?", (wf,))[0]
                self.audit.decision(now, wf, "recovered", f"auto-apply {pid} had already happened before a restart",
                                    "idempotent reconciliation", {"history_hit": hit}, f"linked to v{hit['version']}",
                                    "no double-apply: matched proposal_id in config history", proposal_id=pid)
                self._record_auto(wf, tenant, pid, now, hit["version"], payload.get("whys", []), json.loads(row[1]) if row else [],
                                  0, row[2] if row else ver, payload.get("summary", ""), recovered=True)
                return
        if e.code == "stale_base_version":
            self._set(pid, now, status="stale")
            self.counters["conflicts"] += 1
            return
        self._set(pid, now, status="failed", reasons=json.dumps([e.code, e.detail], default=str))
        self.audit.alert(now, "ticket", wf, "auto_apply_refused",
                         f"auto-apply refused ({e.code}): {e.detail}. Look at plan.why for this workflow.")
        self.audit.decision(now, wf, "auto_apply_refused", f"{e.code}", "simulator policy check", {"detail": e.detail},
                            "falling back to the approval path", str(e.detail), proposal_id=pid)

    # =================================================================== approval path
    def _slot_ok(self, now: int, spec: dict, urgent: bool) -> tuple[bool, str]:
        gov = spec["governance"]
        lo, hi = gov["approver_hours"]
        lat_lo, lat_hi = gov["approver_latency_minutes"]
        ttl = gov["proposal_ttl_hours"] * 60
        hour = (now % 1440) / 60
        decide_worst = next_working(now + lat_hi, [lo, hi])
        if urgent:
            return True, "urgent: sent immediately (a safety fix must not wait for a nicer time slot)"
        earliest = max(lo, self.prefs.get(spec["tenant_id"], "earliest_send_hour", lo))
        if not (earliest <= hour < hi):
            return False, f"outside approver hours [{earliest},{hi})"
        if decide_worst - now > ttl - 15:
            return False, "worst-case decision would land after expiry"
        same_day = decide_worst <= (now // 1440) * 1440 + hi * 60
        first_hour = hour < earliest + 1
        if not (same_day or first_hour):
            return False, "too late today for a same-day decision; wait for the next morning slot"
        return True, "inside approver hours with a same-day decision guaranteed"

    def _cap_ok(self, wf: str, spec: dict, now: int, urgent: bool) -> tuple[bool, str]:
        gov = spec["governance"]
        cap = gov["max_requests_per_24h"]
        used = self._requests_24h(wf, now)
        if urgent:
            return used < cap, f"{used}/{cap} requests in 24h"
        reserve = 1 if cap >= 2 else 0
        pref = self.prefs.get(spec["tenant_id"], "max_requests_per_day", None)
        limit = min(cap - reserve, pref if pref is not None else cap)
        return used < limit, f"{used}/{limit} routine requests in 24h (policy cap {cap}, 1 reserved for safety)"

    def _maybe_propose(self, wf, spec, now, ver, live, target, dims, plan, urgent_dims, thash):
        urgent = bool([d for d in dims if d in urgent_dims])
        use_dims = [d for d in dims if d in urgent_dims] if urgent else dims
        partial = self._partial(live, target, use_dims) if urgent else target
        pkey = short_hash(partial)
        # backoff after failed attempts at the same content
        done = self.st.q("SELECT status, updated_min FROM proposals WHERE wf=? AND attempt_key=? AND route='approval' "
                         "AND status IN ('rejected','expired','lapsed','failed') ORDER BY updated_min", (wf, pkey))
        attempt = len(done)
        bo = BACKOFF_URGENT if urgent else BACKOFF_MIN
        if done and now < done[-1][1] + bo[min(attempt, len(bo) - 1)]:
            return
        if attempt >= 4:
            self.audit.alert(now, "ticket", wf, "proposal_repeatedly_unapproved",
                             f"{attempt} attempts at the same change were not approved ({[d[0] for d in done]}). "
                             "Review audit decisions for this workflow; the controller will keep retrying daily.")
        ok, why_slot = self._slot_ok(now, spec, urgent)
        if not ok:
            return
        ok, why_cap = self._cap_ok(wf, spec, now, urgent)
        if not ok:
            self.audit.decision(now, wf, "proposal_deferred", f"{why_cap}", "approver-fatigue budget", {"dims": dims},
                                "deferred", f"not sending: {why_cap}") if now % 120 == 0 else None
            return
        whys = [plan["why"][k] for d in use_dims for k in self._keys_for(plan, d)]
        pid = f"{wf}-v{ver}-{pkey}-a{attempt}"
        built = self._build(wf, spec, now, ver, live, partial, use_dims, whys, urgent)
        if built is None:
            return
        body, meta = built
        body["proposal_id"] = pid
        if self.st.one("SELECT 1 FROM proposals WHERE proposal_id=?", (pid,)) is None:
            self.st.x("INSERT INTO proposals(proposal_id,wf,route,kind,status,urgent,base_version,created_min,dims,"
                      "attempt_key,attempt,payload,impact,updated_min) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (pid, wf, "approval", ",".join(sorted({w.get('kind', '?') for w in whys})), "intent",
                       1 if urgent else 0, ver, now, json.dumps(use_dims), pkey, attempt,
                       json.dumps({**meta, "body": body, "urgent_dims": use_dims if urgent else []}, default=str),
                       body["impact_score"], now))
        maybe_crash("after_intent_before_post")
        self._submit(pid, now)

    def _submit(self, pid: str, now: int):
        r = self.st.one("SELECT wf, payload FROM proposals WHERE proposal_id=?", (pid,))
        wf, payload = r[0], json.loads(r[1])
        body = payload["body"]
        try:
            res = self.sim.post("/approvals", body)
        except SimError as e:
            if e.code == "duplicate_proposal_id":
                res = next((a for a in self.sim.get("/approvals", params={"workflow_id": wf})
                            if a["proposal_id"] == pid), None)
                if res:
                    self.audit.decision(now, wf, "recovered", f"{pid} was already submitted before a restart",
                                        "idempotent reconciliation", {"approval": res["approval_id"]},
                                        f"linked {res['approval_id']}", "no duplicate request sent", proposal_id=pid)
                else:
                    self._set(pid, now, status="failed", reasons=json.dumps([e.code]))
                    return
            elif e.code in ("stale_base_version",):
                self._set(pid, now, status="stale")
                self.counters["conflicts"] += 1
                return
            else:
                self._set(pid, now, status="failed", reasons=json.dumps([e.code, e.detail], default=str))
                self.audit.alert(now, "page" if e.code in ("missing_fields", "invalid_config") else "ticket", wf,
                                 f"proposal_{e.code}", f"{pid} refused by the simulator ({e.code}): {e.detail}")
                return
        maybe_crash("after_post_before_commit")
        spec_whys = payload.get("whys", [])
        with self.st.tx():
            self._set(pid, now, status="pending", approval_id=res["approval_id"], submitted_min=now,
                      expires_min=_parse_min(res["expires_at"]))
            if not self.st.one("SELECT 1 FROM decisions WHERE proposal_id=? AND kind='proposal_submitted'", (pid,)):
                self.audit.decision(
                    now, wf, "proposal_submitted", payload.get("summary", ""), f"governance batch ({payload.get('slot_reason')})",
                    {"impact_score": body["impact_score"], "affected_leads": body["affected_leads"], "diff": body["diff"],
                     "dry_run": body["dry_run"], "cap": payload.get("cap_reason"), "urgent": bool(payload.get("urgent_dims"))},
                    f"{res['approval_id']} pending", body["change_summary"], proposal_id=pid, version=body["base_version"],
                    parent_id=spec_whys[0].get("decision") if spec_whys else None)
        self.counters["proposals"] += 1

    # =================================================================== reconcile in-flight proposals
    def _reconcile(self, wf: str, spec: dict, now: int, ver: int, live: dict):
        for p in self._rows(wf, ("intent",)):
            if p["route"] == "approval":
                self._submit(p["proposal_id"], now)
            else:
                payload = json.loads(p["payload"])
                self._retry_auto(wf, p, payload, now, ver)
        for p in self._rows(wf, ("pending", "approved")):
            if p["route"] != "approval" or not p["approval_id"]:
                continue
            try:
                a = self.sim.get(f"/approvals/{p['approval_id']}")
            except SimError:
                continue
            st = a["status"]
            if st == "pending":
                continue
            if st == "approved":
                if p["status"] != "approved":
                    self._set(p["proposal_id"], now, status="approved", decided_min=_parse_min(a.get("decided_at")),
                              apply_by_min=_parse_min(a.get("apply_by")))
                    self.audit.decision(now, wf, "approval_seen", f"{a['approval_id']} approved", "poll /approvals",
                                        {"decided_at": a.get("decided_at"), "apply_by": a.get("apply_by")}, "apply now",
                                        "approver said yes; applying immediately (apply window is short)",
                                        proposal_id=p["proposal_id"])
                self._apply(wf, p, a, now, ver)
            elif st in ("rejected", "expired", "lapsed"):
                reasons = a.get("reasons") or []
                self._set(p["proposal_id"], now, status=st, reasons=json.dumps(reasons),
                          decided_min=_parse_min(a.get("decided_at")) or now)
                self.audit.decision(now, wf, f"proposal_{st}", f"{a['approval_id']} {st}", "poll /approvals",
                                    {"reasons": reasons}, "re-plan with fresh data" if st != "rejected" else
                                    "classified, backoff then re-propose", f"{st}: {reasons}", proposal_id=p["proposal_id"])
                if st == "rejected":
                    self._classify_rejection(wf, p, reasons, now)
            elif st == "applied":  # we applied it but died before recording it (crash window): record it now
                self._finish_apply(wf, p, a["approval_id"], now, None, recovered=True)
        # approvals that were approved while we were not looking and the window lapsed are caught by the 410 path

    def _retry_auto(self, wf, p, payload, now, ver):
        try:
            res = self.sim.put(f"/workflows/{wf}/config", {"proposal_id": p["proposal_id"], "base_version": p["base_version"],
                                                              "proposed_config": payload["config"],
                                                              "rationale": self._rationale(payload["whys"]),
                                                              "evidence": {"dims": json.loads(p["dims"])}})
            tenant = self.st.one("SELECT tenant FROM workflows WHERE wf=?", (wf,))[0]
            self._record_auto(wf, tenant, p["proposal_id"], now, res["version"], payload.get("whys", []), json.loads(p["dims"]),
                              0, p["base_version"], payload.get("summary", ""), recovered=True)
        except SimError as e:
            self._handle_put_error(wf, p["proposal_id"], now, p["base_version"], e)

    def _apply(self, wf, p, a, now, ver):
        pid, aid = p["proposal_id"], p["approval_id"]
        if p["base_version"] != ver:
            self._set(pid, now, status="stale")
            self.counters["conflicts"] += 1
            self.audit.decision(now, wf, "proposal_stale", f"{aid} approved but config is now v{ver}", "base_version check",
                                {"base": p["base_version"], "live": ver}, "not applied; will re-propose from fresh base",
                                "approved change can no longer be applied", proposal_id=pid)
            return
        maybe_crash("before_apply")
        try:
            res = self.sim.post(f"/workflows/{wf}/apply", {"approval_id": aid})
        except SimError as e:
            if e.code == "approval_lapsed":
                self._set(pid, now, status="lapsed")
                self.audit.decision(now, wf, "proposal_lapsed", f"{aid} apply window missed", "apply_by deadline",
                                    {}, "re-plan", "approved but not applied in time", proposal_id=pid)
                self.audit.alert(now, "ticket", wf, "approval_lapsed", f"{aid} lapsed before apply; investigate loop lag")
            elif e.code == "stale_base_version":
                self._set(pid, now, status="stale")
                self.counters["conflicts"] += 1
            elif e.code == "not_approved":
                st = self.sim.get(f"/approvals/{aid}")["status"]
                if st == "applied":
                    self._set(pid, now, status="applied", applied_version=ver)
            return
        maybe_crash("after_apply_before_record")
        self._finish_apply(wf, p, aid, now, res["version"])

    def _finish_apply(self, wf, p, aid, now, version, recovered=False):
        pid = p["proposal_id"]
        if version is None:  # find which version this approval produced
            hit = next((h for h in self.sim.get(f"/workflows/{wf}/config/history") if h.get("approval_id") == aid), None)
            version = hit["version"] if hit else None
        payload = json.loads(p["payload"])
        tenant = self.st.one("SELECT tenant FROM workflows WHERE wf=?", (wf,))[0]
        with self.st.tx():
            self._set(pid, now, status="applied", applied_version=version)
            if not self.st.one("SELECT 1 FROM decisions WHERE proposal_id=? AND kind='applied'", (pid,)):
                self.audit.decision(now, wf, "applied", payload.get("summary", ""),
                                    "approved by client approver" + (" [recorded after restart]" if recovered else ""),
                                    {"approval_id": aid}, f"applied v{version}", payload.get("summary", ""),
                                    proposal_id=pid, version=version)
                self.audit.notice(now, tenant, wf, "applied", f"v{version}: {payload.get('summary', '')}")
        self.counters["applies"] += 1

    def _classify_rejection(self, wf, p, reasons, now):
        text = " ".join(reasons).lower()
        if "validation" in text or "prompt changes need" in text:
            self.st.put(f"evidence_invalid:{wf}", now)
        if "fatigue" in text:
            self.audit.alert(now, "ticket", wf, "approver_fatigue", "request cap hit; batching budget too loose")
        if "must all be non-empty" in text or "affected_leads" in text or "impact_score" in text:
            self.audit.alert(now, "page", wf, "malformed_proposal",
                             f"approver rejected the proposal structure: {reasons}. Controller bug in governance._build.")

    # =================================================================== build the proposal (C10)
    def _summary(self, whys: list[dict], dims: list[str]) -> str:
        parts = []
        for w in whys:
            s = w.get("summary")
            if s and s not in parts:
                parts.append(s)
        return ("; ".join(parts) or f"update {', '.join(dims)}")[:400]

    def _rationale(self, whys: list[dict]) -> str:
        parts = []
        for w in whys:
            t = w.get("rationale") or w.get("summary") or ""
            ev = w.get("evidence_text")
            parts.append(f"{t} [{ev}]" if ev else t)
        return " | ".join(p for p in parts if p)[:1200] or "controller plan change"

    def _active_leads(self, wf: str, spec: dict, now: int, share: float) -> int:
        days = self.agg.wf("agg_day", wf)
        d_now = now // 1440
        window = len(spec["cadence"])
        up = sum(v[0] for (d,), v in days.items() if d_now - window < d <= d_now)
        done = sum(v[3] for (d,), v in days.items() if d_now - window < d <= d_now)
        return max(0, int(round((up - done) * share)))

    def _build(self, wf, spec, now, ver, live, target, dims, whys, urgent):
        cohort_share = self._reach(wf, whys, target)
        agent_facing = [d for d in dims if d in cfgutil.AGENT_DIMS or d == "cohorts"]
        if spec["mid_flight"] == "next_campaign_only" and agent_facing and not any(d in ("schedule", "prompt_version") for d in dims):
            affected = int(round(spec["daily_batch"]["size"] * cohort_share))
            basis = "next campaign only (agent-facing parts are locked per campaign: mid_flight=next_campaign_only)"
        else:
            affected = self._active_leads(wf, spec, now, cohort_share)
            basis = "estimated leads still inside their cadence window in the affected cohorts"
        impact, impact_note = self._impact(whys, cohort_share)
        diff = self._diff(live, target, dims)
        gov = spec["governance"]
        summary = self._summary(whys, dims)
        dry = {"method": "stratified projection from randomised per-arm rates observed in this workflow "
                         "(not a counterfactual replay: the sim cannot re-dial history)",
               "projections": [w.get("projection") for w in whys if w.get("projection")] or
                              [{"note": "exposure-only change: no KPI change is claimed",
                                "exposure": [w.get("alloc") for w in whys if w.get("alloc")]}],
               "guardrail": spec["objective"].get("guardrail"),
               "affected_basis": basis, "impact_formula": impact_note}
        body = {"workflow_id": wf, "base_version": ver, "proposed_config": target,
                "change_summary": summary[:300], "diff": diff, "affected_leads": int(affected), "dry_run": dry,
                "impact_score": impact, "rationale": self._rationale(whys),
                "expires_in_hours": gov["proposal_ttl_hours"]}
        ev = next((w.get("evidence") for w in whys if w.get("evidence")), None)
        if "prompt_version" in dims:
            if not ev or not ev.get("validation_run_id"):
                return None  # cannot propose a prompt change without validation evidence
            body["evidence"] = ev
        else:
            body["evidence"] = {"decision_ids": [w.get("decision") for w in whys]}
        _, slot = self._slot_ok(now, spec, urgent)
        _, cap = self._cap_ok(wf, spec, now, urgent)
        return body, {"summary": summary, "whys": whys, "slot_reason": slot, "cap_reason": cap}

    def _reach(self, wf: str, whys: list[dict], target: dict) -> float:
        r = [w.get("reach", 1.0) for w in whys if w.get("reach") is not None]
        return float(max(r)) if r else 1.0

    def _impact(self, whys, reach) -> tuple[float, str]:
        """impact in [0,1]: share of traffic affected x conservative (lower-bound) relative lift on the primary KPI,
        10% lift on 100% of traffic = 1.0. Safety fixes score by severity. Exploration scores by exposure x 0.1."""
        best = 0.0
        for w in whys:
            if w.get("safety"):
                sev = float(w.get("severity", 0.5))
                v = 0.6 + 0.4 * min(1.0, sev)
            elif w.get("exploration"):
                v = 0.10 * float(w.get("reach", 1.0))
            else:
                lift = w.get("lift_rel_lcb")
                v = float(w.get("reach", 1.0)) * max(0.0, lift or 0.0) / 0.10
            best = max(best, v)
        best = round(min(1.0, best), 3)
        return best, ("max over bundled changes of: safety 0.6+0.4*severity | exploration 0.1*reach | "
                      "reach*max(0,LCB relative lift)/0.10; clipped to [0,1]")

    def _diff(self, live: dict, target: dict, dims: list[str]) -> dict:
        d: dict = {"dims": dims}
        for dim in cfgutil.AGENT_DIMS:
            if dim in dims:
                keys = {"default"} | set(cfgutil.cohort_ids(live)) | set(cfgutil.cohort_ids(target))
                d[dim] = {k: {"from": cfgutil.dist(live, k, dim) if k in live["allocations"] or k == "default" else "inherits default",
                              "to": cfgutil.dist(target, k, dim)}
                          for k in sorted(keys) if cfgutil.tv(cfgutil.dist(live, k, dim), cfgutil.dist(target, k, dim)) > 1e-9}
        if "cohorts" in dims:
            d["cohorts"] = {"from": cfgutil.cohort_ids(live), "to": cfgutil.cohort_ids(target)}
        if "prompt_version" in dims:
            d["prompt_version"] = {"from": live["prompt_version"], "to": target["prompt_version"]}
        if "schedule" in dims:
            d["schedule"] = {"hour_weights_cohorts_from": sorted(live["schedule"]["hour_weights"]),
                             "hour_weights_cohorts_to": sorted(target["schedule"]["hour_weights"]),
                             "table": target["schedule"]["hour_weights"]}
        return d


def _parse_min(ts: str | None) -> int | None:
    if not ts:
        return None
    from .util import ts_to_minute
    return ts_to_minute(ts)
