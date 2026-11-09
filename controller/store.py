"""SQLite (WAL) state store. One file holds everything the controller must remember across restarts:

  ingest cursor + aggregates  -> what the world looked like (sufficient statistics, never raw calls)
  plan / experiments / holds  -> what the controller intends and why
  proposals                   -> the governance state machine (write-ahead: intent is persisted before any POST)
  decisions / notices / alerts-> the audit trail (C12) and the supervisor-facing feed (C11)

Everything that mutates the world is written *before* the HTTP call (intent) and reconciled *after* a crash
by asking the simulator (GET /approvals, config history), so a kill -9 at any point cannot double-apply.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS workflows(wf TEXT PRIMARY KEY, tenant TEXT, spec TEXT);
CREATE TABLE IF NOT EXISTS leads(lead_id TEXT PRIMARY KEY, wf TEXT, day INTEGER, cell TEXT) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS leads_day ON leads(day);
CREATE TABLE IF NOT EXISTS campaigns(campaign_id TEXT PRIMARY KEY, wf TEXT, day INTEGER, leads INTEGER,
    version_at_creation INTEGER, minute INTEGER);

-- sufficient statistics (counts only). dials / connected / engaged [+ flagged, adherence for ticks]
CREATE TABLE IF NOT EXISTS agg_cell(wf TEXT, day INTEGER, ver INTEGER, cohort TEXT, cell TEXT, dim TEXT, opt TEXT,
    dials INTEGER, conn INTEGER, eng INTEGER, PRIMARY KEY(wf, day, ver, cohort, cell, dim, opt)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS agg_arm6(wf TEXT, b6 INTEGER, ver INTEGER, cohort TEXT, dim TEXT, opt TEXT,
    dials INTEGER, conn INTEGER, eng INTEGER, PRIMARY KEY(wf, b6, ver, cohort, dim, opt)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS agg_hour(wf TEXT, par INTEGER, cell TEXT, hour INTEGER, att INTEGER,
    dials INTEGER, conn INTEGER, eng INTEGER, PRIMARY KEY(wf, par, cell, hour, att)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS agg_tick(wf TEXT, tick INTEGER, did TEXT, prompt TEXT,
    dials INTEGER, conn INTEGER, eng INTEGER, flag INTEGER, adh_milli INTEGER,
    PRIMARY KEY(wf, tick, did, prompt)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS agg_day(wf TEXT, day INTEGER, uploaded INTEGER, dials INTEGER, conn INTEGER, eng INTEGER,
    PRIMARY KEY(wf, day)) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS cfg_timeline(wf TEXT, version INTEGER, minute INTEGER, actor TEXT, dims TEXT,
    proposal_id TEXT, approval_id TEXT, PRIMARY KEY(wf, version));
CREATE TABLE IF NOT EXISTS cfg_snapshots(wf TEXT, version INTEGER, config TEXT, PRIMARY KEY(wf, version));

CREATE TABLE IF NOT EXISTS proposals(proposal_id TEXT PRIMARY KEY, wf TEXT, route TEXT, kind TEXT, status TEXT,
    urgent INTEGER, base_version INTEGER, approval_id TEXT, created_min INTEGER, submitted_min INTEGER,
    decided_min INTEGER, expires_min INTEGER, apply_by_min INTEGER, applied_version INTEGER,
    dims TEXT, attempt_key TEXT, attempt INTEGER, payload TEXT, reasons TEXT, impact REAL, updated_min INTEGER);
CREATE INDEX IF NOT EXISTS proposals_wf ON proposals(wf, status);

CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER, wf TEXT, kind TEXT,
    trigger TEXT, rule TEXT, inputs TEXT, outcome TEXT, summary TEXT, proposal_id TEXT, experiment_id TEXT,
    version INTEGER, parent_id INTEGER);
CREATE INDEX IF NOT EXISTS decisions_wf ON decisions(wf, minute);

CREATE TABLE IF NOT EXISTS experiments(id TEXT PRIMARY KEY, wf TEXT, dim TEXT, status TEXT, control TEXT,
    arms TEXT, prereg TEXT, started_min INTEGER, promo_min INTEGER, state TEXT, updated_min INTEGER);
CREATE TABLE IF NOT EXISTS exp_pvals(exp_id TEXT, arm TEXT, seg TEXT, kind TEXT, p_min REAL, looks INTEGER,
    PRIMARY KEY(exp_id, arm, seg, kind));
CREATE TABLE IF NOT EXISTS plan(wf TEXT PRIMARY KEY, body TEXT);
CREATE TABLE IF NOT EXISTS holds(wf TEXT, dim TEXT, until_min INTEGER, reason TEXT, PRIMARY KEY(wf, dim));
CREATE TABLE IF NOT EXISTS autonomy(wf TEXT, dim TEXT, level INTEGER, since_min INTEGER, reason TEXT,
    PRIMARY KEY(wf, dim));
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, wf TEXT, kind TEXT, status TEXT, opened_min INTEGER,
    closed_min INTEGER, state TEXT);
CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER, tenant TEXT, wf TEXT,
    kind TEXT, text TEXT, effective_min INTEGER);
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER, severity TEXT, wf TEXT,
    code TEXT, text TEXT, resolved_min INTEGER);
CREATE TABLE IF NOT EXISTS credits(id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER, wf TEXT, what TEXT,
    cost REAL, remaining REAL, incident_id TEXT);
CREATE TABLE IF NOT EXISTS validations(run_id TEXT PRIMARY KEY, wf TEXT, prompt TEXT, n INTEGER, failures INTEGER,
    pass_rate REAL, minute INTEGER, incident_id TEXT);
CREATE TABLE IF NOT EXISTS metrics(minute INTEGER, name TEXT, value REAL, PRIMARY KEY(minute, name));
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
        self.lock = threading.RLock()
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)

    # -- tiny helpers -------------------------------------------------------------------------------------
    def q(self, sql: str, args=()) -> list[tuple]:
        with self.lock:
            return self.db.execute(sql, args).fetchall()

    def one(self, sql: str, args=()):
        with self.lock:
            return self.db.execute(sql, args).fetchone()

    def x(self, sql: str, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def many(self, sql: str, rows):
        with self.lock:
            self.db.executemany(sql, rows)

    def tx(self):
        return _Tx(self)

    def get(self, key: str, default=None):
        r = self.one("SELECT value FROM meta WHERE key=?", (key,))
        return json.loads(r[0]) if r else default

    def put(self, key: str, value):
        self.x("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
               (key, json.dumps(value)))


class _Tx:
    """BEGIN IMMEDIATE ... COMMIT; rolls back on exception. Re-entrant callers must not nest."""

    def __init__(self, s: Store):
        self.s = s

    def __enter__(self):
        self.s.lock.acquire()
        self.s.db.execute("BEGIN IMMEDIATE")
        return self.s

    def __exit__(self, et, ev, tb):
        try:
            self.s.db.execute("ROLLBACK" if et else "COMMIT")
        finally:
            self.s.lock.release()
        return False
