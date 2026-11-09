"""End-to-end: the real controller against the real simulator, in-process (no sockets). Invariants, not golden numbers."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from controller import main as cmain, simclient
from sim import server

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def in_process(monkeypatch):
    def fresh(tmp, scenario="public_01_dev"):
        server.init_world(str(ROOT / "scenarios" / f"{scenario}.yaml"), str(tmp))
        client = TestClient(server.app)
        monkeypatch.setattr(simclient.httpx, "Client", lambda base_url=None, timeout=None: client)
        return client
    return fresh


def _hist(client):
    out = {}
    for w in client.get("/workflows").json():
        out[w["workflow_id"]] = client.get(f"/workflows/{w['workflow_id']}/config/history").json()
    return out


def test_full_run_obeys_the_governance_boundary(tmp_path, in_process):
    client = in_process(tmp_path / "w1")
    ctrl = cmain.Controller("http://x", str(tmp_path / "c.db"))
    ctrl.run()
    assert client.get("/sim/state").json()["finished"]
    hist = _hist(client)
    st = ctrl.st
    # every config version the controller made came from one of the two sanctioned paths, with a recorded proposal id
    for wf, versions in hist.items():
        for v in versions:
            if v["actor"] == "controller_approved":
                assert v["approval_id"] and v["proposal_id"]
            elif v["actor"] == "controller_auto":
                assert v["proposal_id"] and not v["approval_id"]
    ids = [r[0] for r in st.q("SELECT proposal_id FROM proposals")]
    assert len(ids) == len(set(ids))                                   # no proposal id reused
    applied = [r for r in st.q("SELECT proposal_id, applied_version FROM proposals WHERE status='applied'")]
    assert len({(r[0]) for r in applied}) == len(applied)              # nothing applied twice
    assert st.one("SELECT COUNT(*) FROM decisions")[0] > 20            # audit trail exists
    # auto-apply only where the policy allows it, only on permitted dims
    for w in client.get("/workflows").json():
        pol = w["governance"]["auto_apply"]
        for v in hist[w["workflow_id"]]:
            if v["actor"] == "controller_auto":
                assert pol["enabled"] and set(v["changed_dims"]) <= set(pol["allowed_dims"])


def test_restart_mid_run_gives_the_same_result(tmp_path, in_process):
    c1 = in_process(tmp_path / "a")
    cmain.Controller("http://x", str(tmp_path / "ref.db")).run()
    ref = _hist(c1)
    c2 = in_process(tmp_path / "b")
    db = str(tmp_path / "chaos.db")
    for n in (150, 140, 90):                                           # three "processes", each abandoned mid-run
        cmain.Controller("http://x", db).run(max_cycles=n)
    cmain.Controller("http://x", db).run()
    assert _hist(c2) == ref
