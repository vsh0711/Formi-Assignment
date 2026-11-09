"""The controller service: a single always-on loop.  ingest -> detect -> plan -> govern -> advance.

  python -m controller.main --url http://127.0.0.1:8700 --db state/controller.db

Every iteration is idempotent and re-derives what to do from persisted state + the simulator's own records, so the
process can be killed at any instruction and restarted: it resumes from the chunk cursor, re-sends write-ahead
proposals under their deterministic ids, and reconciles pending approvals before planning anything new.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time

from . import cohorts
from .audit import Audit
from .experiments import Experiments
from .governance import Governance, Prefs
from .incident import Incidents
from .ingest import Ingestor
from .plan import PlanStore
from .schedule import Scheduler
from .simclient import Sim, SimError, SimUnavailable
from .store import Store
from .util import maybe_crash, minute_to_str

log = logging.getLogger("controller")
HOLD_DAYS = 3
STEP = 15


class Controller:
    def __init__(self, url: str, db: str, prefs_path: str | None = None, status_port: int | None = None):
        self.sim = Sim(url)
        self.st = Store(db)
        self.audit = Audit(self.st)
        self.plans = PlanStore(self.st)
        self.prefs = Prefs(prefs_path)
        self.ing = Ingestor(self.st, self.sim)
        self.exps = Experiments(self.st, self.ing.agg, self.audit, self.plans)
        self.gov = Governance(self.st, self.sim, self.audit, self.plans, self.prefs, self.ing.agg)
        self.inc = Incidents(self.st, self.sim, self.audit, self.plans, self.ing.agg)
        self.sched = Scheduler(self.st, self.audit, self.plans, self.ing.agg)
        self.specs: dict[str, dict] = {}
        self.stop = False
        self.cycle_ms: list[float] = []
        self.status_port = status_port
        self._load_specs()

    def _load_specs(self):
        for w in self.sim.get("/workflows"):
            self.specs[w["workflow_id"]] = w
            self.st.x("INSERT INTO workflows(wf,tenant,spec) VALUES(?,?,?) ON CONFLICT(wf) DO UPDATE SET spec=excluded.spec",
                      (w["workflow_id"], w["tenant_id"], json.dumps(w)))

    # ------------------------------------------------------------------ reaction to config changes by others
    def _react(self, now: int):
        for wf in self.specs:
            last = self.st.get(f"reacted:{wf}", 0)
            rows = self.st.q("SELECT version,minute,actor,dims,proposal_id FROM cfg_timeline WHERE wf=? AND version>? ORDER BY version",
                             (wf, last))
            for ver, minute, actor, dims, pid in rows:
                dims = json.loads(dims)
                if actor == "supervisor":
                    self._on_supervisor_edit(wf, ver, minute, dims, now)
                else:
                    self.audit.decision(now, wf, "config_change_seen", f"v{ver} by {actor}", "event stream",
                                        {"dims": dims, "proposal_id": pid}, "recorded", f"v{ver} {actor} changed {dims}",
                                        proposal_id=pid, version=ver)
                self.st.put(f"reacted:{wf}", ver)

    def _on_supervisor_edit(self, wf: str, ver: int, minute: int, dims: list[str], now: int):
        """A supervisor edit is a fact of life: we record it, take our hands off those dimensions for HOLD_DAYS, cancel
        any experiment that depended on them, and never revert them behind their back. (A prompt that is demonstrably
        unsafe is handled by the incident flow - through an approval, with evidence, and a notice.)"""
        until = minute + HOLD_DAYS * 1440
        for dim in dims:
            if dim != "prompt_version":
                self.st.x("INSERT INTO holds VALUES(?,?,?,?) ON CONFLICT(wf,dim) DO UPDATE SET until_min=excluded.until_min,"
                          "reason=excluded.reason", (wf, dim, until, f"supervisor edit v{ver}"))
                self.plans.clear_dim(wf, dim)
        closed = []
        for e in self.exps.all_for(wf):
            if e["status"] != "closed" and any(e["id"].split(":")[1] == d for d in dims):
                e["status"] = "closed"
                e["state"]["result"] = "superseded_by_supervisor"
                self.exps._save(e, wf, e["id"].split(":")[1], now)
                closed.append(e["id"])
        tenant = self.specs[wf]["tenant_id"]
        did = self.audit.decision(
            now, wf, "supervisor_edit_seen", f"supervisor changed {dims} at v{ver}", "supervisor edits bypass governance and win",
            {"dims": dims, "hold_until": minute_to_str(until), "experiments_closed": closed}, "hands off those dimensions",
            f"respecting supervisor edit v{ver} ({dims}); pending proposals on the old base go stale and are re-planned")
        self.audit.notice(now, tenant, wf, "supervisor_edit", f"Your change v{ver} ({', '.join(dims)}) is respected; the "
                          f"controller will not touch {', '.join(d for d in dims if d != 'prompt_version') or 'it'} until "
                          f"{minute_to_str(until)}.")

    def _holds(self, wf: str, now: int) -> set[str]:
        return {d for d, until in self.st.q("SELECT dim, until_min FROM holds WHERE wf=?", (wf,)) if until > now}

    # ------------------------------------------------------------------ one cycle
    def cycle(self, state: dict):
        now = state["sim_minute"]
        t0 = time.perf_counter()
        n = self.ing.sync(now)
        t_ing = time.perf_counter() - t0
        maybe_crash("after_sync")
        self._react(now)
        rates = []
        for wf, spec in self.specs.items():
            live = self.sim.get(f"/workflows/{wf}/config")
            ver, cfg = live["version"], live["config"]
            import json as _j
            if self.st.one("SELECT 1 FROM cfg_snapshots WHERE wf=? AND version=?", (wf, ver)) is None:
                self.st.x("INSERT OR IGNORE INTO cfg_snapshots VALUES(?,?,?)", (wf, ver, _j.dumps(cfg)))
            held = self._holds(wf, now)
            r = self.st.one("SELECT minute FROM cfg_timeline WHERE wf=? AND version=?", (wf, ver))
            live_since = r[0] if r else -10 ** 6
            incident_open = bool(self.st.one("SELECT 1 FROM incidents WHERE wf=? AND status='open'", (wf,)))
            self.inc.step_prompt(wf, spec, now, cfg, ver, state["credits_remaining"])
            self.inc.step_did(wf, spec, now, cfg, "caller_id" in held)
            self.exps.step(wf, spec, now, cfg, live_since, state["end_minute"], held, incident_open)
            self.sched.step(wf, spec, now, cfg, "schedule" in held or "cohorts" in held)
            self.gov.cycle(wf, spec, now, state["end_minute"])
            self._autonomy(wf, spec, now)
        dt = (time.perf_counter() - t0) * 1000
        self.cycle_ms.append(dt)
        self.st.x("INSERT OR REPLACE INTO metrics VALUES(?,?,?)", (now, "cycle_ms", dt))
        self.st.x("INSERT OR REPLACE INTO metrics VALUES(?,?,?)", (now, "ingest_events", n))
        self.st.x("INSERT OR REPLACE INTO metrics VALUES(?,?,?)", (now, "ingest_s", t_ing))
        self.st.x("INSERT OR REPLACE INTO metrics VALUES(?,?,?)", (now, "credits", state["credits_remaining"]))
        return n

    def _autonomy(self, wf: str, spec: dict, now: int):
        """Earned autonomy: a customer-facing dimension may be auto-applied (where the policy permits) once a human-approved
        change on it has been live for a day and nothing had to be rolled back."""
        pol = spec["governance"]["auto_apply"]
        if not pol.get("enabled"):
            return
        for dim in ("welcome_message", "voice"):
            if dim not in pol.get("allowed_dims", []) or self.gov.autonomy(wf, dim) >= 1:
                continue
            row = self.st.one("SELECT MIN(updated_min) FROM proposals WHERE wf=? AND route='approval' AND status='applied' "
                              "AND dims LIKE ?", (wf, f'%"{dim}"%'))
            if row and row[0] is not None and now - row[0] >= 1440:
                rb = self.st.one("SELECT 1 FROM decisions WHERE wf=? AND kind='rollback_planned' AND experiment_id LIKE ? ",
                                 (wf, f"{wf}:{dim}:%"))
                if not rb:
                    self.gov.grant(now, wf, dim, "one human-approved change has been live >=24h with no rollback")

    # ------------------------------------------------------------------ service loop
    def run(self):
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "stop", True))
        if self.status_port:
            from .status import serve
            serve(self, self.status_port)
        log.info("controller up; resuming from event %s", self.ing.last_event_id)
        t_start = time.time()
        while not self.stop:
            try:
                state = self.sim.state()
                self.cycle(state)
                if state["finished"]:
                    break
                maybe_crash("before_advance")
                self.sim.advance(STEP)
                maybe_crash("after_advance_before_ingest")
            except SimError as e:
                if e.code == "finished":
                    continue
                log.error("sim error %s", e)
                time.sleep(1)
            except SimUnavailable as e:
                log.error("simulator unreachable: %s", e)
                self.audit.alert(0, "page", None, "sim_unreachable", f"cannot reach the simulator: {e}")
                time.sleep(5)
        # last drain so the audit store contains the final state
        state = self.sim.state()
        self.ing.sync(state["sim_minute"])
        self._react(state["sim_minute"])
        log.info("scenario finished in %.0fs wall; events=%d decisions=%d", time.time() - t_start, self.ing.events_total,
                 self.audit.n_decisions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=os.environ.get("SIM_URL", "http://127.0.0.1:8700"))
    ap.add_argument("--db", default=os.environ.get("CONTROLLER_DB", "state/controller.db"))
    ap.add_argument("--prefs", default=os.environ.get("CONTROLLER_PREFS", "controller/preferences.yaml"))
    ap.add_argument("--status-port", type=int, default=int(os.environ.get("CONTROLLER_PORT", "0")) or None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, stream=sys.stderr,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    Controller(a.url, a.db, a.prefs, a.status_port).run()


if __name__ == "__main__":
    main()
