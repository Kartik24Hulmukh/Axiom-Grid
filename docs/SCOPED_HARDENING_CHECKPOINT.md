# Axiom-Grid scoped hardening — verified continuation checkpoint

**Decision: NO-GO for general availability and automatic merge.** This is a working local hardening checkpoint, not a completed production launch or evidence of traction.

## Exact state

- Prior checkpoint: `14aade432e4fbf54ad5a0164f2782c7d0ef134af`.
- Tested runtime and benchmark revision: `c2791a110253fbe997ab9a11e79b8bf692076b02` on `harden/axiom-grid-v1-launch`. Final documentation-only commit is identified by the delivery manifest.
- Read-only remote check: main remains `8f381cf219098d03c0ae2d440681ed59beeaf99a`; remote hardening remains `09b1c3c7e49619810e39ceda4bec6fbfebeb007f`, an ancestor of the saved continuation. No push, PR, merge or deployment was performed. Posted credentials were not used.

## Implemented

1. **Credential-scoped durable evidence.** Complete resolvable observations and closed refusals are published atomically to SQLite WAL. Full-key SHA256 namespaces replace truncated IDs. Source/review/trace reads cannot assign legacy unscoped records to an authenticated credential. Actual two-worker and restart tests exercise one shared local filesystem, not a distributed cluster.
2. **Actual owned upload workflow.** Browser binary upload → opaque owned reference → admitted parsing/extraction → retained source → human review. Authenticated clients can otherwise read only curated fixtures, not arbitrary repo/temp/state paths. Copies are private on tested Linux, quota-bounded, not encrypted at rest. Orphan cleanup is serialized with publishers; generated-reference collisions cannot delete committed copies.
3. **Review CAS and confidence feedback.** Unknown/out-of-scope IDs return 404; stale/wrong-field updates return 409; byte quota failures are atomic. GET review reload enables explicit retry. Human values never rewrite source observations and are not automatically re-grounded. Exact-source-value reviews calibrate future confidence only within their credential.
4. **Quality-gate refusal correctness.** A BLOCK verdict previously retained an EXACT method and could render as a fact. It now carries BLOCK; both API fields and preview actions refuse it. Real five-review feedback and an explicitly labelled gate-fault oracle verify refusal and cross-credential separation. Unresolved refusals do not invent source edges or poison valid document publication.
5. **Bounded async admission.** Per-loop round-robin waiting, global/per-credential caps, actual receive-side disconnect detection and native completion-owned permits. Cancelled waiters cannot release running capacity. No polling sleeps were introduced as a runtime workaround. Legitimate rate-limit backoff and bounded readiness/drain polling remain.
6. **Lifecycle/readiness.** Workers join before memory/evidence/upload stores close; atomic shutdown marker follows actual completion. Readiness probes durable connections. Cold schema migration is serialized; existing readiness tests now run the real lifespan instead of calling closed stores outside startup.
7. **Repeatable verification.** Native Node full workload, observed 1 versus 100 regular measured request concurrency, portable multi-worker CAS/restart probe, frozen offline semantic-model CI job and real browser upload/review/conflict/mobile tests. CI configuration is authored, not a claim of a completed remote CI run.

## Local verification (overlapping suites; do not add these totals)

| Verification | Result | Scope |
| --- | --- | --- |
| Exact local pre-push / strict resource-warning gate | **450 passed** | Runtime, kernel, corpus/concurrency and lint; not a load certification |
| Broad `kernel/tests packs tests` | **1,415 passed; 4 skipped** | Actual model2vec 0.9.0 and vendored weights; skips remain incomplete coverage |
| Frozen offline PDF semantic E2E | **12 passed**, also included in broad run | Real four-page PDF/paraphrase/citations; no hash fallback or weight download |
| Real Chromium regression suites | **9 local + 11 authenticated = 20 passed** | Includes two clearly labelled response-fuzz rendering oracles; the other journeys use actual backend responses |
| Additional refusal/store/orchestrator regressions | **16 passed** | Includes real scoped review feedback; overlaps other suites |
| Real two-worker, 100-way known-ID CAS, process replacement | **All scoped functional gates passed** | 1 winner; 99 conflicts; revision 1 persists; source unchanged; other credential denied |

The CAS probe is **not a latency pass**: P95 391.12 ms and max 401.84 ms exceed 200 ms.

Remaining broad skips: release-asset training dataset, unavailable required LibreOffice conversion path, missing PDF form fixture, absent cross-platform workflow. Installing declared DuckDB/tree-sitter/model2vec test dependencies enabled genuine tests rather than manufacturing fake fixtures or relaxing semantic gates.

## Five-point premortem resolution

| Failure vector | Remediation/evidence | Remaining gate |
| --- | --- | --- |
| Worker starvation / queue overload | Bounded fair async waiting; all 300 extraction burst calls complete | Queueing and full-load tail latency remain unacceptable |
| Abandoned tasks / exception ladders | Event-driven disconnect watcher; completion-owned permits; strict warning tests | Large-body/slow-client ingress and independent-host chaos still needed |
| Evidence leakage / worker-local source loss | Owned locators, scoped WAL snapshots, real second-worker/restart proof | Shared local volume only; not IAM, host failure or multi-node HA |
| Poison reviews / lost edits / fake facts | 404/409 CAS, UTF-8 review quota, repeat-edit UI, authoritative BLOCK refusal | Human review is not re-grounding or execution proof |
| State/memory/socket lifecycle | Bounded logical retention, private files, orphan recovery, worker-join/store-close marker | No 24-hour soak or worst-case body/parse memory proof |

These are single-agent premortem perspectives and concrete tests, **not an independently convened agent council or a recruited human swarm**. No failing gate was waived, relabelled or relaxed to obtain a release claim; remaining failures are checkpointed rather than an open-ended remediation loop.

## Stress-test decision

Every full workload schedules 4,500 timed calls (1,000 health; 600 hostile; 300 extraction; 2,400 sequential interactions from 120 script identities; 200 recovery) plus 120 deliberately abandoned TCP sessions. Those identities share a fixture credential and six cyclic behaviours; they are not people, 120 independent tenants or a comprehensive UX cohort.

- Extraction burst: **60/300 → 300/300 completed**.
- Final Python workload: **0 timed 5xx, 2 all-server capacity 503s, 2 client transport errors**. The 503s occur in the deliberate abandonment burst and are NOT excluded from the strict zero-5xx gate. Worst timed HTTP error: **4527.24 ms**.
- Final native full workload: all 4,500 timed statuses match, no timed 5xx or transport errors; worst timed HTTP error **4187.07 ms**. Therefore its loaded-error gate still fails.
- Same-revision native one-client reference passes its narrower timed diagnostic gates. Observed regular persona request concurrency is **1 versus 100**. This is a 100-fold client-load experiment, NOT a 100x capacity, throughput, adoption or production guarantee. The separate raw abandonment burst remains 120 in both runs.
- Final Python sampled RSS: **70.93–101.74 MiB**; descriptors **17 → 16**, with zero remaining sampled TCP sessions after bounded drain. No sampled ASGI/unretrieved-task/fatal-Python markers; worker-join and all-store-close lifecycle marker present. These are short-run observations, not a zero-leak theorem.

**All-response latency includes rejected work.** The candidate processes more extraction work than baseline; before/after percentiles are not an equal-successful-work speedup estimate. Nonexistent corrections intentionally change from baseline poison acceptance (200) to rejection (404). Native and HTTPX quantiles are never pooled. Earlier/intermediate failed runs and their exact revisions remain in evidence; only exact delivery revision results are used for current conclusions.

### Reconciled benchmark details

| Client / run | Phase | Calls | P50 ms | P95 ms | P99 ms | Calls/s | Timed 5xx | Transport errors |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Prior checkpoint | health | 1000 | 220.39 | 877.27 | 1324.04 | 308.53 | 0 | 0 |
| Prior checkpoint | hostile | 600 | 424.85 | 2434.27 | 3811.16 | 123.31 | 0 | 0 |
| Prior checkpoint | extraction_burst | 300 | 787.07 | 2354.81 | 2932.01 | 63.69 | 240 | 0 |
| Prior checkpoint | 120_synthetic_personas | 2400 | 988.91 | 3287.06 | 4148.99 | 69.11 | 390 | 0 |
| Prior checkpoint | post_abandon_recovery | 200 | 1370.66 | 2816.14 | 3002.66 | 60.26 | 0 | 0 |
| Delivery candidate | health | 1000 | 99.06 | 444.02 | 684.28 | 641.09 | 0 | 0 |
| Delivery candidate | hostile | 600 | 195.58 | 992.76 | 1229.23 | 320.14 | 0 | 0 |
| Delivery candidate | extraction_burst | 300 | 4651.12 | 4985.10 | 5063.47 | 21.29 | 0 | 0 |
| Delivery candidate | 120_synthetic_personas | 2400 | 2076.38 | 3206.14 | 3433.86 | 59.73 | 0 | 2 |
| Delivery candidate | post_abandon_recovery | 200 | 789.82 | 2003.92 | 2098.11 | 89.27 | 0 | 0 |
| Native prior | health | 1000 | 110.81 | 166.00 | 194.34 | 817.75 | 0 | 0 |
| Native prior | hostile | 600 | 154.71 | 245.54 | 296.81 | 604.97 | 0 | 0 |
| Native prior | extraction_burst | 300 | 539.74 | 2000.09 | 2107.96 | 95.97 | 261 | 0 |
| Native prior | 120_synthetic_personas | 2400 | 781.39 | 2946.89 | 3729.37 | 87.45 | 458 | 0 |
| Native prior | post_abandon_recovery | 200 | 914.58 | 1541.00 | 1558.03 | 83.31 | 0 | 0 |
| Native candidate | health | 1000 | 90.66 | 124.37 | 161.84 | 1006.58 | 0 | 0 |
| Native candidate | hostile | 600 | 95.44 | 426.57 | 454.73 | 687.58 | 0 | 0 |
| Native candidate | extraction_burst | 300 | 5057.94 | 5421.31 | 5551.61 | 18.66 | 0 | 0 |
| Native candidate | 120_synthetic_personas | 2400 | 2194.84 | 3960.99 | 4246.93 | 50.95 | 0 | 0 |
| Native candidate | post_abandon_recovery | 200 | 78.00 | 428.84 | 441.70 | 383.21 | 0 | 0 |
| Native 1-client reference | health | 1000 | 1.25 | 2.20 | 3.36 | 705.91 | 0 | 0 |
| Native 1-client reference | hostile | 600 | 2.69 | 4.48 | 6.07 | 325.93 | 0 | 0 |
| Native 1-client reference | extraction_burst | 300 | 54.16 | 65.96 | 75.65 | 19.38 | 0 | 0 |
| Native 1-client reference | 120_synthetic_personas | 2400 | 3.02 | 60.72 | 70.42 | 52.36 | 0 | 0 |
| Native 1-client reference | post_abandon_recovery | 200 | 1.76 | 5.55 | 18.69 | 261.69 | 0 | 0 |


The chart uses the five HTTPX P95 phase values only. CSV grain is one phase/run; its key is `(run, phase)`, not the profiler's coincidentally unique numeric columns. Error-max nulls mean no timed HTTP errors in that phase, never zero latency. Nested raw reports are not rectangular; profiler failures were resolved by validated phase/status flattening and profiling the 25-row CSV. Totals/phase quantile deltas are independently checked from raw JSON.

## Catalog/tool integration log

The attached repos.md supplied 247 GitHub URL entries. Retained relevant tools: pinned Playwright for actual browser workflows, checksum-verified Gitleaks v8.30.1, existing OpenTelemetry instrumentation and prior export-only Opik/Helicone adapters. Native HTTP/ASGI/SQLite/concurrent-future primitives avoid adding a second production framework. k6/xk6 were considered but not integrated; current loopback clients suffice to expose the red gate. Declared model2vec, networkx, DuckDB and tree-sitter dependencies restored real offline/broad test coverage; they are not new production SaaS connectors. No blind bulk installation, upstream plugin PR or live collector deployment is claimed.

## Security and release boundary

- Strict default-extended snapshot scan: **9 retained findings**, reviewed against prior triage as non-secret digest/identifier/fixture literals; no global checksum/test-word exemptions were restored. This is not a zero-findings claim.
- Full history: **12 findings**, including a historical Melious credential-shaped literal in `scripts/session21_melious_torture.py` at `ac1ad1f`. Its current validity/revocation was not tested. That commit is already an ancestor of public base `8f381cf`; the delivered incremental bundle excludes the public-base ancestry. Scanner on the new history delta reports zero findings. Reports are 100% redacted.
- Posted GitHub/Melious credentials were not used or repeated. Owner rotation/revocation and access audit remain necessary before remote/live testing.
- Authenticated legacy graph/figure/evaluation/compression aggregates fail closed with 501; legacy image paths return 404. Native desktop write/read-back remains unavailable. Traces are owned completed snapshots, not fabricated full span/collector proof.

## Definition of Done remains unmet

1. Sub-200-ms loaded wire-error recovery, zero all-server 5xx and zero client transport failures on independently reproduced final-SHA runs.
2. Worst-case large-body/slow-client admission budgets, adversarial multi-format parsing, long soak, cgroup memory limits, multi-node recovery and supported-platform clean installs/signing.
3. Complete skipped-asset/platform coverage and independent remote CI on the final PR SHA.
4. Rotated scoped credentials; bounded live catalog/quality/failover validation for the requested GLM/Kimi/Qwen model labels; production collector receipt. No live Melious model or model-quality claim is made.
5. Consented real-human trials and measured adoption/conversion/retention. No traction, revenue or 100x impact assertion can be derived from scripts.

The September–October launch is **gated, not delivered**. This checkpoint can be reviewed and applied locally; do not label or auto-merge it as a production release.
