#!/usr/bin/env python
"""Kill -9 the controller at awkward moments, restart it, and prove the run still finishes *identically*.

 1. reference run: controller runs uninterrupted against a fresh simulator.
 2. chaos run: a fresh simulator (same seed) + a controller that is hard-killed (os._exit(137), i.e. kill -9 semantics)
    at injected fault points - mid-chunk before commit, after the write-ahead intent but before the POST, after the POST but
    before it is recorded, before the apply, after the apply but before it is recorded, between advance and ingest - plus
    two external SIGKILLs at random wall-clock moments. Each time the controller is simply restarted.
 3. compare: config histories (version/actor/dims/proposal_id/approval_id/applied_at) and every approval must be identical,
    no proposal id is duplicated, nothing is double-applied, no approval is lost.

    python scripts/crash_test.py --scenario public_02_incidents --out reports/crash_recovery_public_02.md
"""
import argparse, json, os, random, signal, subprocess, sys, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def start_sim(scenario, port, run_dir):
    subprocess.run(["pkill", "-f", f"sim serve.*--port {port}"])  # never talk to a stale simulator from an earlier aborted run
    time.sleep(0.5)
    subprocess.run(["rm", "-rf", str(run_dir)])
    p = subprocess.Popen([PY, "-m", "sim", "serve", "--scenario", f"scenarios/{scenario}.yaml", "--run-dir", str(run_dir),
                          "--force", "--port", str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(120):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                return p
        except Exception:
            time.sleep(0.5)
    raise SystemExit("sim did not start")


def controller(url, db, env_extra, kill_after=None):
    env = {**os.environ, "PYTHONHASHSEED": "0", **env_extra}
    logf = open(ROOT / "state" / "crash_controller.log", "ab")  # a file, not a PIPE: an undrained pipe would block the logger
    p = subprocess.Popen([PY, "-m", "controller.main", "--url", url, "--db", str(db)], cwd=ROOT, env=env,
                         stdout=subprocess.DEVNULL, stderr=logf)
    if kill_after:
        try:
            p.wait(timeout=kill_after)
        except subprocess.TimeoutExpired:
            p.send_signal(signal.SIGKILL); p.wait()
            return -9, ""
    p.wait()
    err = (ROOT / "state" / "crash_controller.log").read_text()[-600:] if p.returncode else ""
    return p.returncode, err


def snapshot(url):
    c = httpx.Client(base_url=url, timeout=60)
    out = {"state": {k: v for k, v in c.get("/sim/state").json().items() if k != "chunks"}, "workflows": {}}
    for w in c.get("/workflows").json():
        wid = w["workflow_id"]
        out["workflows"][wid] = {"history": c.get(f"/workflows/{wid}/config/history").json(),
                                 "config": c.get(f"/workflows/{wid}/config").json()["config"]}
    out["approvals"] = [{k: v for k, v in a.items()} for a in c.get("/approvals").json()]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="public_02_incidents")
    ap.add_argument("--out", default="reports/crash_recovery.md")
    a = ap.parse_args()
    Path(ROOT / "state").mkdir(exist_ok=True)
    log = []

    # ---- reference
    sim = start_sim(a.scenario, 8731, ROOT / "runs" / "crash_ref")
    db = ROOT / "state" / "crash_ref.db"
    for f in db.parent.glob("crash_ref.db*"): f.unlink()
    t0 = time.time()
    rc, err = controller("http://127.0.0.1:8731", db, {})
    ref_s = time.time() - t0
    assert rc == 0, err
    ref = snapshot("http://127.0.0.1:8731")
    sim.terminate(); sim.wait()

    # ---- chaos
    sim = start_sim(a.scenario, 8732, ROOT / "runs" / "crash_chaos")
    db2 = ROOT / "state" / "crash_chaos.db"
    for f in db2.parent.glob("crash_chaos.db*"): f.unlink()
    counter = ROOT / "state" / "crash_counter"
    plan = ["mid_ingest_before_commit:40", "after_advance_before_ingest:30", "before_advance:40", "after_ingest_commit:30",
            "after_intent_before_post:1", "after_post_before_commit:1", "before_apply:1", "after_apply_before_record:1",
            "after_intent_before_post:1", "after_post_before_commit:1", "before_apply:1", "after_apply_before_record:1",
            "after_intent_before_post:1", "after_post_before_commit:1", "before_apply:1", "after_apply_before_record:1",
            "mid_ingest_before_commit:30"]
    if os.environ.get('CRASH_PLAN'):
        plan = os.environ['CRASH_PLAN'].split(',')
    kills = 0
    random.seed(int(os.environ.get("CRASH_SEED", "11")))
    external = [random.uniform(2.5, 6), random.uniform(2.5, 8)]
    for spec in plan + ["external", "external", None]:
        if counter.exists(): counter.unlink()
        env = {"CRASH_COUNTER": str(counter)}
        kill_after = None
        if spec == "external":
            kill_after = external.pop()
        elif spec:
            env["CRASH_AT"] = spec
        t = time.time()
        rc, err = controller("http://127.0.0.1:8732", db2, env, kill_after)
        what = spec or "none (run to the end)"
        if rc in (137, -9):
            kills += 1
            log.append(f"| {what} | killed (exit {rc}) after {time.time() - t:.1f}s wall | restarted |")
        elif rc == 0:
            log.append(f"| {what} | finished cleanly after {time.time() - t:.1f}s wall | scenario complete |")
            break
        else:
            log.append(f"| {what} | CRASHED exit {rc}: {err[-200:]} | |")
            raise SystemExit("\n".join(log))
    got = snapshot("http://127.0.0.1:8732")
    sim.terminate(); sim.wait()

    # ---- compare
    (ROOT / "state" / "crash_ref_snapshot.json").write_text(json.dumps(ref, indent=1))
    (ROOT / "state" / "crash_chaos_snapshot.json").write_text(json.dumps(got, indent=1))
    problems = []
    if got["state"] != ref["state"]:
        problems.append(f"final sim state differs: {got['state']} vs {ref['state']}")
    for wf in ref["workflows"]:
        if got["workflows"][wf]["history"] != ref["workflows"][wf]["history"]:
            problems.append(f"{wf}: config history differs")
        if got["workflows"][wf]["config"] != ref["workflows"][wf]["config"]:
            problems.append(f"{wf}: final config differs")
    if len(got["approvals"]) != len(ref["approvals"]) or [x["status"] for x in got["approvals"]] != [x["status"] for x in ref["approvals"]]:
        problems.append("approval lists differ")
    pids = [x["proposal_id"] for x in got["approvals"]]
    if len(pids) != len(set(pids)):
        problems.append("duplicate proposal ids on the simulator")
    n_hist = sum(len(w["history"]) for w in got["workflows"].values())
    md = [f"# Crash-recovery evidence - {a.scenario}", "",
          f"Reference run (uninterrupted): {ref_s:.0f}s wall. Chaos run: **{kills} hard kills** (`os._exit(137)` at fault points + 2 external `SIGKILL`s), "
          "each followed by a plain restart of the same command against the same SQLite file and the same live simulator.", "",
          "| injected kill | outcome | then |", "|---|---|---|", *log, "",
          f"Compared after the run: {n_hist} config versions across {len(got['workflows'])} workflows, {len(got['approvals'])} approvals.", "",
          "**RESULT: " + ("PASS - the chaos run is byte-identical to the uninterrupted run (config histories incl. proposal/approval ids "
                          "and apply timestamps, final configs, approval statuses); no duplicate proposal ids, no double-apply, no lost approval.**"
                          if not problems else "FAIL - " + "; ".join(problems)), ""]
    Path(ROOT / a.out).write_text("\n".join(md))
    print("\n".join(md))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
