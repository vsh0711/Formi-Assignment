"""HTTP client for the simulator with explicit retry semantics.

Reads are retried with backoff. Mutations are *not* blindly retried: `advance` is not idempotent, and the
governance endpoints are made idempotent by deterministic proposal ids + reconciliation (see governance.py).
"""
from __future__ import annotations

import logging
import time

import httpx

log = logging.getLogger("controller.sim")


class SimError(Exception):
    def __init__(self, status: int, code: str, detail):
        super().__init__(f"{status} {code}: {detail}")
        self.status, self.code, self.detail = status, code, detail


class SimUnavailable(Exception):
    pass


class Sim:
    def __init__(self, url: str, timeout: float = 300.0):
        self.c = httpx.Client(base_url=url.rstrip("/"), timeout=timeout)

    def _do(self, method: str, path: str, *, retry: bool, **kw):
        delay, last = 0.5, None
        for attempt in range(8 if retry else 1):
            try:
                r = self.c.request(method, path, **kw)
            except httpx.TransportError as e:  # connection refused / reset / timeout
                last = e
            else:
                if r.status_code >= 500 and retry:
                    last = SimError(r.status_code, "server_error", r.text[:200])
                elif r.status_code >= 400:
                    try:
                        body = r.json()
                    except ValueError:
                        body = {}
                    raise SimError(r.status_code, body.get("error", "http_error"), body.get("detail", r.text[:200]))
                else:
                    return r
            if attempt < (7 if retry else 0):
                log.warning("sim %s %s failed (%s); retry in %.1fs", method, path, last, delay)
                time.sleep(delay)
                delay = min(delay * 2, 15)
        if isinstance(last, SimError):
            raise last
        raise SimUnavailable(f"{method} {path}: {last}")

    def get(self, path: str, **kw):
        return self._do("GET", path, retry=True, **kw).json()

    def post(self, path: str, body: dict, *, retry: bool = False):
        return self._do("POST", path, retry=retry, json=body).json()

    def put(self, path: str, body: dict):
        return self._do("PUT", path, retry=False, json=body).json()

    # -- typed helpers
    def state(self) -> dict:
        return self.get("/sim/state")

    def advance(self, minutes: int) -> dict:
        return self.post("/sim/advance", {"minutes": minutes})

    def chunks(self, kind: str, after: int) -> list[dict]:
        return self.get("/events/chunks", params={"kind": kind, "after": after})

    def iter_chunk_lines(self, n: int):
        """Stream an NDJSON chunk without holding the whole body in memory."""
        with self.c.stream("GET", f"/events/chunks/{n}") as r:
            if r.status_code >= 400:
                raise SimError(r.status_code, "chunk_error", n)
            buf = b""
            for part in r.iter_bytes(1 << 20):
                buf += part
                lines = buf.split(b"\n")
                buf = lines.pop()
                yield from (ln for ln in lines if ln)
            if buf.strip():
                yield buf
