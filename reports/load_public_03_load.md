# Load evidence - public_03_load (12 workflows, ~650k dials/day, 9,737,667 events incl. 7 days history)

Measured on the machine that also ran the simulator (so the numbers are conservative: the sim competed for CPU).

| metric | value |
|---|---|
| wall clock, whole run (5 simulated days + 7 days history ingest) | 123 s |
| wall clock per simulated day (incl. history amortised) | 25 s  (target: < 600 s) |
| ingest throughput (parse + aggregate + SQLite commit), live ticks | 105,850 events/s |
| history bootstrap (first cycle): events / time | 5,537,531 events / 36 s (153,418 events/s) |
| events ingested live | 4,200,136  (~840,027 per simulated day) |
| decision lag per 15-min tick (ingest + 12 workflows planning + governance), p50 / p95 / max (excl. the one-off bootstrap cycle) | 158 / 223 / 1133 ms |
| peak RSS of the controller | 409 MiB |
| decisions written to the audit store | 394 |

