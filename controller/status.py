"""Loop health (C14) and the one-screen supervisor view (C11), served from the controller's own store.

  GET /status[?tenant=..]  what is being tested, what is winning, what we want from you, what changed today
  GET /metrics             ingest lag/throughput, decision lag, decisions/hour, credit burn, open alerts
  GET /explain?workflow=..&at=D3T14:00
Alert policy (also in SUBMISSION.md section 10): 'page' = a client-visible harm or the loop is blind/stuck, and the text says
what to look at; 'ticket' = can wait until morning; everything else is a decision-log row, not an alert.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .explain import explain
from .util import minute_to_str, parse_when


def _q(db, sql, a=()):
    return db.execute(sql, a).fetchall()


def metrics(path: str) -> dict:
    db = sqlite3.connect(path)
    now = (_q(db, "SELECT value FROM meta WHERE key='max_minute'") or [["0"]])[0][0]
    now = int(json.loads(now)) if now else 0
    cyc = [r[0] for r in _q(db, "SELECT value FROM metrics WHERE name='cycle_ms' ORDER BY minute DESC LIMIT 200")]
    ing = _q(db, "SELECT SUM(value) FROM metrics WHERE name='ingest_events'")[0][0] or 0
    ing_s = _q(db, "SELECT SUM(value) FROM metrics WHERE name='ingest_s'")[0][0] or 0
    cred = _q(db, "SELECT value FROM metrics WHERE name='credits' ORDER BY minute DESC LIMIT 1")
    burn = _q(db, "SELECT COALESCE(SUM(cost),0) FROM credits")[0][0]
    day_ago = now - 1440
    dec_h = _q(db, "SELECT COUNT(*) FROM decisions WHERE minute>?", (day_ago,))[0][0] / 24
    cyc.sort()
    p = lambda q: round(cyc[int(q * (len(cyc) - 1))], 1) if cyc else None
    return {
        "sim_time": minute_to_str(now),
        "ingest": {"events_total": json.loads((_q(db, "SELECT value FROM meta WHERE key='events_total'") or [["0"]])[0][0]),
                   "events_per_sec_ingest_only": round(ing / ing_s) if ing_s else None},
        "decision_lag_ms": {"p50": p(0.5), "p95": p(0.95), "max": p(1.0)},
        "decisions_per_sim_hour_last_24h": round(dec_h, 2),
        "credits": {"remaining": cred[0][0] if cred else None, "spent_by_controller": burn},
        "proposals": dict(_q(db, "SELECT status, COUNT(*) FROM proposals GROUP BY status")),
        "open_alerts": [{"severity": r[0], "workflow": r[1], "code": r[2], "text": r[3], "since": minute_to_str(r[4])}
                        for r in _q(db, "SELECT severity,wf,code,text,minute FROM alerts WHERE resolved_min IS NULL ORDER BY "
                                        "CASE severity WHEN 'page' THEN 0 ELSE 1 END, minute")],
    }


def status(path: str, tenant: str | None = None) -> dict:
    db = sqlite3.connect(path)
    now = (_q(db, "SELECT value FROM meta WHERE key='max_minute'") or [["0"]])[0][0]
    now = int(json.loads(now)) if now else 0
    out = {"as_of": minute_to_str(now), "workflows": {}}
    for wf, ten in _q(db, "SELECT wf, tenant FROM workflows"):
        if tenant and ten != tenant:
            continue
        w = {"tenant": ten}
        testing, winning = [], []
        for eid, st, ctrl, arms, state in _q(db, "SELECT id,status,control,arms,state FROM experiments WHERE wf=?", (wf,)):
            s = json.loads(state)
            if st == "running":
                testing.append({"experiment": eid, "incumbent": ctrl, "arms": json.loads(arms), "dropped": s.get("dropped", [])})
            elif st in ("promoting", "monitoring"):
                winning.append({"experiment": eid, "winner": s.get("winner"), "overrides": s.get("overrides"),
                                "status": st, "holdout": s.get("holdout")})
        w["what_is_being_tested"] = testing
        w["what_is_winning"] = winning
        w["what_we_want_from_you"] = [
            {"approval_id": r[0], "proposal_id": r[1], "summary": json.loads(r[2]).get("summary"), "impact_score": r[3],
             "submitted": minute_to_str(r[4]), "expires": r[5] and minute_to_str(r[5])}
            for r in _q(db, "SELECT approval_id,proposal_id,payload,impact,submitted_min,expires_min FROM proposals "
                            "WHERE wf=? AND route='approval' AND status IN ('pending','approved') ORDER BY impact DESC", (wf,))]
        w["what_changed_today"] = [
            {"when": minute_to_str(r[0]), "kind": r[1], "text": r[2]} for r in _q(
                db, "SELECT minute,kind,text FROM notices WHERE wf=? AND minute>? ORDER BY id DESC", (wf, now - 1440))]
        w["holds"] = [{"dim": r[0], "until": minute_to_str(r[1]), "reason": r[2]} for r in
                      _q(db, "SELECT dim,until_min,reason FROM holds WHERE wf=? AND until_min>?", (wf, now))]
        w["autonomy"] = {r[0]: r[1] for r in _q(db, "SELECT dim,level FROM autonomy WHERE wf=?", (wf,))}
        w["open_incidents"] = [r[0] for r in _q(db, "SELECT kind FROM incidents WHERE wf=? AND status='open'", (wf,))]
        out["workflows"][wf] = w
    return out


def serve(ctrl, port: int):
    path = ctrl.st.path

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/health":
                    body = {"ok": True}
                elif u.path == "/metrics":
                    body = metrics(path)
                elif u.path == "/status":
                    body = status(path, q.get("tenant"))
                elif u.path == "/explain":
                    body = explain(path, q["workflow"], parse_when(q["at"]) if "at" in q else None,
                                   int(q["version"]) if "version" in q else None)
                else:
                    self.send_error(404)
                    return
            except Exception as e:  # never take the loop down because of a read-only view
                body = {"error": str(e)}
            data = json.dumps(body, indent=1, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    srv = ThreadingHTTPServer(("0.0.0.0", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
