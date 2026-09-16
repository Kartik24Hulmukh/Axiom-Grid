# Session 27: new hardening fixes; launch remains NO-GO

Verified 2026-09-16 UTC. Launch target: September 17–18, 2026.

**Do not merge or launch.** This continuation ran fresh tests, not just a status reread. Starting head `54618f7183058c88679a84d9c34e9c850d300409`; branch `harden/axiom-grid-v1-launch`; existing draft PR #32.

## Inputs and catalog reconciliation

Read and hashed the sole attached `axiom_grid_session26_status.md`. Its claim that an 80+ repository catalog was created cannot be substantiated from supplied inputs: `repos.md` is absent from the checked-out branch and GitHub main recursive tree (API response not truncated). The ZIP and Session 25 attachment mentioned in that document were not attached here. No catalog integration is claimed. Installed existing declared Python dependencies from PyPI to reproduce tests; exact versions are in evidence/session27/environment.txt. No invented catalog, new runtime connector, or licensing certification.

## Reproduced and fixed

1. **False-green audit gates:** new adversarial tests initially gave 10 failures / 15 passes. Missing report sections could throw, NaN/negative latency and empty samples could pass, status counters could conceal failures, harness errors and absent resource samples were not independently gated, and loaded fuzz latency was ignored. Hardened the gate and added 40 cases: **54 passed**. These gates now reject incomplete/non-finite/inconsistent evidence and any loaded fuzz error response >=200 ms. They do not establish production launch readiness on their own.
2. **Airgap context leaks sealed environment:** 7/7 new lifecycle tests failed. `SocketEgressInterceptor` restored socket functions but left KAIRO_SEALED/KAIRO_AIRGAP and proxy flags changed, silently suppressing subsequent JSONL traces. Restore the pre-context environment on normal/exception exit; nested contexts preserve the outer scope and pre-existing sealed flags remain sealed. No production sealed-mode enforcement was removed. **60 passed** across lifecycle, personalization, trace/receipt tests; **25 passed** across existing airgap + lifecycle tests. This interceptor remains process-global and is not certified for simultaneous overlapping contexts.

Atomic commits: `b981a54` (test gates) and `393cdfa` (airgap lifecycle). One implementation remediation cycle per module; under the five-cycle limit.

## Validation matrix

| Scope | Fresh result |
|---|---|
| Baseline focused kernel/overlay/packs/audit | 368 passed, 33.68 s |
| Final focused scope, ResourceWarning and unraisable warnings fatal | 408 passed, 28.92 s |
| Router/gateway fault-injection regressions | 48 passed, 0.86 s |
| Full suite before domain dependencies | 20 failed / 377 passed / 5 skipped; maxfail=20 |
| Full suite after dependency installation, before lifecycle fix | 20 failed / 836 passed / 17 skipped; maxfail=20 |
| Full suite after lifecycle fix | **20 failed / 1,358 passed / 28 skipped**, 45.40 s; maxfail=20 |
| Changed Python files, Ruff F checks | Pass |
| Real TCP launch audit, both runs | **FAIL** |
| Browser E2E | Local URL blocked by browser environment; not completed |
| Rust/native suites | Cargo unavailable; not run |

The final full-suite run progressed beyond the earlier trace/PII failures, which pass in targeted tests. Remaining failures include missing podcast/Whisper/embed dependencies, PDF ingestion, Excel recompute/CLI, and risk/security expectations. They require triage, not blanket relabeling as environment-only. Counts are early-stop results, not an exhaustive failure inventory. No tests were skipped or relaxed to obtain green.

## Real TCP benchmark deltas

5,240 recorded responses per run plus 300 abandoned sockets; 120 seeded synthetic clients, not actual humans. Health baseline is one client, burst is 100 clients: this is NOT 100x measured production demand. Baseline overlapped focused pytest and collection; final TCP run was isolated and had additional dependencies including headroom-ai. Deltas are descriptive, not causal performance improvements.

| Scenario | N | Baseline P50/P95/P99 ms | Final P50/P95/P99 ms | Baseline → final req/s |
|---|---:|---|---|---|
| health_1_client | 200 | 1.225 / 2.342 / 6.74 | 1.272 / 3.126 / 3.784 | 647.55 → 524.71 |
| health_100_clients | 1000 | 177.359 / 277.964 / 289.661 | 110.282 / 185.415 / 188.559 | 530.05 → 809.86 |
| fuzz_100_clients | 720 | 270.951 / 538.928 / 555.431 | 186.798 / 292.667 / 301.629 | 320.64 → 469.88 |
| extraction_queue_100_clients | 200 | 373.48 / 624.69 / 644.805 | 318.493 / 370.768 / 396.433 | 215.73 → 266.13 |
| synthetic_120_clients | 3000 | 227.031 / 2213.293 / 2853.375 | 111.204 / 1366.7 / 1846.223 | 201.93 → 311.5 |
| recovery | 120 | 2.277 / 5.531 / 47.829 | 2.026 / 3.072 / 4.703 | 210.17 → 332.47 |

Extraction admission: baseline **127×200 / 73×503 (36.5% shed)**; final **159×200 / 41×503 (20.5% shed)**. The 503s are bounded admission rejections, not demonstrated crashes. Do not remove backpressure or enlarge queues merely to pass.

Sampled RSS baseline **94.17–153.45 MiB**, final **120.13–181.81 MiB**. FDs **11→11**, then **12→11**. No unhandled-exception markers in either server log; all four probes 200 after load. Final graceful lifecycle completion **0.164 s** (exit -15 with completion marker). Post-load recovery max **91.578 ms**, but loaded fuzz max **325.498 ms**, P95 **292.667 ms**: the universal <200ms requirement fails. Short samples are not proof of zero socket/coroutine leaks or a 24h memory plateau.

## Melious live verification

Catalog returned 200 and all four target IDs were present. Ran four bounded completion requests with concurrency two and max_tokens=32 each (128 completion-token requested cap), using the supplied bearer credential only for the gateway. GLM-5.3 / GLM-5.3 Flash / Kimi K3 / Qwen 3.8 27B returned HTTP 200 with one choice each: **561.41 / 1825.11 / 2272.87 / 764.67 ms**. Provider-reported total tokens sum to **296**, completion tokens **122**. This is transport/catalog smoke evidence, NOT verified visible-answer quality: the inherited smoke script does not inspect content or finish_reason. Reasoning models can exhaust this small cap. No live 100-client provider torture or induced provider outage. Failover/429/5xx/budget checks use existing fault injection tests.

## Five-point council premortem

One agent applying three review lenses, not an independent council or recruited evaluator swarm.

| Vector / lens | Resolution and open gate |
|---|---|
| Founder: broken real journeys / false release claim | Fixed false-green evidence gates; full suite, browser journeys and actual human evaluation remain open. |
| Architect: worker starvation / overload | Bounded admission observed; 20.5% final burst shedding. Define accepted-load SLO and capacity/replica target before tuning. |
| Chaos: unhandled async exceptions | No markers across malformed input and abandonment workload. Loaded error recovery remains >200ms. |
| Architect: resource/state leaks | Fixed scoped environment leak suppressing traces; FD counts non-growing in short TCP runs. Coroutine census, 24h soak and multi-replica failures unverified. |
| Founder/security: gateway spend, exposed credentials | 48 fault-injection tests and bounded live smoke pass; production failover/answer-quality/telemetry export still unverified. Rotate both exposed credentials immediately. |

## Merge and release gates

Existing PR #32 was draft/open and five remote checks on the starting head were green. Those checks do NOT cover the full Definition of Done. Continue as a draft hardening checkpoint; no auto-merge. Secrets were not written to source, reports or Git configuration; supplied credentials were used transiently for authorized GitHub/gateway requests. They remain exposed in the user-provided task text and require revocation/rotation.

Required next: supply the actual repos.md; resolve the recorded full-suite failures in bounded module cycles; set burst admission/latency SLO and profile worker service time; run independent browser and real-human evaluation; perform coroutine census, 24h soak and multi-replica chaos; verify OTel exporter receipt and production model failover with rotated credentials. Launch is **NO-GO**.
