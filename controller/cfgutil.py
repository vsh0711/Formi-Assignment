"""Config arithmetic mirroring docs/SIMULATOR.md section 3-4 (no sim imports): normalisation, diffs, total-variation."""
from __future__ import annotations

import copy

AGENT_DIMS = ["welcome_message", "voice", "caller_id"]
CHANGE_DIMS = ["cohorts", "welcome_message", "voice", "caller_id", "prompt_version", "schedule"]


def round_dist(d: dict, nd: int = 4) -> dict:
    """Normalise to sum 1, drop zero weights, round to nd decimals while keeping the sum exactly 1."""
    d = {k: float(v) for k, v in sorted(d.items()) if v and v > 0}   # sorted: sums/ties must not depend on dict or hash order
    s = sum(d.values())
    if s <= 0:
        raise ValueError("empty distribution")
    r = {k: round(v / s, nd) for k, v in d.items()}
    drift = round(1.0 - sum(r.values()), nd)
    if drift:
        kmax = max(r, key=lambda k: (r[k], k))
        r[kmax] = round(r[kmax] + drift, nd)
    return {k: v for k, v in r.items() if v > 0}


def dist(cfg: dict, cohort: str, dim: str) -> dict:
    return (cfg["allocations"].get(cohort) or {}).get(dim) or cfg["allocations"]["default"][dim]


def tv(a: dict, b: dict) -> float:
    return 0.5 * sum(abs(a.get(o, 0.0) - b.get(o, 0.0)) for o in set(a) | set(b))


def cohort_ids(cfg: dict) -> list[str]:
    return [c["id"] for c in cfg.get("cohorts", [])]


def changed_dims(old: dict, new: dict) -> list[str]:
    ch = set()
    if old.get("cohorts", []) != new.get("cohorts", []):
        ch.add("cohorts")
    keys = {"default"} | set(old["allocations"]) | set(new["allocations"])
    for dim in AGENT_DIMS:
        if any(tv(dist(old, k, dim), dist(new, k, dim)) > 1e-9 for k in keys):
            ch.add(dim)
    if old["prompt_version"] != new["prompt_version"]:
        ch.add("prompt_version")
    if _sched(old) != _sched(new):
        ch.add("schedule")
    return [d for d in CHANGE_DIMS if d in ch]


def _sched(cfg: dict) -> dict:
    s = cfg.get("schedule") or {}
    return {"hour_weights": {k: {str(h): float(w) for h, w in v.items()} for k, v in (s.get("hour_weights") or {}).items()},
            "lead_preferred_hour": {str(k): v for k, v in (s.get("lead_preferred_hour") or {}).items()}}


def max_shift(old: dict, new: dict) -> float:
    keys = {"default"} | set(cohort_ids(old)) | set(cohort_ids(new))
    return max((tv(dist(old, k, d), dist(new, k, d)) for k in keys for d in AGENT_DIMS), default=0.0)


def clean(cfg: dict) -> dict:
    """Canonical, API-valid copy of a config (round distributions, drop empty tables)."""
    out = copy.deepcopy(cfg)
    out.setdefault("cohorts", [])
    out.setdefault("schedule", {"hour_weights": {}, "lead_preferred_hour": {}})
    out["schedule"].setdefault("hour_weights", {})
    out["schedule"].setdefault("lead_preferred_hour", {})
    for k, dims in list(out["allocations"].items()):
        for d, w in list(dims.items()):
            dims[d] = round_dist(w)
        if not dims and k != "default":
            del out["allocations"][k]
    valid = set(cohort_ids(out))
    for k in list(out["allocations"]):
        if k != "default" and k not in valid:
            del out["allocations"][k]
    for k in list(out["schedule"]["hour_weights"]):
        if k != "default" and k not in valid:
            del out["schedule"]["hour_weights"][k]
    return out


def step_toward(live: dict, target: dict, cap: float) -> dict:
    """Move every agent-dim distribution from live toward target by one common fraction f so that the largest
    total-variation move is <= cap (strictly inside it). Non-allocation dims are taken from target as-is."""
    worst = max_shift(live, target)
    if worst <= cap * 0.98:
        return copy.deepcopy(target)
    f = (cap * 0.98) / worst
    out = copy.deepcopy(target)
    keys = {"default"} | set(cohort_ids(live)) | set(cohort_ids(target))
    for k in keys:
        for d in AGENT_DIMS:
            a, b = dist(live, k, d), dist(target, k, d)
            if tv(a, b) < 1e-9:
                continue
            mix = {o: a.get(o, 0.0) + f * (b.get(o, 0.0) - a.get(o, 0.0)) for o in set(a) | set(b)}
            if k in out["allocations"] or k == "default":
                out["allocations"].setdefault(k, {})[d] = round_dist(mix)
            else:
                out["allocations"][k] = {d: round_dist(mix)}
    return clean(out)
