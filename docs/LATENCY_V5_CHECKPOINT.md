# Axiom-Grid latency v5 — frozen checkpoint, not a 200 ms pass

## Outcome and exact tree

**NO-GO for the requested <200 ms loaded-error bound.** Final narrow ASGI reproduction still returns a legitimate missing-source 404 in **281.53 ms**, including **275.24 ms native extraction-executor backlog**. Status/auth/quota expectations remain unchanged. Parent owns serial integrated 100-client wire tests; none were run here.

- Baseline: `e2b9d4236fc067241318b5ed56f5c4f495761c41`, initially clean `council/latency-v5` at `/data/axiom-fifth/latency`.
- Rejected preflight + grounding experiment: `1e30fc3ae2c78a1e6f78dc41e87e69a75c93bd16`.
- **Final tested runtime: `d96ad2e905852841fc4fc80bfd6fe3ba34c5912c`**. This rolls back server preflight and removes its incompatible active tests. Both commits are needed if applying this history; do not integrate the rejected commit alone.
- Net runtime change: **only `kernel/core/grounding.py`**. New active focused tests: `kernel/tests/test_grounding_window_allocation.py`. New reproducible diagnostics: `docs/diagnostics/latency_v5_probe.py`, `latency_v5_grounding_ab.py`.
- `overlay/server.py` is byte-equal to baseline; admission, request_policy, stores, gateway, frontend, thresholds/load generators and `kernel/sidecar/isolated_ingest.py` are unchanged.

## Ownership and cumulative cycle ledger

The initial exclusive source declaration was server + isolated_ingest. Parent subsequently expressly authorized grounding.py after the profile and history audit. Isolated_ingest was inspected but never changed.

- Server: prior evidence-lane cycle **1**, preflight implementation **2**, explicit rollback **3**. Frozen at 3; rollback is counted, not hidden.
- Grounding: conservatively declared **4 prior** (bf89849, 55e41ac lint plus 92fbcbd bitvector and a770c02 pruning), parent accepted that ledger; this turn's single source edit is **5**. **No further grounding edits**, including cosmetic cleanup.
- New grounding test module: 1 source cycle. Rejected preflight test module: initial authoring 1, ownership/overload additions 2, deletion from active tests 3. Exact rejected file retained outside the active suite; no xfail.
- New diagnostic ASGI script: initial authoring 1, per-lane/denied-request instrumentation 2, unused-import cleanup 3. Grounding A/B script: 1. Existing test sources were not edited.
- Two implementation cycles total: experiment then server-only rollback, with an explicit parent checkpoint between them.

## Baselines frozen before runtime edits

Evidence directory: `/data/axiom-fifth/reviews/latency-evidence/`.

1. Six existing evidence-lane/isolation handoff tests: **6 passed** (`baseline-existing.log`).
2. Initial actual offline text extraction probe: 16 ASGI requests, 8 extraction contenders, baseline `e2b9`; native worker CPU near 50 ms in serial warm calls, executor delay as high as 294.27 ms; loop lag sample max 15.30 ms (`baseline.json`).
3. Updated baseline: 17 requests, adding one missing absolute source `/etc/passwd`. Real denied 404 total **305.90 ms**: admission acquisition **0.004 ms**, executor wait **294.05 ms**, native worker **5.27 ms**, thread CPU **0.57 ms** (`baseline2.json`). This is a real non-held workload and demonstrates hidden executor head-of-line delay, not a new HTTP expectation.
4. Controlled held-real-parser scheduling oracles: `/demo` and `/api/extract-document` both failed timely missing-source completion. Later baseline version also failed the proposed revalidation/IO-overload contracts; owner/expired/auth test passed: **4 failed / 1 passed** (`preflight-baseline2-failure.log`). These deliberate oracles are not wire benchmarks.
5. Grounding oracle baseline: **1 failed / 7 passed**. The failing allocation contract detects existing Counter.__and__ calls; equivalence/anchor tests already pass baseline (`grounding-baseline-failure.log`). This is a redundant-work oracle, not a pre-existing semantic correctness defect or arbitrary timing threshold.

## Causal attribution and its limits

### CPU/GIL and executor backlog: reproduced

The trusted benchmark fixture is `sample_memo_01.txt`; it does **not** invoke binary-process parsing. Profiling identifies `best_fuzzy_match`, string joins, Counter construction/intersection and bounded normalization as hot work. The serial profile records evidence publication around 2 ms; do not attribute the entire ~50 ms worker CPU to SQLite.

Eight baseline2 extraction workers consume **426.71 ms aggregate thread CPU** over a cohort whose maximum ASGI request time is **420.56 ms**. Final cohort: **340.45 ms thread CPU**, max **334.57 ms**. Four threads do not turn this largely Python CPU work into four cores of effective execution; these observations support GIL/CPU contention rather than a pure storage-wait explanation. They do not isolate scheduler jitter, cgroup throttling or every lock at 100 clients.

The final missing-source call remains **281.53 ms**, including **275.24 ms executor wait**, **0.58 ms worker wall**, **0.21 ms worker CPU**, and practically zero admission-gate wait. Its source is not uploaded, so no DocumentStore SQLite ownership lookup occurs. The demonstrated failure is executor FIFO behind CPU work; moving SQLite alone cannot fix it. Admission permits include worker+queue depth; `admission;dur=0` does not mean no native backlog.

Profile outputs include async-loop entries from diagnostic concurrency; profile cumulative times are not additive CPU accounting or trustworthy wall-time percentages. Thread_time and the separate single-thread intervention below are stronger CPU-cost evidence. Profiles themselves slow requests and are explicitly excluded from ordinary timing claims.

### Exact optimization retained, no cache

Grounding precomputes local normalized-character/nonempty-token length prefixes. Windows unable to meet the *same* truncated length upper bound are rejected before joining strings. Accepted candidates use the same character-multiset bound via an exact sum of minima instead of allocating Counter intersection results. The scan count still increments before pruning; 500-window cap, subsampling, original token offsets, first-tie ordering, Unicode normalization, truncation, fuzzy/semantic thresholds and BLOCK rules remain unchanged. No source, extraction, ownership or review cache was introduced.

An alternating **six-run, single-thread** intervention loads frozen baseline grounding source into a separate in-memory module and runs the same 12 real memo fields against identical chunks. Results match **methods, spans, pages and bbox exactly**. CPU ranges: baseline **21.96–22.51 ms**, retained candidate **16.82–17.40 ms**; medians **22.45 vs 16.96 ms** (`grounding-ab.json`). This is a small causal component-cost experiment without SQLite, HTTP, parser spawn or new provider. It is not a throughput/wire-tail speedup claim or a model-quality evaluation.

### Original 100-client observations retained

Original authoritative aggregate JSON inputs and hashes are recorded in `inherited-inputs.sha256`, runtime `b28d58a2a180d7dd32694d51efdaf7217d5dd2bc`:

- Python hostile error max **1802.058 ms**, app-to-headers max **19.984 ms**. Health wire max **1661.391 ms**, app max **7.175 ms**. Large pre-/post-policy/client/transport scheduling remains; aggregate maxima are **not paired requests**, so subtracting them is not a causal decomposition. We cannot distinguish HTTPX client CPU, socket/accept scheduling and pre-policy server event-loop delay from these producer aggregates.
- Python mixed-persona error max **3656.296 ms**. Native overall worst error **702.479 ms**, specifically hostile phase; native hostile app max **607.386 ms**, admission max **0**. Native validation 422 app errors are short; the long native hostile path is the worker-admitted missing-file 404. Those hostile jobs contain no successful document grounding, so the pure-hostile native tail is not proven to be fuzzy CPU. Its executor/path-resolution/native scheduling contributions at 100 clients remain unisolated.
- Final persona all-attempt P95 regresses **3450.862→6703.160 ms Python**, **3886.894→6321.868 ms native**, even while mixed worst errors improve **5462.032→3656.296** and **3994.946→595.296 ms** respectively. Do not pool distributions, call this overall speedup, or conflate app time with wire time.
- Native final persona admission P95 **5061.300 ms**, max **5381.847 ms**: a substantial queue component exists alongside CPU work. Faster early errors changing sequential persona arrival timing remains a scheduling hypothesis, not a controlled proof of the prior P95 regression. No request-level historic arrays exist here to reconstruct quantiles or correlate the worst wire error with a specific app span.
- Native metric snapshot records **4** 499s, while its eventual raw server log contains **120** completed 499 entries. That is a snapshot/drain boundary; server logging does not prove the native client received those headers. Do not claim only four requests eventually reached/completed ASGI from that snapshot.

We did not run full workloads or replace producer thresholds. Actual historic failures remain authoritative until parent remeasures the frozen integrated tree serially. A bounded 8-contender reproduction already exceeds 200 ms after optimization; there is no basis to certify 100-client worst-error latency.

## Rejected preflight experiment and retained regressions

The experiment uniformly routed source existence/ownership preflight through the existing bounded evidence lane, then re-resolved the original reference inside CPU admission to avoid stale expiry authorization. It did not remove process isolation, change auth/quota caps or introduce a cache. Its 17-call denied 404 improved to **10.24 ms** in one ASGI sample; invalid-response timing worsened **2.17→2.99 ms**. Both movements are retained (`candidate.json`); neither is the final runtime.

However, unchanged admission guards caught a real contract conflict: **12 passed / 2 failed** (`guards.log`):

- `test_saturated_extraction_does_not_resolve_or_read_document`: source resolver ran before extraction admission. The deliberate forbidden-resolver oracle produced a 500 instead of expected 503; not an observed natural production crash.
- `test_cancelled_waiter_keeps_capacity_until_real_worker_finishes`: the held resolver now owned evidence capacity, not extraction capacity, violating the existing guarantee/oracle.

Parent expressly rejected lane-aware test relaxation. Server was rolled back byte-for-byte, failing experimental tests removed rather than xfailed, and original guards rerun unchanged. **404 isolation while extraction capacity is held remains unresolved.** The rejected faster sample cannot be advertised as delivered performance.

## Final verification and reproducibility

**41 focused tests passed**, strict ResourceWarning and PytestUnraisableExceptionWarning enforced; one upstream Starlette/TestClient deprecation (`final-focused.log`). This overlaps earlier suites; counts are not additive. Coverage includes 400 cutoff examples, 250 Unicode preparation examples, 120 additional deterministic property examples, bitvector equivalence, repeated/empty/truncated/subsampled windows, source bbox/page and same-ID changed-text invalidation, evidence capacity/context/lifecycle, real spawned large handoff, preview/extraction admission, middleware status/auth posture and disconnect precedence. Lint E9/F and diff whitespace pass (`final-lint2.log`).

Exact test selection:

```
kernel/tests/test_grounding_window_allocation.py
kernel/tests/test_grounding_cutoff.py
kernel/tests/test_grounding_bitvector.py
kernel/tests/test_grounding.py
overlay/tests/test_evidence_lane.py
kernel/tests/test_isolation_handoff.py
overlay/tests/test_preview_admission.py
overlay/tests/test_extraction_admission.py
overlay/tests/test_request_policy_asgi.py
tests/test_disconnect_admission_race.py
```

From the isolated worktree, Python is `/data/axiom-third/venv/bin/python`; use a fresh `AXIOM_STATE_DIR` under `/tmp`. Tests used `AXIOM_GATEWAY_TEST_MODE=1`; no inference/provider was called. Diagnostics explicitly use real offline pack extraction with tier3 disabled; no mock model-quality claims. Set `AXIOM_EXTRACTION_ISOLATION=process` for the ASGI probe (the trusted text fixture still follows the existing text path).

```
PYTHONPATH=. /data/axiom-third/venv/bin/python docs/diagnostics/latency_v5_probe.py OUTPUT.json
PYTHONPATH=. /data/axiom-third/venv/bin/python docs/diagnostics/latency_v5_grounding_ab.py OUTPUT.json
```

Baseline/candidate raw JSON reports originally retained HEAD e2b9 while dirty source was under test; source manifests disambiguate them. `candidate-source.sha256` is the **rejected** preflight tree; `final.json` reports exact frozen d96ad2e. `grounding-ab.json` was taken at 1e30fc3, whose grounding bytes are identical to final d96ad2e.

The compact evidence projection has **67 rows**, grain `(run,label)`; no duplicates. A unique floating latency is not an ID. Missing extraction CPU/executor values mean routes did not use that lane, not zero. Warmup/profile entries are labelled and never pooled into error percentiles. `summary.json`, `probe-requests.csv` and `probe-profile.txt` retain validation; aggregation script is `/data/analysis/axiom_latency_v5_summary.py`.

## Final source hashes

```
22d0419672dee8c7e90a0b964618ca70243d4a05c1efd2fdbc26fbd376d57086  overlay/server.py (baseline exact)
5a866207b4db902162a8dd37f67f81300da437b2b2b3685c911123f1490588b6  kernel/core/grounding.py
e37a91d5bddb0f84e7941156eb3a6f3e86ec0453b0cc328e3fda95bc6967db14  kernel/sidecar/isolated_ingest.py (unchanged)
ff93701d51824bfb17044adf874d00349b3160bd57ea0677050c41e46f762150  overlay/admission.py (unchanged)
84265163e3cd1751c7679360131c1538e854653ae2111732376dc5f36485411a  overlay/request_policy.py (unchanged)
```

No additional source changes after freeze, no full load/broad suites on shared host, no real-human evaluation, exposed key use, network provider calls, push, merge or deploy. Intended-host, full-wire error tail and every prior persona regression remain release blockers, not hidden by this component optimization.
