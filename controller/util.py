"""Small helpers: IST sim-time parsing, canonical hashing, crash-injection hook."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os

D0 = dt.date(2027, 1, 4)  # simulated D0 (documented in docs/SIMULATOR.md)
_ORD0 = D0.toordinal()
_date_cache: dict[str, int] = {}


def ts_to_minute(ts: str) -> int:
    """'2027-01-04T08:15:00+05:30' -> minutes since D0 00:00 IST (negative for history). Hot path."""
    d = _date_cache.get(ts[:10])
    if d is None:
        d = (dt.date.fromisoformat(ts[:10]).toordinal() - _ORD0) * 1440
        _date_cache[ts[:10]] = d
    return d + int(ts[11:13]) * 60 + int(ts[14:16])


def minute_to_str(m: int) -> str:
    day, mod = divmod(int(m), 1440)
    return f"D{day} {mod // 60:02d}:{mod % 60:02d}"


def parse_when(s: str) -> int:
    """'D3 14:30' / 'D3T14:30' -> minute."""
    s = s.strip().replace("T", " ")
    day, hm = s.split()
    h, m = hm.split(":")
    return int(day.lstrip("Dd")) * 1440 + int(h) * 60 + int(m)


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def short_hash(obj, n: int = 10) -> str:
    return hashlib.sha1(canon(obj).encode()).hexdigest()[:n]


def maybe_crash(point: str) -> None:
    """Fault injection for the kill/restart evidence. CRASH_AT='point[:nth]' kills the process hard."""
    spec = os.environ.get("CRASH_AT")
    if not spec:
        return
    name, _, nth = spec.partition(":")
    if name != point:
        return
    nth = int(nth or 1)
    path = os.environ.get("CRASH_COUNTER", "/tmp/controller_crash_counter")
    try:
        n = int(open(path).read()) if os.path.exists(path) else 0
    except ValueError:
        n = 0
    n += 1
    open(path, "w").write(str(n))
    if n == nth:
        os._exit(137)
