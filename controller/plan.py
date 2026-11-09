"""Desired state ("the plan") per workflow.

Planners (experiments, caller-ID, schedule, incident response) never talk to the simulator. They edit the plan:
"I want default voice to be X, these cohorts to exist, this schedule, this prompt". The governance executor is the
only component that turns a plan into API calls, by diffing plan vs. the *live* config. Consequences:
  * crash safety: the plan is persisted; after a restart the executor recomputes the diff, nothing is "in memory only"
  * stale base / supervisor edits: the diff is always recomputed against fresh live config
  * batching: all pending desires for a workflow become ONE proposal (one request with five things)
"""
from __future__ import annotations

import copy
import json

from . import cfgutil
from .store import Store

EMPTY = {"cohorts": None, "cohort_defs": {}, "alloc": {}, "schedule": None, "prompt": None, "why": {}}


def dim_of(key: str) -> str:
    if key == "cohorts":
        return "cohorts"
    if key == "schedule":
        return "schedule"
    if key == "prompt":
        return "prompt_version"
    return key.rsplit(":", 1)[1]  # alloc:<cohort>:<dim>


class PlanStore:
    def __init__(self, st: Store):
        self.st = st

    def get(self, wf: str) -> dict:
        r = self.st.one("SELECT body FROM plan WHERE wf=?", (wf,))
        return json.loads(r[0]) if r else copy.deepcopy(EMPTY)

    def save(self, wf: str, body: dict):
        self.st.x("INSERT INTO plan(wf,body) VALUES(?,?) ON CONFLICT(wf) DO UPDATE SET body=excluded.body",
                  (wf, json.dumps(body, sort_keys=True)))

    def set_alloc(self, wf: str, cohort: str, dim: str, d: dict, why: dict):
        p = self.get(wf)
        p["alloc"].setdefault(cohort, {})[dim] = cfgutil.round_dist(d)
        p["why"][f"alloc:{cohort}:{dim}"] = why
        self.save(wf, p)

    def clear(self, wf: str, key: str):
        p = self.get(wf)
        if key == "cohorts":
            p["cohorts"] = None
        elif key == "schedule":
            p["schedule"] = None
        elif key == "prompt":
            p["prompt"] = None
        else:
            _, cohort, dim = key.split(":", 2)
            if cohort in p["alloc"]:
                p["alloc"][cohort].pop(dim, None)
                if not p["alloc"][cohort]:
                    del p["alloc"][cohort]
        p["why"].pop(key, None)
        self.save(wf, p)

    def clear_dim(self, wf: str, dim: str):
        """Drop every desire touching a config dimension (used when a supervisor takes ownership of it)."""
        p = self.get(wf)
        for k in list(p["why"]):
            if dim_of(k) == dim:
                self.clear(wf, k)

    def add_cohort_defs(self, wf: str, defs: list[dict]):
        p = self.get(wf)
        for d in defs:
            p.setdefault("cohort_defs", {})[d["id"]] = d
        self.save(wf, p)

    def set_cohorts(self, wf: str, cohorts: list[dict] | None, why: dict):
        p = self.get(wf)
        p["cohorts"] = cohorts
        p["why"]["cohorts"] = why
        self.save(wf, p)

    def set_schedule(self, wf: str, hour_weights: dict, why: dict):
        p = self.get(wf)
        p["schedule"] = hour_weights
        p["why"]["schedule"] = why
        self.save(wf, p)

    def set_prompt(self, wf: str, prompt: str, why: dict):
        p = self.get(wf)
        p["prompt"] = prompt
        p["why"]["prompt"] = why
        self.save(wf, p)


def target_config(live: dict, plan: dict) -> dict:
    """live config + the plan's desires, as a valid canonical config."""
    cfg = copy.deepcopy(live)
    cfg.setdefault("cohorts", [])
    if plan.get("cohorts") is not None:
        cfg["cohorts"] = copy.deepcopy(plan["cohorts"])
    have = {c["id"] for c in cfg["cohorts"]}
    for cohort in plan.get("alloc", {}):
        if cohort != "default" and cohort not in have and cohort in plan.get("cohort_defs", {}):
            cfg["cohorts"].append(copy.deepcopy(plan["cohort_defs"][cohort]))
            have.add(cohort)
    for cohort, dims in plan.get("alloc", {}).items():
        cfg["allocations"].setdefault(cohort, {})
        for dim, d in dims.items():
            cfg["allocations"][cohort][dim] = dict(d)
    if plan.get("schedule") is not None:
        cfg.setdefault("schedule", {"hour_weights": {}, "lead_preferred_hour": {}})
        cfg["schedule"]["hour_weights"] = copy.deepcopy(plan["schedule"])
    if plan.get("prompt") is not None:
        cfg["prompt_version"] = plan["prompt"]
    return cfgutil.clean(cfg)
