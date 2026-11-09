"""Event ingestion (C1, C3): streaming, idempotent, restartable.

Design:
  * Each chunk is parsed into an in-memory *delta* of sufficient statistics, then committed to SQLite in ONE
    transaction together with the chunk cursor. A crash mid-chunk rolls the whole chunk back; on restart the same
    chunk is re-read. `event_id` is strictly increasing, so a replayed line can never be counted twice.
  * We keep counts, never raw calls. Memory is O(#distinct (workflow, day, version, cohort, cell, dim, option))
    rather than O(calls), so a 850k events/day stream costs the same RAM as a 30k events/day one.
  * History chunks (C3) are read through the same code path - older history than `history_days_used` is skipped
    because only the recent profile matters (and the 10-minute/day budget does).
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

from . import cohorts
from .simclient import Sim
from .store import Store
from .util import maybe_crash, ts_to_minute

log = logging.getLogger("controller.ingest")
loads = json.loads
AGENT_DIMS = ("welcome_message", "voice", "caller_id")

AGG_SPECS = {  # table -> (key columns, counter columns)
    "agg_cell": (("wf", "day", "ver", "cohort", "cell", "dim", "opt"), ("dials", "conn", "eng")),
    "agg_arm6": (("wf", "b6", "ver", "cohort", "dim", "opt"), ("dials", "conn", "eng")),
    "agg_hour": (("wf", "par", "cell", "hour", "att"), ("dials", "conn", "eng")),
    "agg_tick": (("wf", "tick", "did", "prompt"), ("dials", "conn", "eng", "flag", "adh_milli")),
    "agg_day": (("wf", "day"), ("uploaded", "dials", "conn", "eng")),
}


def _upsert_sql(table: str) -> str:
    keys, cnt = AGG_SPECS[table]
    cols = keys + cnt
    sets = ",".join(f"{c}={c}+excluded.{c}" for c in cnt)
    return (f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))}) "
            f"ON CONFLICT({','.join(keys)}) DO UPDATE SET {sets}")


class Aggregates:
    """In-memory mirror of the agg_* tables, indexed by workflow: t[table][wf][key_without_wf] -> counters.
    Read by detectors/experiments; written only *after* the SQLite commit so readers never see uncommitted data."""

    def __init__(self):
        self.t: dict[str, dict[str, dict[tuple, list]]] = {k: {} for k in AGG_SPECS}
        self.ticks: dict[str, dict[int, dict[tuple, list]]] = {}  # wf -> tick -> {(did, prompt): counters}

    def wf(self, table: str, wf: str) -> dict:
        return self.t[table].get(wf) or {}

    def _put(self, table: str, k: tuple, v: list, add: bool):
        d = self.t[table].setdefault(k[0], {})
        rest = k[1:]
        cur = d.get(rest)
        if cur is None:
            cur = d[rest] = list(v)
        elif add:
            for i, x in enumerate(v):
                cur[i] += x
        if table == "agg_tick":
            self.ticks.setdefault(k[0], {}).setdefault(rest[0], {})[(rest[1], rest[2])] = cur

    def load(self, st: Store):
        for table, (keys, cnt) in AGG_SPECS.items():
            for row in st.q(f"SELECT {','.join(keys + cnt)} FROM {table}"):
                self._put(table, tuple(row[:len(keys)]), list(row[len(keys):]), False)

    def merge(self, delta: dict[str, dict[tuple, list]]):
        for table, rows in delta.items():
            for k, v in rows.items():
                self._put(table, k, v, True)


class Ingestor:
    def __init__(self, store: Store, sim: Sim, history_days_used: int = 7):
        self.st, self.sim = store, sim
        self.history_days_used = history_days_used
        self.agg = Aggregates()
        self.leadcell: dict[str, str] = {}
        self.lead_day: dict[int, list[str]] = defaultdict(list)
        self.last_event_id = 0
        self.cur_hist = -1
        self.cur_ev = -1
        self.events_total = 0
        self.max_minute = -10 ** 9
        self.unmapped = 0
        self.wall_ingest_s = 0.0
        self.version_seen: dict[str, int] = {}
        self._load()

    # ------------------------------------------------------------------ restart
    def _load(self):
        st = self.st
        feats = st.get("features")
        if feats:
            cohorts.set_features(feats)
        self.last_event_id = st.get("last_event_id", 0)
        self.cur_hist = st.get("cursor_history", -1)
        self.cur_ev = st.get("cursor_events", -1)
        self.events_total = st.get("events_total", 0)
        self.max_minute = st.get("max_minute", -10 ** 9)
        self.agg.load(st)
        day_now = self.max_minute // 1440
        for lid, day, cell in st.q("SELECT lead_id, day, cell FROM leads WHERE day >= ?", (day_now - 6,)):
            self.leadcell[lid] = cell
            self.lead_day[day].append(lid)
        for wf, v in st.q("SELECT wf, MAX(version) FROM cfg_timeline GROUP BY wf"):
            self.version_seen[wf] = v
        log.info("ingest restored: last_event=%s hist_chunk=%s ev_chunk=%s leads=%d", self.last_event_id,
                 self.cur_hist, self.cur_ev, len(self.leadcell))

    # ------------------------------------------------------------------ sync
    def sync(self, now_minute: int) -> int:
        """Drain every chunk we have not processed yet. Returns events ingested."""
        n = 0
        for kind, cur_attr in (("history", "cur_hist"), ("events", "cur_ev")):
            for meta in self.sim.chunks(kind, getattr(self, cur_attr)):
                if kind == "history" and meta["until_minute"] < -self.history_days_used * 1440:
                    self.st.put("cursor_history", meta["chunk"])
                    setattr(self, cur_attr, meta["chunk"])
                    continue
                n += self._process_chunk(meta, kind)
                setattr(self, cur_attr, meta["chunk"])
        return n

    # ------------------------------------------------------------------ core
    def _process_chunk(self, meta: dict, kind: str) -> int:
        t0 = time.perf_counter()
        leadcell = self.leadcell
        cell_d: dict = {}
        arm_d: dict = {}
        hour_d: dict = {}
        tick_d: dict = {}
        day_d: dict = {}
        new_leads: list[tuple] = []
        camps: list[tuple] = []
        cfg_rows: list[tuple] = []
        max_id, nev, max_min = self.last_event_id, 0, self.max_minute
        last_id = self.last_event_id
        feats_known = bool(self.st.get("features"))
        new_feats = None

        for line in self.sim.iter_chunk_lines(meta["chunk"]):
            ev = loads(line)
            eid = ev["event_id"]
            if eid <= last_id:
                continue  # replayed line (idempotency guard)
            if eid > max_id:
                max_id = eid
            nev += 1
            typ = ev["type"]
            if typ == "call":
                wf = ev["workflow_id"]
                m = ts_to_minute(ev["ts"])
                if m > max_min:
                    max_min = m
                day = m // 1440
                hour = (m - day * 1440) // 60
                conn, eng = ev["connected"], ev["engaged"]
                c, e = (1 if conn else 0), (1 if eng else 0)
                var, ver, coh = ev["variant"], ev["config_version"], ev["cohort_id"]
                cell = leadcell.get(ev["lead_id"])
                b6 = m // 360
                for dim in AGENT_DIMS:
                    opt = var[dim]
                    k = (wf, b6, ver, coh, dim, opt)
                    a = arm_d.get(k)
                    if a is None:
                        arm_d[k] = [1, c, e]
                    else:
                        a[0] += 1; a[1] += c; a[2] += e
                    if cell is not None:
                        k = (wf, day, ver, coh, cell, dim, opt)
                        a = cell_d.get(k)
                        if a is None:
                            cell_d[k] = [1, c, e]
                        else:
                            a[0] += 1; a[1] += c; a[2] += e
                if cell is not None:
                    k = (wf, day & 1, cell, hour, ev["attempt_no"] if ev["attempt_no"] < 3 else 3)
                    a = hour_d.get(k)
                    if a is None:
                        hour_d[k] = [1, c, e]
                    else:
                        a[0] += 1; a[1] += c; a[2] += e
                else:
                    self.unmapped += 1
                qa = ev["qa"]
                fl = 1 if (qa and qa["hallucination_flag"]) else 0
                adh = int(qa["flow_adherence"] * 1000) if qa else 0
                k = (wf, m // 15, var["caller_id"], var["prompt_version"])
                a = tick_d.get(k)
                if a is None:
                    tick_d[k] = [1, c, e, fl, adh]
                else:
                    a[0] += 1; a[1] += c; a[2] += e; a[3] += fl; a[4] += adh
                k = (wf, day)
                a = day_d.get(k)
                if a is None:
                    day_d[k] = [0, 1, c, e]
                else:
                    a[1] += 1; a[2] += c; a[3] += e
            elif typ == "lead":
                f = ev["features"]
                if not feats_known and new_feats is None:
                    new_feats = sorted(f)
                    cohorts.set_features(new_feats)
                cell = cohorts.cell_of(f)
                lid = ev["lead_id"]
                leadcell[lid] = cell
                day = ts_to_minute(ev["ts"]) // 1440
                new_leads.append((lid, ev["workflow_id"], day, cell))
                self.lead_day[day].append(lid)
            elif typ == "campaign_created":
                m = ts_to_minute(ev["ts"])
                camps.append((ev["campaign_id"], ev["workflow_id"], m // 1440, ev["leads"],
                              ev["config_version_at_creation"], m))
                k = (ev["workflow_id"], m // 1440)
                a = day_d.get(k)
                if a is None:
                    day_d[k] = [ev["leads"], 0, 0, 0]
                else:
                    a[0] += ev["leads"]
            elif typ == "config_changed":
                m = ts_to_minute(ev["ts"])
                cfg_rows.append((ev["workflow_id"], ev["version"], m, ev["actor"], json.dumps(ev["changed_dims"]),
                                 ev.get("proposal_id"), ev.get("approval_id")))

        maybe_crash("mid_ingest_before_commit")
        delta = {"agg_cell": cell_d, "agg_arm6": arm_d, "agg_hour": hour_d, "agg_tick": tick_d, "agg_day": day_d}
        st = self.st
        with st.tx():
            for table, rows in delta.items():
                if rows:
                    st.many(_upsert_sql(table), [k + tuple(v) for k, v in rows.items()])
            if new_leads:
                st.many("INSERT OR IGNORE INTO leads(lead_id,wf,day,cell) VALUES(?,?,?,?)", new_leads)
            if camps:
                st.many("INSERT OR IGNORE INTO campaigns VALUES(?,?,?,?,?,?)", camps)
            if cfg_rows:
                st.many("INSERT OR IGNORE INTO cfg_timeline(wf,version,minute,actor,dims,proposal_id,approval_id) "
                        "VALUES(?,?,?,?,?,?,?)", cfg_rows)
            if new_feats:
                st.put("features", new_feats)
            self.events_total += nev
            st.put("last_event_id", max_id)
            st.put("max_minute", max_min)
            st.put("events_total", self.events_total)
            st.put("cursor_events" if kind == "events" else "cursor_history", meta["chunk"])
        maybe_crash("after_ingest_commit")
        # commit succeeded: now it is safe to expose to readers
        self.agg.merge(delta)
        for r in cfg_rows:
            self.version_seen[r[0]] = max(self.version_seen.get(r[0], 0), r[1])
        self.last_event_id, self.max_minute = max_id, max_min
        self._prune(max_min // 1440)
        dt = time.perf_counter() - t0
        self.wall_ingest_s += dt
        log.debug("chunk %s (%s): %d events in %.2fs (%.0f ev/s)", meta["chunk"], kind, nev, dt, nev / max(dt, 1e-9))
        return nev

    def _prune(self, day_now: int):
        for d in [d for d in self.lead_day if d < day_now - 6]:
            for lid in self.lead_day.pop(d):
                self.leadcell.pop(lid, None)
        if day_now > self.st.get("pruned_day", -10 ** 9):
            self.st.x("DELETE FROM leads WHERE day < ?", (day_now - 6,))
            self.st.put("pruned_day", day_now)
