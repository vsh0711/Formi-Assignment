"""Audit store (C12) + feed (C11). Every decision the controller takes - including decisions NOT to act - is a row
with the rule that fired and the statistics snapshot that triggered it, so any change can be explained from here."""
from __future__ import annotations

import json
import logging

from .store import Store

log = logging.getLogger("controller.audit")


class Audit:
    def __init__(self, st: Store):
        self.st = st
        self.n_decisions = 0

    def decision(self, minute: int, wf: str, kind: str, trigger: str, rule: str, inputs: dict, outcome: str,
                 summary: str, proposal_id: str | None = None, experiment_id: str | None = None,
                 version: int | None = None, parent_id: int | None = None) -> int:
        cur = self.st.x(
            "INSERT INTO decisions(minute,wf,kind,trigger,rule,inputs,outcome,summary,proposal_id,experiment_id,"
            "version,parent_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (minute, wf, kind, trigger, rule, json.dumps(inputs, default=str), outcome, summary, proposal_id,
             experiment_id, version, parent_id))
        self.n_decisions += 1
        log.info("[%s] %s %s -> %s | %s", wf, kind, trigger, outcome, summary)
        return cur.lastrowid

    def alert(self, minute: int, severity: str, wf: str | None, code: str, text: str):
        """severity: 'page' (act now, message says what to look at) | 'ticket' (can wait until morning) | 'info'."""
        open_ = self.st.one("SELECT id FROM alerts WHERE code=? AND IFNULL(wf,'')=IFNULL(?,'') AND resolved_min IS NULL",
                            (code, wf))
        if open_:
            return open_[0]
        cur = self.st.x("INSERT INTO alerts(minute,severity,wf,code,text) VALUES(?,?,?,?,?)",
                        (minute, severity, wf, code, text))
        log.warning("ALERT[%s] %s %s: %s", severity, wf, code, text)
        return cur.lastrowid

    def resolve_alert(self, minute: int, wf: str | None, code: str):
        self.st.x("UPDATE alerts SET resolved_min=? WHERE code=? AND IFNULL(wf,'')=IFNULL(?,'') AND resolved_min IS NULL",
                  (minute, code, wf))

    def notice(self, minute: int, tenant: str, wf: str, kind: str, text: str, effective_min: int | None = None):
        self.st.x("INSERT INTO notices(minute,tenant,wf,kind,text,effective_min) VALUES(?,?,?,?,?,?)",
                  (minute, tenant, wf, kind, text, effective_min))
