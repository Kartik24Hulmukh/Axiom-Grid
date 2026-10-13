# Axiom-Grid parallel council — verified hardening checkpoint

**Decision: NO-GO for general availability, paid sensitive intake and automatic merge.** Final short load runs close the observed HTTP 5xx/transport gates, but do not meet the requested 200 ms loaded-error bound. This is a working local engineering checkpoint, not a production launch, human trial or traction claim.

## Exact state and authority

- Starting verified checkpoint: `4f3a822621ccfff843fa2f97a67dcd3ec1e80bb3` (its runtime was `c2791a1`). The attached ZIP SHA-256 matches the previous delivered artifact exactly.
- **Final tested runtime: `b28d58a2a180d7dd32694d51efdaf7217d5dd2bc`**, branch `harden/axiom-grid-v1-launch`. Final documentation-only delivery head is in the manifest.
- Fresh public read-only refs: main `8f381cf219098d03c0ae2d440681ed59beeaf99a`; remote hardening `09b1c3c7e49619810e39ceda4bec6fbfebeb007f`. No push, PR, merge, deployment, external live-provider call, outreach, grant submission or real-human recruitment was performed. Posted credentials were not used.
- Three coding agents worked concurrently in isolated Git worktrees: load/admission, gateway, UX/product redteam. An independent fourth founder/product agent reconciled the research and launch gates. This is an AI council, not four recruited specialists or 100 human evaluators.
- Eight original research Markdown files were recovered; two September 19 versions are exact duplicates. Research/source/input hashes are retained. Their competitor/legal/funding/model-era claims were not silently treated as current verified facts. The older eight-file replacement-source ZIP was not reapplied over the newer verified checkpoint.

## Implemented and integrated

1. **Evidence-I/O bulkhead.** Source reads, review CAS, trace reads and action-evidence lookup no longer wait in the document extraction executor. A separate four-worker default lane has completion-owned capacity, scoped ContextVar propagation, the same bounded/fair async gate and lifecycle join before state closure. Known storage failures and connected overload still fail honestly. A held-parser HTTP regression fails on baseline and passes after isolation; this is functional isolation proof, not a wire SLO.
2. **Native admission and queue telemetry.** O(1) pending/cancellation bookkeeping, coalesced completion wakeups, exact restoration and separate per-semaphore queues. `Server-Timing: app;dur=..., admission;dur=...` and structured `admission_wait_ms` distinguish gate wait from policy-to-headers time. Neither is wire latency, and admission time excludes native executor backlog. Global/per-tenant wait caps were not increased.
3. **Confirmed-disconnect race.** When a verified disconnect and AdmissionFull finish together, the caller is disconnected rather than a retry recipient. Connected overload remains 503; actual completed work and storage faults are not masked. Before proof: one failure/three passes; after: four passes. This change, not a threshold/status-expectation relaxation, explains the final 499 handling of aborted requests. It is not proof that queues never saturate or sent writes roll back.
4. **Gateway resilience.** Per-dispatch spend admission; reasoning-token lower bounds; bounded Retry-After/cooldown; connected-socket trickle deadline and explicit cancellation; sanitized exception chains; explicit bounded catalog GET and exact configured/reported model-ID checks. Actual loopback fault tests include 100 competing callers admitting one half-open HTTP recovery probe. No new provider/framework was blindly installed.
5. **Production-enabled tracing path.** Replaced tracing's BaseHTTPMiddleware stream/task ladder with pure ASGI. Actual SDK tests retain trace/log correlation and omit query/header/body/exception content; actual loopback OTLP HTTP/protobuf wire export is decoded and checked. This test receiver is not a deployed Collector, and SDK/exporter configuration remains an operator responsibility.
6. **Eight reproduced UI defects.** Fixed Forget-during-flight stale state/errors, hidden editor focus, keyboard tabs/dialog focus containment, CAS conflict baseline/reopen errors, old save closing a different new editor, and clipped mobile dialog. Real backend responses are paused for deterministic race tests, not fabricated as extraction evidence. Save remains reachable by scrolling at 320×480. Unsupported desktop writes remain refused.
7. **Catalog audit integration.** Added exact development-only axe-core 4.11.0 from the provided dequelabs/axe-core entry, MPL-2.0 with inspected license and committed npm integrity lock; lifecycle scripts disabled. No production bundle/exporter, cloud visual service or second browser framework was added. Existing pinned Playwright, checksum-verified Gitleaks and OpenTelemetry are retained.
8. **Release gates.** CI now includes the new load primitives/disconnect tests, 19-case owned-journey/axe suite, artifact preservation and independent native full load. Native diagnostics now check untimed all-server errors, actual joined shutdown and transport mismatches instead of reporting a narrower false green. CI configuration is authored; no remote CI run is claimed.

## Final verification — overlapping suites, not additive people/tests

| Gate | Exact local result | Boundary |
|---|---|---|
| Strict pre-push + runtime lint/resource warnings | **507 passed** | ResourceWarning/unraisable errors enforced; one upstream TestClient deprecation remains |
| Broad kernel/packs/tests | **1,466 passed; 4 skipped** | Actual model2vec 0.9.0 + vendored weights; no hash fallback |
| Frozen offline PDF semantic E2E | **12 passed**, included in broad | Real local PDF/paraphrase/source evidence; not live frontier quality |
| Original browser regression modes | **9 local + 11 authenticated passed** | Two executed XSS response-fuzz oracles explicitly labelled |
| New scoped UX/browser suite | **19 passed** | Three isolated empty/halted, proxy-HTML and timeout oracles; other tests are real backend/browser interactions |
| Shared-volume two-worker CAS/restart | **All scoped gates passed** | One winner/99 conflicts; revision 1 and source/upload persist across actual worker replacement |
| Distinct credential workflow probe | **100 actor workflows; 800 calls; functional gates passed** | Actual owned upload/extraction/source, other-scope 404, one CAS winner per actor, immutable source; scripts not people |

Four broad skips remain: release-asset training dataset, required LibreOffice conversion path, missing PDF-form fixture and absent cross-platform workflow. The machine has a local `soffice` wrapper; that is not evidence that the suite's required conversion path works. These are incomplete coverage, not a 100%-coverage pass.

The two-worker CAS latency is **not** a 200 ms pass: P95 348.50 ms, max 353.93 ms. The 100-credential probe similarly has worst HTTP error 2,016.90 ms. Its 100 winners/100 stale conflicts are legitimate CAS outcomes, not 100 people or calibrated model-quality votes.

## Matched load results — release bound still fails

Both final clients schedule **4,500 timed calls** at 100 configured clients, plus 120 deliberate raw TCP abandonments. Python and native distributions are independent; never pool them. Both final extraction bursts finish **300/300** with 200. All timed statuses match expectations and no timed transports fail.

| Client | Before all-server 5xx | Final all-server 5xx | Before transports | Final transports | Final worst HTTP error |
|---|---:|---:|---:|---:|---:|
| HTTPX/Python | 4 | 0 | 3 | 0 | **3,656.30 ms** |
| Native Node HTTP | 4 | 0 | 0 | 0 | **702.48 ms** |

The remaining strict loaded-error gate is false in both clients: requested **<200 ms**, not a revised percentile or app-only time. The final short runs observe no ASGI/unretrieved-task/fatal-Python markers; joined shutdown passes. These do not prove arbitrary-load zero crashes, 24-hour zero leaks or production recovery.

**Opposing movements must not be hidden:** Python hostile worst error grows 1,153.63→1,802.06 ms while mixed-persona worst error improves 5,462.03→3,656.30 ms. Native hostile grows 410.61→702.48 ms while mixed-persona improves 3,994.95→595.30 ms. Mixed-persona all-attempt P95 nevertheless worsens: HTTPX **3,450.86→6,703.16 ms**, native **3,886.89→6,321.87 ms**. Faster error paths change how scripts reach the expensive pipeline; this is a hypothesis, not isolated causal proof or an overall speedup claim.

One native regular-client reference has all short-run diagnostic gates green and worst HTTP error 10.17 ms. Observed regular persona-request peak is **1 versus 100**. This is a 100-fold client-load experiment, not 100x throughput, server capacity, humans, impact or adoption; the reference still includes a separate 120-session raw abandon burst.

Python RSS floor/ceiling: **70.26–95.05 MiB**; sampled FD range 17–225; sampled thread ceiling 11. FDs return to idle bounds after drain. Native diagnostics do not add a RAM/FD/soak certification. Host: Python 3.13.14, two reported CPUs, 4 GiB cgroup memory limit, local Linux.

**Historical evidence erratum (v5 audit):** the native metrics snapshot contained four 499s before drain, not four received final headers or only four eventual ASGI completions. The retained historical native server log contains 120 eventual 499 completion entries. Raw close attempts, snapshot counts and eventual application logs are distinct; no 116 successful-request inference is justified. See the current v5 report for its separate fresh run, which logged 112 eventual native 499s.

## Scenario, accessibility and human boundary

The independent UX matrix defines **120 distinct scenarios**: 54 have explicitly constrained partial/pre-edit/oracle evidence references; **66 remain proposed/unverified**. It does not say 54 whole journeys passed or 120 permutations were tested. Separately, the new credential probe executes 100 genuine credential partitions; its content/session variations remain automated fixtures, not real-world human diversity.

Axe-core on three real candidate states yields zero serious/critical **violations**, not zero findings: initial/processed have moderate heading/region violations; serious color-contrast **incomplete** nodes are 17 initial, 38 processed, 3 correction. Manual contrast, screen-reader and consented human evaluation remain. Baseline screenshots are post-remediation reconstructions of frozen 4f3a822 static assets; before-edit geometry/assertion failures were actually frozen. Screenshots are not falsely timestamped as before-edit captures.

## Five-point council premortem and unresolved gates

| Vector | Resolution/proof now | Still open |
|---|---|---|
| Starvation / overload | Bounded evidence bulkhead, fair/coalesced native admission, actual disconnect precedence | Loaded tails, slow-body/large-input ingress and intended-host scale |
| Gateway faults / billing | Real loopback trickle/cancel/429/5xx/catalog/probe tests; per-dispatch reserve/settle | DNS/pre-watchdog connect cannot be hard-interrupted; explicit cancellation needs caller wiring; missing usage/error billing may be unknown, ceiling remains heuristic not invoice cap |
| State leakage / rollback | 100 scoped workflows, two-worker restart, CAS/source immutability | Credential rotation changes hash namespace; IAM, migration/deletion/backup policy, multi-host HA and rollback drill |
| UI/assurance confusion | Eight reproduced defects, dev-only axe audits, honest native/refusal/receipt wording | Manual accessibility, actual recruited humans and independent recipient verification |
| Product/traction mismatch | Qualified buyer/pilot kit grounded in original research; archived readiness claims marked | Overlay review and separate signed export are not automatic every-action receipts; no paid demand, customer deployment, legal/compliance proof or native writes |

The gateway model catalog/quality for GLM-5.3, GLM-5.3 Flash, Kimi K3 and Qwen 3.8 27B remains **unverified**. Provider aliases cannot be silently translated into a verified-model claim. Live checks require rotated credentials, approved exact IDs, provider quota/spend controls and a bounded test plan; no production provider was hammered.

The founder review chooses truthful source-linked review or separate signed-observation export as a scoped buyer hypothesis. It includes a consented discovery invitation/interview/qualification sheet, teach-back/negative-verification exercises, seven P0/P1 acceptance gates, human evaluation and rollback/retention procedures. The $650 evaluation offer is a research hypothesis, not pricing validation, sales, LOIs or revenue. It is in `docs/FOUNDER_PILOT_QUALIFICATION.md`; no message/application/contract was sent.

## Convergence, retained failures and claim discipline

No failing runtime module exceeded five source-changing cycles. Admission: two agent runtime cycles + import-only integration + confirmed-disconnect cycle (four); gateway: three runtime cycles + import-only integration (four); new gateway test module: five; frontend: one runtime cycle, later screenshot/test evidence only. Evidence lane: one; tracing: implementation and lint-only second cycle. Native producer has two scoped accounting changes. No further runtime edit follows the final b28d58a freeze.

Retained: baseline defects, failed gateway cancellation/test-SQLite-lifetime iterations, wrong no-suggestion UX assumption, route-hold/screenshot harness corrections, malformed parent test selector, formatting dependency failure, original worse same-lane timing sample and intermediate 5583 load regressions. Successful commands are not inferred from stale tool handles during a brief sandbox infrastructure interruption; persisted final logs and exact runtime IDs are the evidence. Generated benchmark files written by broad tests were copied aside, then tracked baseline files restored before final load. Their synthetic reports are not launch performance evidence.

## Secret and delivery gates

- Strict default-extended runtime snapshot: **9 retained reviewed non-secret digest/identifier/fixture findings**, identical source-relative rules/lines/matches to previous triage. Scanner returns 1; this is not a zero-findings claim or a restored broad hash/test-word allowlist.
- New commit history delta from public base 8f381cf: **zero findings**, 100% redacted. Prior full history still contains a historical Melious credential-shaped literal at ac1ad1f, already an ancestor of public base. Validity/revocation was never tested; owner must revoke/rotate and audit historical/chat exposures. Public-base ancestral objects are excluded from delivered incremental bundle.
- No .git, virtualenv, node_modules, local runtime DB/WAL, private signing key, uploaded sensitive file or raw original research ZIP is included. The snapshot, incremental bundle, script, manifest/checksums, current/prior failures, raw benchmark reports, canonical chart, scenario matrix and reviews are included.
- Bundle is reconstructed in a fresh object database with its required public base and must match final delivery tree. No automatic merge/deploy instruction is supplied.

## Full phase metrics and analysis provenance

CSV grain is one phase/run (32 rows across six reports), key `(run, phase)`. Numeric columns that happen to be unique are not IDs. Twenty HTTP-error-max cells are null because their phases contain no timed HTTP errors; null is not zero latency. Timed 5xx is constant zero even in baseline while **untimed** baseline server 503s remain in separate counters. Nested raw dictionaries were not rectangular for the profiler (it prints an error but returns 0); validated phase/status projection was profiled separately. Counts and global error maxima were checked through independent direct JSON aggregation; percentile distributions are reported producer aggregates, not recomputed request-level observations. No pooled quantiles or fabricated interpolated samples.

| run | phase | requests | p50_ms | p95_ms | p99_ms | max_ms | http_error_max_ms | http_4xx | timed_5xx | transport_errors | successful_2xx | status_mismatches | throughput_rps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Python baseline | health | 1000 | 117.14 | 506.88 | 747.52 | 1151.99 | Not applicable | 0 | 0 | 0 | 1000 | 0 | 560.03 |
| Python baseline | hostile | 600 | 124.69 | 574.40 | 931.50 | 1153.63 | 1153.63 | 600 | 0 | 0 | 0 | 0 | 492.56 |
| Python baseline | extraction_burst | 300 | 5109.36 | 5429.93 | 5563.79 | 5721.40 | Not applicable | 0 | 0 | 0 | 300 | 0 | 18.70 |
| Python baseline | 120_synthetic_personas | 2400 | 2495.59 | 3450.86 | 3860.16 | 5993.24 | 5462.03 | 1200 | 0 | 3 | 1197 | 3 | 51.29 |
| Python baseline | post_abandon_recovery | 200 | 900.41 | 2146.96 | 2241.43 | 2383.66 | Not applicable | 0 | 0 | 0 | 200 | 0 | 81.37 |
| Python final | health | 1000 | 189.50 | 805.38 | 1113.11 | 1661.39 | Not applicable | 0 | 0 | 0 | 1000 | 0 | 362.23 |
| Python final | hostile | 600 | 214.57 | 761.95 | 1082.86 | 1802.06 | 1802.06 | 600 | 0 | 0 | 0 | 0 | 322.95 |
| Python final | extraction_burst | 300 | 5667.98 | 5922.92 | 5990.06 | 6067.69 | Not applicable | 0 | 0 | 0 | 300 | 0 | 17.21 |
| Python final | 120_synthetic_personas | 2400 | 74.54 | 6703.16 | 6823.18 | 7032.11 | 3656.30 | 1200 | 0 | 0 | 1200 | 0 | 46.06 |
| Python final | post_abandon_recovery | 200 | 742.94 | 2033.91 | 2210.35 | 2246.50 | Not applicable | 0 | 0 | 0 | 200 | 0 | 87.34 |
| Native baseline | health | 1000 | 70.17 | 85.78 | 88.01 | 91.17 | Not applicable | 0 | 0 | 0 | 1000 | 0 | 1351.36 |
| Native baseline | hostile | 600 | 78.64 | 332.89 | 397.94 | 410.61 | 410.61 | 600 | 0 | 0 | 0 | 0 | 836.88 |
| Native baseline | extraction_burst | 300 | 5166.71 | 5673.14 | 5724.11 | 5806.61 | Not applicable | 0 | 0 | 0 | 300 | 0 | 19.02 |
| Native baseline | 120_synthetic_personas | 2400 | 2061.81 | 3886.89 | 4133.65 | 4252.31 | 3994.95 | 1200 | 0 | 0 | 1200 | 0 | 52.19 |
| Native baseline | post_abandon_recovery | 200 | 409.63 | 509.72 | 535.73 | 537.90 | Not applicable | 0 | 0 | 0 | 200 | 0 | 238.48 |
| Native final | health | 1000 | 112.12 | 131.91 | 147.27 | 152.58 | Not applicable | 0 | 0 | 0 | 1000 | 0 | 849.54 |
| Native final | hostile | 600 | 141.41 | 618.79 | 653.56 | 702.48 | 702.48 | 600 | 0 | 0 | 0 | 0 | 483.35 |
| Native final | extraction_burst | 300 | 5318.05 | 5710.25 | 5784.33 | 5968.21 | Not applicable | 0 | 0 | 0 | 300 | 0 | 18.17 |
| Native final | 120_synthetic_personas | 2400 | 46.74 | 6321.87 | 6469.00 | 6698.99 | 595.30 | 1200 | 0 | 0 | 1200 | 0 | 49.10 |
| Native final | post_abandon_recovery | 200 | 111.70 | 344.94 | 439.31 | 442.93 | Not applicable | 0 | 0 | 0 | 200 | 0 | 439.44 |
| Native 1-client reference | health | 1000 | 1.61 | 2.24 | 3.26 | 11.87 | Not applicable | 0 | 0 | 0 | 1000 | 0 | 582.20 |
| Native 1-client reference | hostile | 600 | 2.07 | 3.18 | 4.29 | 10.17 | 10.17 | 600 | 0 | 0 | 0 | 0 | 421.93 |
| Native 1-client reference | extraction_burst | 300 | 41.53 | 57.58 | 62.47 | 184.75 | Not applicable | 0 | 0 | 0 | 300 | 0 | 22.29 |
| Native 1-client reference | 120_synthetic_personas | 2400 | 2.54 | 57.47 | 62.72 | 104.10 | 7.38 | 1200 | 0 | 0 | 1200 | 0 | 60.35 |
| Native 1-client reference | post_abandon_recovery | 200 | 1.12 | 9.27 | 25.84 | 61.88 | Not applicable | 0 | 0 | 0 | 200 | 0 | 404.02 |
| 100 credential workflows | owned_uploads | 100 | 149.20 | 197.04 | 201.50 | 201.79 | Not applicable | 0 | 0 | 0 | 100 | 0 | 458.12 |
| 100 credential workflows | extract_owned | 100 | 2575.36 | 4734.94 | 4925.98 | 4965.62 | Not applicable | 0 | 0 | 0 | 100 | 0 | 19.97 |
| 100 credential workflows | owner_source | 100 | 510.78 | 906.22 | 948.90 | 960.24 | Not applicable | 0 | 0 | 0 | 100 | 0 | 99.24 |
| 100 credential workflows | cross_partition_denial | 100 | 406.78 | 681.02 | 784.36 | 791.82 | 791.82 | 100 | 0 | 0 | 0 | 0 | 123.51 |
| 100 credential workflows | known_id_review_races | 200 | 695.00 | 1856.32 | 1950.66 | 2016.90 | 2016.90 | 100 | 0 | 0 | 100 | 0 | 95.25 |
| 100 credential workflows | read_review | 100 | 267.75 | 469.11 | 483.82 | 501.88 | Not applicable | 0 | 0 | 0 | 100 | 0 | 188.58 |
| 100 credential workflows | source_after_review | 100 | 210.56 | 356.46 | 375.29 | 375.86 | Not applicable | 0 | 0 | 0 | 100 | 0 | 247.22 |

