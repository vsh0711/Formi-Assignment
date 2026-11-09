# Load evidence - public_03_load (12 workflows, ~650k dials/day, 9,737,682 events incl. 7 days history)

Measured on the machine that also ran the simulator (so the numbers are conservative: the sim competed for CPU).

| metric | value |
|---|---|
| wall clock, whole run (5 simulated days + 7 days history ingest) | 129 s |
| wall clock per simulated day (incl. history amortised) | 26 s  (target: < 600 s) |
| ingest throughput (parse + aggregate + SQLite commit), live ticks | 101,097 events/s |
| history bootstrap (first cycle): events / time | 5,537,531 events / 39 s (143,791 events/s) |
| events ingested live | 4,200,151  (~840,030 per simulated day) |
| decision lag per 15-min tick (ingest + 12 workflows planning + governance), p50 / p95 / max (excl. the one-off bootstrap cycle) | 163 / 232 / 1236 ms |
| peak RSS of the controller | 402 MiB |
| decisions written to the audit store | 436 |

