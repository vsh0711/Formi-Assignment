# Crash-recovery evidence - public_02_incidents

Reference run (uninterrupted): 15s wall. Chaos run: **18 hard kills** (`os._exit(137)` at fault points + 2 external `SIGKILL`s), each followed by a plain restart of the same command against the same SQLite file and the same live simulator.

| injected kill | outcome | then |
|---|---|---|
| mid_ingest_before_commit:40 | killed (exit 137) after 2.3s wall | restarted |
| after_advance_before_ingest:30 | killed (exit 137) after 0.5s wall | restarted |
| before_advance:40 | killed (exit 137) after 0.7s wall | restarted |
| after_ingest_commit:30 | killed (exit 137) after 0.7s wall | restarted |
| after_intent_before_post:1 | killed (exit 137) after 1.1s wall | restarted |
| after_post_before_commit:1 | killed (exit 137) after 0.2s wall | restarted |
| before_apply:1 | killed (exit 137) after 1.5s wall | restarted |
| after_apply_before_record:1 | killed (exit 137) after 0.2s wall | restarted |
| after_intent_before_post:1 | killed (exit 137) after 0.4s wall | restarted |
| after_post_before_commit:1 | killed (exit 137) after 0.2s wall | restarted |
| before_apply:1 | killed (exit 137) after 0.3s wall | restarted |
| after_apply_before_record:1 | killed (exit 137) after 0.2s wall | restarted |
| after_intent_before_post:1 | killed (exit 137) after 0.5s wall | restarted |
| after_post_before_commit:1 | killed (exit 137) after 0.2s wall | restarted |
| before_apply:1 | killed (exit 137) after 1.0s wall | restarted |
| after_apply_before_record:1 | killed (exit 137) after 0.2s wall | restarted |
| mid_ingest_before_commit:30 | killed (exit 137) after 0.7s wall | restarted |
| external | killed (exit -9) after 5.6s wall | restarted |
| external | finished cleanly after 2.7s wall | scenario complete |

Compared after the run: 25 config versions across 3 workflows, 7 approvals.

**RESULT: PASS - the chaos run is byte-identical to the uninterrupted run (config histories incl. proposal/approval ids and apply timestamps, final configs, approval statuses); no duplicate proposal ids, no double-apply, no lost approval.**
