# Load evidence - public_03_load (12 workflows, ~650k dials/day, 9,737,703 events incl. 7 days history)

Measured on the machine that also ran the simulator (so the numbers are conservative: the sim competed for CPU).

| metric | value |
|---|---|
| wall clock, whole run (5 simulated days + 7 days history ingest) | 139 s |
| wall clock per simulated day (incl. history amortised) | 28 s  (target: < 600 s) |
| ingest throughput (parse + aggregate + SQLite commit), live ticks | 93,596 events/s |
| history bootstrap (first cycle): events / time | 5,537,531 events / 38 s (147,538 events/s) |
| events ingested live | 4,200,172  (~840,034 per simulated day) |
| decision lag per 15-min tick (ingest + 12 workflows planning + governance), p50 / p95 / max (excl. the one-off bootstrap cycle) | 171 / 275 / 1526 ms |
| peak RSS of the controller | 450 MiB |
| decisions written to the audit store | 474 |

