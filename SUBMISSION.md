# Outcome-First Agent Loop — Submission

**Name:** Vishalini S · **Date:** 2026-11-09 · **Hours actually spent (be honest):** 15hrs · **Language / storage:** Python 3.10+ (`httpx`, `pyyaml`; stdlib `sqlite3`) / one SQLite file in WAL mode

---

## 0. TL;DR
- A resumable service: every 15 simulated minutes it ingests events as counts, detects drift on populations, runs stratified always-valid welcome/voice experiments, balances caller IDs, answers hallucination incidents with a validated fix and rolls back decaying winners; every change goes through `/approvals` or a policy-permitted auto-apply and is explainable from our own SQLite store.
- Results vs no-op baseline: public_01 +4.8%, public_02 +18.2% conclusion rate (public_03 +11.2%); hallucinated calls on public_02 431 → 167, prompt incident fixed 330 min after the bad edit; harmful changes: 1 on public_01 (a fading W3 promotion, −3.0%), 0 on public_02.
- Reliability: 17–18 hard kills per run (fault-injected at write-ahead boundaries plus 2 external `SIGKILL`s) finish byte-identical to the uninterrupted run; decisions are identical across Python hash seeds.
- Scale: public_03 (≈650k dials/day, 12 workflows) takes 129 s wall for 5 simulated days including 7 days of history, p95 decision lag 232 ms, peak RSS 402 MiB.
- Deliberately not built: per-person call time, a UI, fair-share across tenants (C15), hierarchical shrinkage; history bootstrap and the supervisor view are partial.

---

## 1. Assumptions
1. **Levers map to the KPI they can causally move.** Pickup is decided *before* the customer hears the agent → `caller_id` and `schedule` serve the pickup KPI. Engagement is decided *after* pickup → `welcome_message`, `voice`, `prompt_version` serve it. So welcome/voice are only tested on workflows whose `primary` is engagement; on pickup-primary workflows (KYC) they are not touched (they could only hurt the guardrail). This halves exploration cost and is checked, not assumed, whenever both KPIs are measured per arm.
2. `guardrail: {<kpi>_max_drop: x}` is an **absolute** drop of that KPI versus its own past 8 days (`detect.guardrail_status`). Note that raising pickup mechanically dilutes engagement-per-connect (more marginal people answer): KYC engagement moves −0.6…−1.7% relative while pickup rises 7–19%; we watch it and alert, we do not "fix" it.
3. Sim time is truth. A decision is taken at each 15-minute tick; nothing in the controller reads a wall clock (this is what makes runs reproducible).
4. A supervisor edit **wins**: the controller keeps its hands off the edited dimension for 3 days (`HOLD_DAYS`), cancels experiments that depended on it, and never reverts it silently. The one exception is an unsafe prompt — handled through an approval with evidence and a notice (§7).
5. **Prompt changes are never exploratory.** There is no per-cohort prompt, so a prompt cannot be A/B tested concurrently; we change it only to fix a validated safety incident.
6. The automated hallucination flag is imperfect, so it is only ever used as a *rate against its own reference rate* (pre-change history of the same workflow), and a paid validation run is the arbiter before any action.
7. Schedule objective = **concluded leads per dial** (`eng/dials`, or `conn/dials` when pickup is primary). Per-hour weights are only meaningful *between* cohorts (a global table scales every lead equally), so a schedule always comes with a cohort partition.
8. Approvals are decided only inside `approver_hours`, after a random latency, expire at `proposal_ttl_hours` and must be applied within `apply_window_hours`; we poll every tick so the apply window is never the bottleneck.
9. The simulator's `max_requests_per_24h` counts *all* requests incl. rejected/expired; we mirror it locally and keep one slot in reserve for safety actions.
10. Only 7 days of history are ingested (older chunks are skipped by their `until_minute`) — enough for baselines (hour profile per cell, caller-ID pickup, flag reference rate) and what keeps a 14-day history from costing minutes.
11. One controller instance per simulator. State from another scenario / a restarted simulator is detected (`world` fingerprint) and moved aside, never resumed.
12. Auto-apply has no request cap in the policy; we still self-limit (30 min between steps for safety, 60 min otherwise, every step ≤ `max_shift`) and we require **earned autonomy** for customer-facing dimensions (§6).

## 2. Scope decisions
| # | Capability | Built / Partial / Cut | Why | What it would take to finish |
|---|---|---|---|---|
| C1 | Ingestion at load scale | **Built** | The whole loop is only as fresh as ingestion. Streaming NDJSON, per-chunk atomic commit with the cursor, `event_id` replay guard, counts-not-calls (O(cells) memory). | Shard by workflow across processes (§8). |
| C2 | One shared cohort object | **Built** | `controller/cohorts.py`: canonical content-derived ids, simulator's first-match semantics; used by experiments, schedule, detection, `/status`. A unit test pins the semantics. | — |
| C3 | Bootstrapping from history | **Partial** | History flows through the same ingest path (7 days) and seeds: hour×cell pickup (schedule), caller-ID health, hallucination reference, baseline engagement. Not used to pre-fit experiment effects (history has only the default variant — nothing to learn). | Cross-workflow priors once there are hundreds of workflows. |
| C4 | Call-time optimisation | **Partial** | Per-**cohort** hour weights chosen by 2-fold day-parity cross-validation (held-out gain LCB ≥ 1%). Per-**person** (`lead_preferred_hour`) is cut. | Per-person needs ≥2 connected observations per person; returning share is only 20–40% and the table is capped at 200k entries — low expected value vs. the cohort lever. |
| C5 | Caller-ID health | **Built** | Peer-relative detection (caller ID is randomised per call, so peers in the same ticks are an unconfounded control), bounded rotation, probe floor, recovery test, load-balancing by observed pickup. Worth the most lift in the public scenarios. | — |
| C6 | Welcome/voice experimentation | **Built** | Crossed (factorial) design, stratified estimator, mSPRT+Holm, harm/futility/decay arm-drops, segment tier with Holm. | Hierarchical shrinkage for segments (§12). |
| C7 | Winner promotion, decay, rollback | **Built** | **Staged** promotion (50/50, widened to 75/25 only after 24 h of confirmed lift); recency guards (36 h and 12 h); 18-h lift vs holdout every 3 h; rollback after 2 consecutive bad looks; autonomy revoked on rollback. | A time-since-exposure prior (§11). |
| C8 | Hallucination incidents | **Built** | detect (CUSUM) → confirm (validation) → last-known-good first, LLM only if needed → validated fix → approval → verify (flags + engagement canary + ranked fallback). | — |
| C9 | Governance client | **Built** | Full FSM, write-ahead intents, batching, approver-hours/TTL-aware slots, apply-immediately, stale re-plan, bounded auto-apply, earned autonomy. | — |
| C10 | Honest impact / affected / dry run | **Built** | See §6.4. Dry-run is a projection from randomised arm rates, labelled as such — the simulator cannot re-dial history. | — |
| C11 | Supervisor view | **Partial** | `GET /status` (one JSON screen: testing / winning / what we want from you / changed today / holds / autonomy). No UI. | A page over the same JSON. |
| C12 | Audit store | **Built** | `decisions` rows carry trigger, rule, the statistics snapshot and links to proposals; `python -m controller.explain`. Plus a per-call exposure archive for the IRDAI question. | — |
| C13 | Crash recovery, demonstrated | **Built** | `scripts/crash_test.py`, `tests/test_e2e.py`. | — |
| C14 | Observability of the loop | **Built** | `GET /metrics`, alert taxonomy (page / ticket), §10. | Prometheus exporter (same numbers). |
| C15 | Fair allocation across tenants | **Cut** | Credits are only spent on incidents (≤ 20–30 per incident, hard cap 60), approver attention is already per-workflow-capped by the simulator. A fair-share solver would optimise something that never binds at this scale. | Per-tenant credit budgets + weighted max-min when credits become scarce. |

**Principle:** build what a regulated client can *audit* and what protects them first (governance, incidents, rollback, crash safety), then the levers whose lift is large and cheaply verified (caller ID, call time), then experiments where statistics can honestly say "no winner". I cut capabilities whose benefit I could not verify with the data volume available (per-person timing, tiny segments) rather than ship them under-tested. I deliberately did **not** use a solver anywhere: every decision here has a closed form (bounded step toward a target, Holm, CUSUM), which is also what a 2 a.m. engineer can reason about.

## 3. Stakeholders
Claims were checked against the actual policies (`GET /workflows/{id}` → `governance`).

**Claims vs the enforced policy** (policy = the `governance` block of each workflow; "our runs" = counts from the controller's own store on public_01 / public_02):

| Memo | Claim | Verdict | What the policy says | What our runs did |
|---|---|---|---|---|
| 01 Sales | "Kestrel turned on auto-apply for everything" | **False** | `ks_cancel` auto-apply: `schedule, caller_id, welcome_message, voice` only, `max_shift` 0.2; never `prompt_version` or `cohorts` | public_02: the `ks_cancel` prompt fix went through an approval (apr_00004); `ks_cancel` auto steps 7 / 10 (public_01 / 02), all in allowed dims, 0 refused |
| 01 Sales | "Northwind is fine with auto-apply on KYC" | **False** | `nw_kyc` auto-apply `enabled: false`, no allowed dims | `nw_kyc`: 0 auto proposals; 3 approvals applied on public_01, 2 applied + 1 rejected on public_02 |
| 01 Sales | One blended lift score | **Contradicts the rules** | Each workflow has a `primary` KPI and a `guardrail`; the README forbids blending | Every table and `/status` report pickup, engagement and conclusion rate separately |
| 01 Sales | "Roll out the persuasive prompt wherever available" | **Unsafe** | Prompt changes need `validation_run_id` and a pass rate (`nw_renewal` ≥ 0.97) | No prompt is ever proposed without a validation run id; public_02 credits used 30 (3 validation runs, 0 LLM calls) |
| 02 Compliance | Timing and caller ID are covered by the signed policy | **True on renewal, false on KYC** | `nw_renewal` auto-apply: `schedule, caller_id`; `nw_kyc`: none | `nw_renewal` 3 / 4 auto steps (public_01 / 02); `nw_kyc` 0 |
| 02 Compliance | Approvers 10:00–19:00 (KYC 10:00–18:00) | **True** | `approver_hours` [10,19] and [10,18] | Requests are sent inside those hours; 0 lapsed, 0 expired |
| 04 Ops (Anita) | "Two requests a day, maximum" | **Not the policy** | `ks_cancel` `max_requests_per_24h` is **4** (renewal 3, KYC 2); 2/day is her preference | Honoured as a tenant preference; peak `ks_cancel` requests per 24 h: 1 on each scenario |
| 04 Ops (Anita) | "Never before 11:00" | **Not the policy** | `approver_hours` start at 10:00 | Honoured through `preferences.yaml` (earliest send 11:00), except safety fixes |
| 04 Ops (Anita) | "Tell me before a running campaign changes" | **Not enforced by the simulator** | `ks_cancel` `mid_flight: allowed`; there is no notify step in the API | Done by our notices feed: 60 min pre-announce for customer-facing auto-applies |
| 05 Product | "An expired proposal is a rejection" | **Wrong word, right behaviour** | `expired` (TTL) and `rejected` (approver) are different statuses | Both are re-planned from fresh data with a new id; 0 expired on both scenarios |
| 03 SRE, 06 CTO | Scale and "other memos are wrong" | **Engineering bar / hint** | No policy claim to falsify | Measured in §8; three false claims above (Sales ×2, Compliance ×1) plus Anita's 2/day |

### 01 — Sales (Nikhil)
- **Accepted:** never spam supervisors — requests are batched (one proposal can carry five changes), at most 1–2 routine requests/day/workflow; "speed" → safety fixes and caller-ID rotation are sent immediately and applied the tick they are approved.
- **Declined:** a *single blended lift score* (violates the README and Product's rule — we report pickup, engagement and conclusion rate separately); "winning by lunch → live for everyone by evening" (an always-valid test plus a 25% holdout is what keeps a fading variant from becoming a client incident; W3 in public_02 loses its lift after two days); rolling the "persuasive" prompt P4 out "wherever available" (its hallucination rate is 4× P1 and prompt changes need validation + a human).
- **Wrong against the policy:** "Kestrel auto-apply for everything" — it permits `schedule, caller_id, welcome_message, voice` only, each step ≤ `max_shift` 0.2, never `prompt_version` or `cohorts`. "Northwind is fine with auto-apply on KYC" — `nw_kyc.auto_apply.enabled = false`; and Northwind Compliance (memo 02) asks for the opposite.
- **Reply:** *Nikhil — for the summit I can show, per client, three separate numbers: pickup, engagement and leads concluded ÷ uploaded, each vs. its baseline, with the audit trail behind every change. A single blended score would hide exactly the trade-offs a BFSI buyer asks about, so I won't build it. On speed: safe levers (caller-ID, call-time) apply the moment they're approved; voice/welcome winners go live as soon as the statistics are honest and the client approves — earlier than that we'd be showing noise. Kestrel's policy allows auto-apply only on four dimensions and ≤20% shift per step; Northwind KYC has it switched off, so no push-through there. P4 is out: 4× the hallucination rate.*

### 02 — Compliance, Northwind (Meera)
- **Accepted:** (1) customer-facing changes (welcome, voice, script/prompt, cohorts) on Northwind **always** go through a named approval — the policy for `nw_renewal` only lets `schedule`/`caller_id` auto-apply and `nw_kyc` nothing at all, and our earned-autonomy ladder keeps welcome/voice at "ask a human" until a human-approved change on that dimension has been live ≥24 h without a rollback; (2) prompt changes carry `evidence.validation_run_id`; (3) 24-hour answer for the auditors: `explain --lead` (variant, config version, cohort, and the decision chain that made it live); (4) slow-and-right: control-heavy tests (50%), harm/futility/decay drops, holdout, rollback; (5) requests go out inside approver hours with a same-day decision guaranteed (safety fixes excepted — they must not wait).
- **Pushed back:** "caller-ID rotation is operational" — the caller ID *is* something a customer sees. We use that latitude only where the signed policy allows it (`nw_renewal`), the change is bounded, and every such change appears in the notices feed for the weekly summary.
- **Wrong against the policy:** her memo assumes timing/caller-ID are covered by the signed policy on *both* workflows. On `nw_kyc` auto-apply is disabled entirely, so even those go through approval there.
- **Reply:** *Meera — agreed on all five. Welcome, voice, script and cohort changes on Northwind never go live without a named approval; scripts carry validation evidence. One correction to the memo's premise: auto-apply is permitted on renewal only for timing and caller ID, and not at all on KYC, so on KYC those also wait for your approvers (10–18h, requests are sent inside that window). For IRDAI: for any lead we can show every call it received, which variant and config version it heard, and the decision that put that version live, in minutes. Every weekly summary will list the auto-applied timing/caller-ID changes.*

### 03 — Platform/SRE (Kabir)
- **Accepted:** kill/restart proof (`reports/crash_recovery_public_02.md`), idempotency end to end (deterministic proposal ids, write-ahead intents, 409 handling), actionable alerts (§10), no new stateful infra (one SQLite file; in prod swap the 5 SQL helpers for your Postgres), the 10-minute-per-sim-day target (§8), loop health without logs (`/metrics`).
- **Wrong against the policy:** none found. His 10-minute target is a ceiling we beat by ~20× (§8); his "no new stateful infra" is met with one SQLite file.
- **Pushback / honesty:** one controller per simulator/environment (SQLite is single-writer); at 10× the first thing to break is single-process ingest (§8), and I would shard by workflow before reaching for Redis.
- **Reply:** *Kabir — done: kill -9 at 17–18 points (mid-ingest, between "intent written" and "POST", between "POST" and "recorded", before/after apply) and external SIGKILLs: the run finishes byte-identical to the uninterrupted one, no double-apply, no lost approval. State is one SQLite file (WAL) — no Redis; if you want Postgres the storage layer is ~120 lines. Pages are only for client-visible harm or a blind/stuck loop, with the next step in the text; everything else is a ticket. One simulated day of the 650k-dials scenario takes seconds, not minutes; at 10× the first thing to go is single-process ingest — plan is sharding by workflow.*

### 04 — Ops supervisor, Kestrel (Anita)
- **Accepted:** ≤2 routine requests/day and never before 11:00 (`controller/preferences.yaml`, tenant-level, can only *tighten* policy); one batched request instead of five; "tell me before a running campaign changes" → customer-facing auto-applies are **pre-announced** in the notices feed 60 min before they happen (not for safety fixes); one screen (`/status`); her prompt edits are never reverted silently (hold + notice); and the "verbatim script" trap is closed by validation + an engagement canary + a ranked fallback (§7).
- **Pushed back / wrong against the policy:** her "2 requests a day" is a tenant preference inside the policy cap of 4/24h, not the policy itself; the policy cap is what the simulator enforces. A hallucinating prompt is the one thing that cannot wait for 11:00 or for a nicer slot, and it may use the reserved safety slot beyond her 2/day (the policy cap is 4/24h); she is told *why*, with the evidence, and nothing changes without her approver's yes.
- **Reply:** *Anita — your limits are in: at most two requests a day, never before 11:00, five changes → one request, and a heads-up an hour before anything customer-facing auto-applies. Your own prompt edits stay yours: the controller keeps off whatever you edit for three days. The only exception is a prompt whose flagged-answer rate shoots up and a fresh validation run confirms it's unsafe: then you get an immediate request (with the evidence) to go back to the last known-good prompt — never a verbatim-script one, and never applied without your approver's yes. One screen: /status.*

### 05 — Product (Tara)
- **Accepted (and where):** separate KPIs everywhere (grader tables, `/status`, guardrail monitor); one cohort object (`cohorts.py`) with one id for "seniors in Tamil"; **minimum cohort size & evaluation window picked**: 250 connected calls per arm (pooled), 200 per arm-and-cell (segments), evaluated every 3 h with always-valid p-values — the cost is speed (a +10% relative lift needs ~2–3 days at 1,000 connected calls/day) in exchange for a fixed 5% false-winner budget; proposals ranked by `impact_score` with a documented formula (§6.4); an expired proposal is a rejection and is **re-planned from fresh data** (new id), never resubmitted; only calls that actually carried a variant are evidence (counts come from call events, an arm that never ran has n=0 and cannot win); a winner updates that workflow only.
- **Cut / sequenced:** per-person call time (see C4 — I would not put it on a summit slide on this evidence); supervisor view is JSON, not a UI.
- **Wrong against the system:** "minimum cohort size … open question" is not fully open — a cohort smaller than ~200 connected calls per arm *cannot* be told apart from noise at these call volumes (§5); and an "affected leads" number for `next_campaign_only` workflows is the *next campaign's* size, not today's backlog.
- **Reply:** *Tara — definitions held: pickup, engagement and leads-concluded÷uploaded are never blended; a cohort is one object with one id used by detection, experiments and the supervisor view. My picks: 250 connected calls per arm to start judging, 200 per arm per cohort cell, a look every 3 hours with always-valid p-values and a 5% family-wise false-winner budget. The price is time: ~2–3 days for a +10% relative lift at 1,000 connected calls a day, and cohort-specific winners are only visible with several times that volume. Impact score = reach × conservative lift ÷ 10%. Per-person call time is out of this iteration; caller-ID health and the supervisor view are in.*

### 06 — CTO
- **Accepted:** explainable beats clever (no solver, no black box; every decision has a rule + stats snapshot); "best compute is no compute": the LLM is not called when the last known-good prompt validates (public_02: 0 LLM calls, 2 validation runs = 20 credits); scale honesty (§8); choose and say no (this table + §12).
- **Pushed back / wrong against the policy:** nothing declined; the "trust the contract over anyone's recollection" line was applied to memos 01–05: every claim was checked against the `governance` blocks and three were wrong (Sales ×2, Compliance ×1).
- **Reply:** *Aryamann — three things I chose not to build and why: per-person timing (not enough repeat observations to beat the cohort lever), fair-share across tenants (credits are only spent on incidents; no contention yet), a UI (the JSON is the contract). Credits: the LLM was called zero times on public_02 because the last known-good prompt validated first; validation is the arbiter for every alarm. First thing to break at 10×: single-process ingest — I'd shard by workflow; second: the per-tick HTTP fan-out. Both are in §8 with numbers.*

## 4. Architecture
Run: `./run.sh <SIM_URL>` (plain Python; Docker optional). Read: this file → `controller/main.py` (the loop) → `controller/governance.py` (the only code that changes a config). Tests: `python -m pytest -q tests` (20 tests).

```
 simulator (HTTP)                                         controller process (one loop, 15 simulated minutes per iteration)
 ┌───────────────┐   GET /events/chunks/{n} (stream)  ┌──────────────────────────────────────────────────────────────────┐
 │ events        │ ─────────────────────────────────▶ │ INGEST  controller/ingest.py                                     │
 │ /sim/advance  │                                    │   parse → delta of counts → ONE sqlite txn (+chunk cursor)       │
 │ /workflows    │                                    │   agg_cell(day,version,cohort,cell,dim,opt)  agg_arm6  agg_hour │
 │ /approvals    │                                    │   agg_tick(did,prompt,flags)  agg_day  leads  cfg_timeline       │
 │ /…/config     │                                    └───────────────┬──────────────────────────────────────────────────┘
 │ /llm  /valid. │                                                    │ in-memory mirror of the committed counts
 └───────▲───────┘                                    ┌───────────────▼──────────────────────────────────────────────────┐
         │                                            │ PLAN (pure, atomic txn, no HTTP)                                  │
         │ POST /approvals · PUT /config · apply      │   incident.py  caller-ID health · hallucination (CUSUM)           │
         │ POST /validation/runs · /llm/suggest-fixes │   experiments.py  welcome/voice: mSPRT+Holm, holdout, decay       │
         │                                            │   schedule.py  cohort hour weights (held-out CV gain)             │
         │                                            │        └──▶ plan(wf)  = DESIRED STATE, persisted                  │
         │                                            └───────────────┬──────────────────────────────────────────────────┘
         │                                            ┌───────────────▼──────────────────────────────────────────────────┐
         └──────────────────────────────────────────── │ GOVERN  controller/governance.py  (the only writer)               │
                                                      │   diff(plan, LIVE config) → route: auto-step | approval batch      │
                                                      │   proposals(FSM)  write-ahead intent → POST → pending → apply      │
                                                      └───────────────┬──────────────────────────────────────────────────┘
                                                      decisions · notices · alerts · credits · validations (AUDIT) ──▶ explain.py · status.py (/status /metrics)
```
**State and restart.** Everything is in one SQLite file: counts, plan, experiments, proposals (with their deterministic ids), incidents, audit. Loop order is chosen so a restart replays an uninterrupted iteration exactly: (1) drain unprocessed chunks by *listing* them after the stored cursor (never trusting the `advance` reply), (2) **reconcile in-flight proposals first** (re-send write-ahead intents, poll approvals, apply what was approved), (3) plan, (4) govern, (5) advance. Planning is one transaction, so an experiment row and its plan entry can never disagree after a kill. Statelessness where it matters: planners *recompute* their desires every look; the executor diffs against fresh live config, so stale bases, supervisor edits and rejections need no special state.

## 5. The learning loop
- **Cohorts.** Statistics are stored at the finest grain (the lead's 4 features = "cell") and per `(config version, cohort id)` **stratum**, so any cohort can be evaluated later without re-reading events. A cohort is a predicate over cells with a canonical id; membership follows the simulator's first-match rule. Cohort partitions never mix features within a workflow (`Experiments.partition_features`), so first-match membership stays disjoint. **Minimum size** is a statistics question: ≥200 connected calls per arm per cell for any cohort-level claim, ≥250 per arm pooled; cells below that are not evaluated. **Fragmentation** is limited three ways: single-feature splits only, ≤4 override cohorts, and a split must beat the pooled policy on held-out data (schedule) or survive Holm (experiments).
- **Experiment design.** Welcome and voice are sampled independently per call, so one crossed experiment estimates both main effects from the same calls (interaction is not assumed away — the promoted winners keep a holdout, which also catches a bad combination). Allocation is control-heavy (50%), candidates share the rest; harmful arms stop (always-valid p≤0.01 and lift≤−3pt), futile arms stop (90% upper bound below the 2% minimum lift), *fading* arms stop (last-36h lift significantly ≤0 while pooled lift>0). **Freed traffic returns to the incumbent, never to a surviving arm** (a survivor may itself be fading). Exploration vs exploitation: a fixed exploration budget until a pre-registered stop, then **staged exploitation**: 50/50 against the incumbent, widened to 75/25 only after 24 h of confirmed lift.
- **Deciding a winner.** Per arm: difference in engagement-among-connected, combined across strata with **sample-size (Mantel–Haenszel) weights** (inverse-variance weights depend on outcomes and inflated z on tiny cells — found and fixed in testing), mixture-SPRT always-valid p-value (running minimum stored), Holm across arms at α=0.05, plus: relative lift ≥ 2%, pickup guardrail UCB > −1pt, and a **recency guard** (last 36 h lift ≥ half, and last 12 h lift ≥ a quarter, of the pooled lift). Segments are a separate tier tested **once** at conclusion with Holm over the pre-registered family (single-feature levels) at α=0.05 plus a 5% practical-lift floor; harm to a segment vetoes a promotion on a looser, safety-first threshold (z≤−1.28 and drop≥2pt). Deterministic: same counts → same decision; no randomness anywhere in `stats.py`.
  **False-winner rate** (tests/test_controller.py): A/A, 3 arms vs control, looked at 120 times: family-wise false-winner rate measured **1.0%** over 1,500 A/A runs (budget 5%; the test asserts ≤ 8% to tolerate Monte-Carlo noise), where naive peeking (any z>1.96 at any look) gives **38.9%**. The rule is conservative by design — the price is the 2–3 days to detect a +10% lift. Segment tier: simulated null any-finding 2.9% (Holm), power at load-scale volumes ≈ 85%, at dev-scale ≈ 30%.
- **Decay and rollback.** After promotion, the last-18-h lift versus the holdout (50%, later 25%) is evaluated every 3 h from 6-hour buckets. Rollback after 2 consecutive looks with `lift ≤ −1pt & z≤−2` (harm) or `lift + 1.28se < 0.5 × promised lift` (decay); the arm is blacklisted and **autonomy for that dimension is revoked**. Typical reaction time ≈ 1 day (limited by holdout size; the staged 50% holdout makes the first day the most sensitive).
- **Call time and caller ID.** Call time: per-cohort hour weights from attempt-standardised, shrunk pickup rates; the partition feature is chosen by held-out gain (train on even days, score on odd, and vice versa; adopt only if the gain's lower confidence bound ≥ 1%; weights floored at 0.25 because an omitted hour is weight 0). Caller ID: because the ID is randomised per call, peers in the same ticks are an unconfounded control: a number is *degraded* when pickup is statistically (z≥3.5) and materially (≤0.6×) below its peers over 6 h → rotate away in bounded steps down to a 3% probe floor, re-test after 48 h; the slow path spreads traffic by observed health (χ² homogeneity p≤0.01, ≥8% spread) and probes unmeasured IDs at 5%. Loaded numbers lose pickup too, so merely spreading calls across IDs is itself a large lift (KYC +10–19% pickup).
- **Guardrail.** Per arm: pickup UCB gate before any promotion. Per workflow: `guardrail_status` every 6 h (48 h vs 8 days, absolute drop, z<−3) → ticket, or page at >1.5× the allowed drop.

## 6. Governance
### 6.1 Proposal lifecycle
```
 plan≠live ─▶ intent ──POST──▶ pending ──approver──▶ approved ──apply──▶ applied
                │  409 dup → link by listing /approvals     │  \                │  \
                ▼                                           │   └─▶ rejected     │   └─▶ lapsed(410)  ─▶ re-plan, new id, attempt+1
              failed(422)                                   └────▶ expired       └─▶ stale(409/base moved) ─▶ re-plan from fresh base
                                                 superseded: an urgent change replaced a routine pending request
```
Ids are `wf-v<base>-<hash(config)>-a<attempt>` — deterministic, so a retry after a crash is the *same* request (409 `duplicate_proposal_id` = "it already happened"). While an approval is in flight for a workflow **no other change is made** (any version bump, even our own auto-step, would stale it) — except a safety change that pre-empts a routine one.
### 6.2 Batching, timing, fatigue
One proposal per workflow carries every pending change. Routine requests go out only inside approver hours, only when a same-day decision is guaranteed (`now + max_latency ≤ approver end`) or in the first hour of the day, and respect `min(policy cap − 1 reserved, tenant preference)` per rolling 24 h (counting rejected/expired). Safety changes go immediately (the decision lands at the next approver tick anyway; night submissions are decided at opening time). Rejections back off by reason (judgement call: 3 h → 24 h → 48 h; urgent: 0/30/120/240 min); `expired` and `lapsed` are re-planned with fresh data, never re-sent.
### 6.3 Auto-apply — when and when not
Used only if `auto_apply.enabled`, every changed dim ∈ `allowed_dims`, and the move is cut into steps whose total-variation shift ≤ `max_shift` (`cfgutil.step_toward`, unit-tested to never exceed it). Voluntarily **not** used (even if allowed) for `welcome_message`/`voice`/`cohorts` until autonomy is earned: one human-approved change on that dimension live ≥24 h with no rollback (`autonomy` table, audit row `autonomy_granted`); revoked on any rollback. Safety actions (rotate away from a degraded number, revert) are exempt from the ladder. Tenants may ask for a pre-announce window (Kestrel: 60 min).
### 6.4 Impact, affected leads, dry run — and how honest they are
- **impact_score** ∈ [0,1] = max over the bundled changes of: *safety* `0.6+0.4×severity`; *exploration* `0.1×reach`; *performance* `reach × max(0, LCB relative lift)/0.10` (10% on all traffic = 1.0). Always a **lower bound**, so queue ranking is conservative.
- **affected_leads** = estimated leads still inside their cadence window in the affected cohorts (uploaded − concluded over the cadence window × cohort share); for `next_campaign_only` agent-facing changes it is the *next campaign's* size × share (the only leads the change can touch). Labelled as an estimate with its basis.
- **dry_run** = projection from the workflow's own randomised per-arm rates (current vs projected KPI, LCB, guardrail), the held-out CV gain for schedules, and the exposure budget for experiments. It says in the payload that it is *not* a counterfactual replay: the simulator cannot re-dial history, and pretending otherwise would be dishonest.
### 6.5 A supervisor edits mid-experiment
`config_changed(actor=supervisor)` → audit row; hold on exactly the edited dimensions (3 days); experiments on them closed `superseded_by_supervisor`; plan entries on them dropped; pending proposals go stale and are re-planned from the new base *including the supervisor's change*; a notice tells the client what we will and will not touch. In public_02, `nw_renewal` voice (D5 15:00) and `ks_cancel` prompt (D3 11:30) are both handled this way.

## 7. Incidents
**Caller ID (`ks_cancel` D2 10:00).** Detection: peer-relative pickup z≥3.5 *and* ratio ≤0.6 over 6 h, ≥60 dials. Expected false-positive rate: <1% per workflow-day on a null (unit test: 400 null trials, ≤1% flagged; power ≥95% for a 3× drop). Response: auto-apply steps ≤`max_shift` every 30 min to a 3% probe floor. Timeline (public_02, deterministic): flagged D2 10:00 → detected D2 15:15 (needs ≥60 dials per number in the 6-h window) → share of the bad number cut from 50% to the 3% probe floor within 45 min (day-2 share 25.7% → 3.1% from day 3).
**Hallucination (`ks_cancel` D3 11:30, supervisor ships P2).** Detection: Page's CUSUM on the flag rate vs the workflow's own pre-change reference (h=7.5, ≥100 connected calls); Monte-Carlo: P(false alarm per workflow per 30 days) ≈ 13%, median delay ≈ 2.3 h at 112 connected calls/hour (observed on public_02: 4.5 h after the edit, because the first hours are diluted by the old prompt's calls and the run needs ≥100 flagged-prompt calls). Because the alarm is only a *trigger*, a **paid validation run on the live prompt confirms it** (a clean run → "false alarm, no change", suppress 3 days — this is what turned an observed 13.6%-engagement-loss false switch in a stress scenario into 10 wasted credits). Then: last-known-good first (validated n=1000 against a safety gate: failure rate ≤1.5% and pass ≥ min+0.5pt, which also rejects P4's 2.75%); the LLM is called only if that fails, and then we take the *least restrictive* validated prompt (validation is blind to engagement and strict scripts lose callers); propose urgently with `evidence.validation_run_id` and a notice to the supervisor; **verify after apply**: the same CUSUM must stay quiet and engagement must not be significantly below the pre-incident level, otherwise fall back to the next validated candidate. Credits per incident: 20 (confirm + candidate), 10 for a dismissed false alarm, hard cap 60, floor 25 kept for other workflows.
Timeline (public_02, from `scripts/timeline.py`): D3 11:30 edit → 11:45 supervisor edit seen, hold placed → 16:00 CUSUM alarm, validation of live P2 pass_rate 0.939 (**unsafe**), P1 validated 0.990, `fix_chosen`, urgent proposal → 16:37 approved → 17:00 applied (60 min after detection) → 20:15 `fix_verified` (flag rate 0.98% vs 1.44% reference on 307 calls). Credits: 20; LLM calls: 0. (Later in the same run, D8 18:00, a CUSUM alarm on P1 was dismissed by a clean validation: 10 credits, no change.)

## 8. Scale
Measured on `public_03_load` (`scripts/loadtest.sh` → `reports/load_public_03_load.md`; sim and controller on the same machine):
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
**Why it is cheap:** the controller keeps counts, not calls. Per call ≈ 10 dict increments; per 15-minute tick the planners read ≈ 10³–10⁴ counters. **What breaks first at 10×** (6,500 workflows' worth is not 10×, but 120 workflows / 6.5M dials a day is): (1) *single-process ingest* — ≈ 100k events/s means ≈ 90 s of one core per simulated day at 1×, 15 min at 10×: shard workflows across N worker processes by hash (each owns its own SQLite file; the cursor is per-chunk-per-shard); (2) *HTTP fan-out* — `GET /config` ×3 per workflow per tick = 120×96×3 ≈ 35k calls/day: cache by `current_version` from the event stream; (3) *SQLite single writer* — move to Postgres once shards > 4; (4) *memory* — `lead→cell` is the only O(leads) structure (pruned to 6 days; ≈ 190k leads/day here), at 10× ≈ 1.2M leads in a hash map: move it to the shard's SQLite. Tenants partition cleanly (no cross-tenant state), which is the natural shard key.

## 9. Reliability
- **Crash recovery test** (`scripts/crash_test.py`, `reports/crash_recovery_public_02.md`): reference run vs. chaos run with hard kills injected via `os._exit(137)` at: mid-ingest before commit, after commit, after advance before ingest, before advance, after intent before POST, after POST before it is recorded, before apply, after apply before it is recorded — repeated three times — plus two external `SIGKILL`s at random wall times (three random seeds run). Result: **byte-identical** final config histories (incl. proposal ids, approval ids, apply timestamps), approval list and final configs. The test found four real bugs before it passed (a missing field in the auto-apply retry path; an auto-step cooldown that lived only in memory; compound writes that weren't atomic; planners running before reconciliation).
- **What is lost:** nothing durable. Known gap: a kill in the millisecond between a *paid* call (validation / LLM) returning and our DB write loses that one result; the API has no way to list runs, so it is paid again (≤ 10 credits).
- **Idempotency keys:** proposal ids (deterministic, attempt-numbered), `event_id` replay guard, chunk cursor committed with the data, deterministic cooldowns derived from the proposals table.
- **4xx/5xx:** reads retry with backoff (8 tries); mutations are *not* blindly retried: `advance` is never retried (we re-derive from `/sim/state` and list chunks), approvals/auto-apply are idempotent by id; 409 stale → re-plan; 410 lapsed → re-plan; 402 out of credits → page + never propose an unvalidated prompt; 403 auto-apply refused → ticket + falls back to approval path.
- **Determinism:** decisions are identical across PYTHONHASHSEED values (found and fixed: tie-breaks and rounding in distributions depended on dict order).

## 10. Audit & observability
Question: *"why did `ks_cancel` change at D3 17:30, who approved it, what happened next?"*
```
$ python -m controller.explain --db state/public_02_incidents.db --workflow ks_cancel --at D3T19:00
ks_cancel v8 at D3 17:00 by controller_approved  dims=['prompt_version']
  approval: named client approver (simulated approver) via /approvals
  proposal ks_cancel-v7-7d82de42dc-a0 (approval, attempt 0) -> applied
    summary: replace prompt P2 with P1: P2 is producing 3.04x the normal rate of flagged answers
    created D3 16:00, submitted D3 16:00, decided D3 16:37, approval apr_00004
    impact 0.842  affected_leads 3121
    slot: urgent: sent immediately (a safety fix must not wait for a nicer time slot)
    rationale: P2 flag rate 4.5% vs reference 1.5% over 467 calls; P1 validated at pass_rate 0.9900 [validation val_00002]
  because [incident_fix] replace prompt P2 with P1: P2 is producing 3.04x the normal rate of flagged answers  (decision #68)
  decision #68 D3 16:00 fix_chosen: replace P2 with P1 (validation val_00002 pass_rate 0.9900); credits spent 20.0  rule: last-known-good first; else least restrictive passing prompt
  decision #69 D3 16:00 proposal_submitted: replace prompt P2 with P1: P2 is producing 3.04x the normal rate of flagged answers  rule: governance batch (urgent: sent immediately (a safety fix must not
  decision #70 D3 17:00 approval_seen: approver said yes; applying immediately (apply window is short)  rule: poll /approvals
  decision #71 D3 17:00 applied: replace prompt P2 with P1: P2 is producing 3.04x the normal rate of flagged answers  rule: approved by client approver
  decision #73 D3 17:15 config_change_seen: v8 controller_approved changed ['prompt_version']  rule: event stream
  KPI 24h before: {'dials': 4800, 'pickup': 0.2402, 'engagement': 0.4692}   after: {'dials': 4800, 'pickup': 0.2325, 'engagement': 0.4848}
  next: D3 20:15 fix_verified -> incident closed: P1: flag rate 0.0098 vs reference 0.0144 on 307 calls; fix live 60 min after detection
```
Lead-level (IRDAI): `python -m controller.explain --db … --lead ks_cancel:l00012345 --archive state/exposure_archive` → every call, variant, config version, and why that version was live.
**Alerts — page:** `prompt_hallucination` (message says the controller is validating and what to check after 30 min), `fix_not_effective`, `no_safe_prompt`, `credits_low`, `sim_unreachable`, `malformed_proposal` (controller bug), `guardrail_breach` at >1.5× allowed. **Ticket (morning):** `caller_id_degraded`, `proposal_repeatedly_unapproved`, `approval_lapsed`, `approver_fatigue`, `auto_apply_refused`, `kpi_drift_*`. **Not alerts:** experiment looks, arm drops, rollbacks, rebalancing — they are decision rows. `GET /metrics`: ingest throughput, decision lag p50/p95/max per tick, decisions/sim-hour, credits remaining/spent, proposals by status, open alerts. `GET /status`: the Kestrel "one screen".

## 11. Results
### public_01_dev (`reports/public_01.md`)
| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.355 | +4.1% | 0.247 | +0.8% | 0.503 | +2.3% | 6% | 65 (57) |
| nw_kyc | 0.399 | +8.9% | 0.267 | +10.5% | 0.589 | -1.3% | 0% | 23 (21) |
| nw_renewal | 0.430 | +3.4% | 0.266 | +0.8% | 0.553 | +2.1% | 10% | 52 (54) |
| ALL | 0.390 | +4.8% | 0.257 | +2.6% | 0.538 | +1.7% | 6% | 140 (132) |

### public_02_incidents (`reports/public_02.md`)
| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.337 | +43.0% | 0.238 | +31.6% | 0.485 | +3.7% | 30% | 76 (348) |
| nw_kyc | 0.402 | +7.5% | 0.257 | +9.5% | 0.594 | -2.4% | 0% | 31 (29) |
| nw_renewal | 0.457 | +5.6% | 0.279 | +6.3% | 0.550 | -0.8% | 14% | 60 (54) |
| ALL | 0.391 | +18.2% | 0.256 | +16.6% | 0.530 | -0.4% | 21% | 167 (431) |

Harmful-change counts come from the "Changes applied" section of each report; public_03 (12 workflows, +11.2%) is summarised in §8 and `reports/public_03_load.md`.

**Reading them.** Conclusion rate is up on every scenario (+4.8% / +18.2% / +11.2% overall). The big movers are *pickup* levers: caller-ID health and spreading (ks_cancel +43% on public_02, KYC +9–30%); engagement levers add +2–7% on engagement-primary workflows (≈ 6–46% of the hidden engagement headroom, 19–21% on the two bigger scenarios). KYC (pickup-primary) shows engagement −1…−2% *relative* while pickup rises 9–30%: composition (more marginal callers answer), inside the absolute guardrail, and watched by `guardrail_status`.
**Where I was harmful:** one change on public_01 (nw_renewal W3 promotion, −3.0% expected engagement at apply time) and one on public_03 (nort_renewal_0 W3, −1.5%), none on public_02. Same mechanism both times: the variant's lift fades after ~2 days of exposure and the fade starts *after* the decision (at decision time the last-12h lift was still +0.10, so no data-driven guard could have seen it). Staged promotion (50/50 first, 75/25 only after 24 h of confirmed lift) cut the public_01 damage from −4.8% to −3.0% and the decay monitor (18-h window, every 3 h, two consecutive looks) rolled both back in ≈ 1 day. public_02: W3's share fell 44% → 5% → 0% on consecutive days. The adversarial `stress_a` scenario additionally shows the exploration cost (§13). **What I'd still change:** a time-since-first-exposure prior (effects in this domain fade) that caps any winner at 50% until it has survived ~4 days of exposure.
**Incidents on public_02:** caller ID flagged D2 10:00 → detected 15:15 → bad number's traffic share 25.7% (day 2) → 3.1% (day 3+); prompt P2 shipped D3 11:30 → alarm 16:00 → validated & proposed 16:00 → approved 16:37 → live 17:00: **time-to-fix 330 min** (270 min is detection volume at ≈112 connected calls/hour, 60 min the approver). Hallucinated calls 431 → 167. The same run contains the false-alarm path working as designed: D8 18:00 CUSUM alarm on P1 → validation clean (pass 0.990) → *no change*, 10 credits (30 total = 20 incident + 10 dismissed alarm; 0 LLM calls).

Also in `reports/`: `stress_a.md`, `stress_b.md` (synthetic scenarios with different truth/policy/incidents, so the public ones are not overfitted), `crash_recovery_public_0{1,2}.md`, `load_public_03_load.md`.

## 12. Trade-offs & rejected alternatives
| Option | Why considered | Why rejected / what instead |
|---|---|---|
| LP/MILP for allocation and proposal scheduling | "Optimisation" framing; fits constrained allocation | A point-estimate LP picks winners (violates "winner selection is statistical") and chases noise (optimiser's curse); with 2–3 arms the LP optimum is a vertex = "move to the winner". Approvals have 2–4 slots per day and random latency a MILP cannot control. Instead: closed-form bounded steps + a rules-based queue. |
| Thompson sampling / bandit allocation | Faster learning, less regret | Every allocation change is a governed change: approver latency (hours) and fatigue caps (2–4/day) make per-day adaptation the ceiling anyway. Fixed control-heavy design + always-valid stopping + arm drops gets most of the benefit and is explainable. |
| Inverse-variance pooling across strata | Standard, efficient | Weights depend on outcomes; inflated z on small cells (produced 3 harmful false cohort winners in testing). Replaced by sample-size (MH) weights. |
| Fixed-horizon tests | Simplest | Peeking is unavoidable (we look every 3 h); mSPRT makes it valid. |
| Hierarchical shrinkage for segments | Better power at small n | Simulated: lower power than Holm at the same false-finding rate for realistic n; more moving parts. Kept as future work. |
| Redis/Postgres/DuckDB | "Scale" | Kabir: no new stateful infra. One SQLite file + counters is enough for 1× and the shard plan is clear. |
| LLM first for prompt fixes | The README flow | Credits "where they change a decision": the last known-good prompt has *measured* engagement; the LLM is a fallback. |
| Engagement-only prompt reverts of supervisor edits | Anita's verbatim-script story | Not built: a prompt that hurts engagement without hallucinating would be proposed, not forced; left as a gap (§13). |
| Docker-first `run.sh` | Reproducibility | The grader gives a host URL; containers need host networking and Docker may be absent. Plain Python first, Dockerfile optional. |

## 13. Known weaknesses
1. **Exploration has a price and the grader's "harmful" label counts it.** Under an adversarial truth (a −15% arm, `scenarios/stress_a.yaml`) starting a test is labelled harmful (−3.3% expected engagement at the moment of the change). The 50% control share bounds it; it is not zero.
2. **Promotion right before a variant fades.** In public_01 the W3 lift series was +.096, .043, .055, .075 and the last-12h lift at decision time was still +.10; the fade starts after the decision, so no recency guard can see it. Staged promotion caps the damage (−3.0%, ≈1 day) but does not remove it; public_03 shows it once (−1.5%).
3. **Segment power at dev scale is low** (≈30%): cohort-specific winners are mostly invisible in 8-day, 1,000-call/day scenarios. Honest, but it leaves "engagement gap captured" low (≈6–20%).
4. **Approval-only workflows are slow**: one routine request per day (policy cap 2–4, one reserved) means a test, its arm drop and its conclusion each cost a day.
5. **Hallucination baseline is relative to the workflow's own history**: a prompt that was *always* bad is never flagged; a supervisor prompt that tanks engagement *without* hallucinating is not detected (no engagement regression detector for third-party prompt changes).
6. **"Least restrictive validated prompt" is an assumption** (strictness costs engagement); the engagement canary + ranked fallback is what protects us when it is wrong.
7. **Interaction between welcome and voice** is checked only through the holdout of the promoted combination.
8. **Single-process, single-writer.** One controller per environment; HA is "restart quickly" (state is durable), not active-active.
9. The `lead→cell` map and `agg_cell` are O(leads/day) and O(cells) respectively; no compaction of old days (fine for the scenario lengths).

## 14. If this went to production at Formi next month
1. **Day 1–2:** swap SQLite helpers for the existing Postgres; run in shadow mode (I would propose, never apply) on one tenant; wire `/metrics` into the existing monitoring and the page/ticket taxonomy into on-call.
2. **Day 3–4:** shard ingestion by workflow hash; cache workflow config by `current_version`; load-test at 10× with the simulator.
3. **Week 1:** replace the `preferences.yaml` stand-in with per-tenant policy read from the contract system; turn the exposure archive into a proper table with retention agreed with IRDAI.
4. **Week 2:** supervisor UI over `/status`; weekly summary generator from `notices`; engagement-regression detector for third-party prompt edits; per-tenant credit budgets (C15); then — only with real repeat-caller data — per-person call time.
