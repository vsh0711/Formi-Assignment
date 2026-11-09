import json, re, sqlite3, sys
db_path, time_path, out = sys.argv[1:4]
db = sqlite3.connect(db_path)
t = open(time_path).read()
def grab(pat, default=None):
    m = re.search(pat, t)
    return m.group(1) if m else default
wall = grab(r"scenario finished in (\d+)s wall")
peak_b = grab(r"(\d+)\s+maximum resident set size") or (int(grab(r"Maximum resident set size \(kbytes\): (\d+)", 0)) * 1024)
events = json.loads(db.execute("select value from meta where key='events_total'").fetchone()[0])
rows = db.execute("select minute, value from metrics where name='ingest_events' order by minute").fetchall()
secs = dict(db.execute("select minute, value from metrics where name='ingest_s'").fetchall())
cyc_all = dict(db.execute("select minute, value from metrics where name='cycle_ms' ").fetchall())
first = rows[0][0]                       # the first cycle also ingests the 7 days of history (bootstrap)
boot_ev, boot_s, boot_ms = rows[0][1], secs[first], cyc_all[first]
ing = sum(v for m, v in rows[1:]); ing_s = sum(secs[m] for m, _ in rows[1:])
cyc = sorted(v for m, v in cyc_all.items() if m != first)
q = lambda p: cyc[int(p * (len(cyc) - 1))]
hist_ev = boot_ev
decisions = db.execute("select count(*) from decisions").fetchone()[0]
days = 5
L = [f"# Load evidence - public_03_load (12 workflows, ~650k dials/day, {events:,} events incl. 7 days history)", "",
     "Measured on the machine that also ran the simulator (so the numbers are conservative: the sim competed for CPU).", "",
     "| metric | value |", "|---|---|",
     f"| wall clock, whole run ({days} simulated days + 7 days history ingest) | {wall} s |",
     f"| wall clock per simulated day (incl. history amortised) | {int(wall)/days:.0f} s  (target: < 600 s) |",
     f"| ingest throughput (parse + aggregate + SQLite commit), live ticks | {ing / ing_s:,.0f} events/s |",
     f"| history bootstrap (first cycle): events / time | {int(boot_ev):,} events / {boot_s:.0f} s ({boot_ev / boot_s:,.0f} events/s) |",
     f"| events ingested live | {int(ing):,}  (~{int(ing) // days:,} per simulated day) |",
     f"| decision lag per 15-min tick (ingest + 12 workflows planning + governance), p50 / p95 / max (excl. the one-off bootstrap cycle) | {q(.5):.0f} / {q(.95):.0f} / {cyc[-1]:.0f} ms |",
     f"| peak RSS of the controller | {int(peak_b) / 2**20:,.0f} MiB |",
     f"| decisions written to the audit store | {decisions:,} |", ""]
open(out, "w").write("\n".join(L) + "\n")
print("\n".join(L))
