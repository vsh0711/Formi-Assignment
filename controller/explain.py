"""Answer "why did workflow X change at T, who approved it, and what happened next?" from OUR store only (C12).

    python -m controller.explain --db state/x.db --workflow nw_renewal --at D3T14:00
    python -m controller.explain --db state/x.db --workflow nw_renewal --version 7
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from .util import minute_to_str, parse_when

TICK = 15


def _rate(db, wf, t0, t1):
    d = c = e = 0
    for dials, conn, eng in db.execute("SELECT SUM(dials),SUM(conn),SUM(eng) FROM agg_tick WHERE wf=? AND tick>=? AND tick<?",
                                       (wf, t0 // TICK, t1 // TICK)):
        d, c, e = dials or 0, conn or 0, eng or 0
    return {"dials": d, "pickup": round(c / d, 4) if d else None, "engagement": round(e / c, 4) if c else None}


def explain(db_path: str, wf: str, at: int | None = None, version: int | None = None) -> dict:
    db = sqlite3.connect(db_path)
    if version is None:
        r = db.execute("SELECT version FROM cfg_timeline WHERE wf=? AND minute<=? ORDER BY version DESC LIMIT 1", (wf, at)).fetchone()
        if not r:
            return {"error": f"no config change recorded for {wf} at or before {minute_to_str(at)}"}
        version = r[0]
    row = db.execute("SELECT version,minute,actor,dims,proposal_id,approval_id FROM cfg_timeline WHERE wf=? AND version=?",
                     (wf, version)).fetchone()
    if not row:
        return {"error": f"unknown version {version}"}
    ver, minute, actor, dims, pid, aid = row
    out: dict = {"workflow": wf, "version": ver, "when": minute_to_str(minute), "minute": minute, "actor": actor,
                 "changed_dims": json.loads(dims)}
    prev = db.execute("SELECT config FROM cfg_snapshots WHERE wf=? AND version=?", (wf, ver - 1)).fetchone()
    cur = db.execute("SELECT config FROM cfg_snapshots WHERE wf=? AND version=?", (wf, ver)).fetchone()
    if prev and cur:
        out["config_before"], out["config_after"] = json.loads(prev[0]), json.loads(cur[0])
    if actor == "supervisor":
        out["why"] = "client supervisor edit (bypasses governance by design); controller recorded it and held its hands off"
    prop = None
    if pid:
        prop = db.execute("SELECT proposal_id,route,status,created_min,submitted_min,decided_min,apply_by_min,approval_id,payload,"
                          "impact,reasons,attempt FROM proposals WHERE proposal_id=?", (pid,)).fetchone()
    if prop:
        payload = json.loads(prop[8])
        body = payload.get("body", {})
        out["proposal"] = {"proposal_id": prop[0], "route": prop[1], "status": prop[2], "created": minute_to_str(prop[3]),
                           "submitted": prop[4] and minute_to_str(prop[4]), "approver_decided": prop[5] and minute_to_str(prop[5]),
                           "approval_id": prop[7] or aid, "attempt": prop[11],
                           "change_summary": body.get("change_summary") or payload.get("summary"),
                           "impact_score": prop[9], "affected_leads": body.get("affected_leads"), "diff": body.get("diff"),
                           "dry_run": body.get("dry_run"), "rationale": body.get("rationale") or None,
                           "slot": payload.get("slot_reason"), "approver_rejections_before": prop[10]}
        who = {"controller_approved": "named client approver (simulated approver) via /approvals",
               "controller_auto": "no human: policy-permitted auto-apply (governance.auto_apply)"}.get(actor)
        out["approved_by"] = who
        why = payload.get("whys", [])
        out["reasons"] = [{"kind": w.get("kind"), "summary": w.get("summary"), "rationale": w.get("rationale"),
                           "decision_id": w.get("decision")} for w in why]
    # decision chain: everything tied to the proposal, plus the decisions that caused the planned dims
    ids = [r[0] for r in db.execute("SELECT id FROM decisions WHERE wf=? AND proposal_id=?", (wf, pid))] if pid else []
    for w in (out.get("reasons") or []):
        if w.get("decision_id"):
            ids.append(w["decision_id"])
    chain = []
    for i in sorted(set(ids)):
        r = db.execute("SELECT id,minute,kind,trigger,rule,inputs,outcome,summary,experiment_id FROM decisions WHERE id=?", (i,)).fetchone()
        if r:
            chain.append({"id": r[0], "when": minute_to_str(r[1]), "kind": r[2], "trigger": r[3], "rule": r[4],
                          "outcome": r[6], "summary": r[7], "experiment": r[8], "evidence": json.loads(r[5])})
    out["decision_chain"] = chain
    after = db.execute("SELECT minute,kind,outcome,summary FROM decisions WHERE wf=? AND minute>? AND kind IN "
                       "('monitor','fix_verified','fix_failed','rollback_planned','winner_declared','promotion_live','arm_dropped',"
                       "'incident_closed','no_winner','experiment_look','autonomy_granted') ORDER BY id LIMIT 12", (wf, minute)).fetchall()
    out["what_happened_next"] = {
        "decisions": [{"when": minute_to_str(a[0]), "kind": a[1], "outcome": a[2], "summary": a[3]} for a in after],
        "kpi_24h_before": _rate(db, wf, minute - 1440, minute), "kpi_24h_after": _rate(db, wf, minute, minute + 1440),
        "note": "before/after is descriptive (population mix and other changes move too); the causal evidence is in the decision chain"}
    nxt = db.execute("SELECT version,minute,actor,dims FROM cfg_timeline WHERE wf=? AND version>? ORDER BY version LIMIT 1", (wf, ver)).fetchone()
    if nxt:
        out["next_change"] = {"version": nxt[0], "when": minute_to_str(nxt[1]), "actor": nxt[2], "dims": json.loads(nxt[3])}
    return out


def render(x: dict) -> str:
    if "error" in x:
        return x["error"]
    L = [f"{x['workflow']} v{x['version']} at {x['when']} by {x['actor']}  dims={x['changed_dims']}"]
    if x.get("approved_by"):
        L.append(f"  approval: {x['approved_by']}")
    if x.get("why"):
        L.append(f"  why: {x['why']}")
    p = x.get("proposal")
    if p:
        L += [f"  proposal {p['proposal_id']} ({p['route']}, attempt {p['attempt']}) -> {p['status']}",
              f"    summary: {p['change_summary']}", f"    created {p['created']}, submitted {p['submitted']}, decided {p['approver_decided']}, "
              f"approval {p['approval_id']}", f"    impact {p['impact_score']}  affected_leads {p['affected_leads']}",
              f"    slot: {p['slot']}", f"    rationale: {p['rationale']}"]
    for r in x.get("reasons") or []:
        L.append(f"  because [{r['kind']}] {r['summary']}  (decision #{r['decision_id']})")
    for c in x.get("decision_chain") or []:
        L.append(f"  decision #{c['id']} {c['when']} {c['kind']}: {c['summary']}  rule: {c['rule']}")
    n = x.get("what_happened_next", {})
    L.append(f"  KPI 24h before: {n.get('kpi_24h_before')}   after: {n.get('kpi_24h_after')}")
    for d in n.get("decisions", []):
        L.append(f"  next: {d['when']} {d['kind']} -> {d['outcome']}: {d['summary']}")
    if x.get("next_change"):
        L.append(f"  superseded by v{x['next_change']['version']} ({x['next_change']['actor']}) at {x['next_change']['when']}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--at", help="e.g. D3T14:00")
    ap.add_argument("--version", type=int)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    x = explain(a.db, a.workflow, parse_when(a.at) if a.at else None, a.version)
    print(json.dumps(x, indent=2) if a.json else render(x))


if __name__ == "__main__":
    main()
