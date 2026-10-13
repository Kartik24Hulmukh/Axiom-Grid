# V8.3 extraction-capacity candidate: independent read-only review

## Verdict

The explicit-two-worker defect is confirmed by static inspection. Approve the narrow startup assignment plus range-validation candidate for parent review, **not** a latency fix or a demonstrated runtime success. Do not spend the reserved final server cycle until the parent has accepted a baseline actual-configuration oracle. Diagnostic 5/5 and installer 5/5 remain frozen; no tests, imports, workloads, credentials, network operations, or repository edits were performed.

## Scope and identity

The literal requested path `/data/axiom-integration31277e8` does not exist. The existing checkout `/data/axiom-integration` has HEAD `31277e8` and an empty `git status --short` at inspection. All source findings below refer to that matching checkout. Only this report was written. Review is static, not execution evidence.

## Concrete baseline oracle

- `docker/Dockerfile.overlay:32–35` and `deploy/docker-compose.prod.yml:20–23` explicitly configure extraction workers=2, pipeline concurrency=2, extraction queue depth=4, evidence workers=2. Compose limits are 2.0 CPUs and 768M (`:38–42`). Compose explicitly says not to derive these settings from host-visible CPUs (`:18–19`).
- `overlay/server.py:384–388` computes `max(4, int(env or 0) or min(32,(cpu_count or 2)*2))`. With explicit string `"2"`, the interior expression is 2, regardless of host CPU count; the outer floor deterministically returns **4**.
- Baseline effective configuration is consequently extraction executor=4 (`:389–391`), metadata executor=4 (`:396–399`), extraction permits/capacity=8 (`:406–408`), pipeline gate=2 (`:722–745`), evidence executor/permits=2 (`:414–420`). This is expression-level proof, not a captured live-process oracle.
- Candidate expected configuration is extraction executor=2, metadata executor=2, extraction permits/capacity=6; pipeline=2, evidence=2, queue depth=4 remain unchanged.
- Metadata is another stage of already admitted work, not an independent allocation of extraction permits. Neither 8 nor 6 is an HTTP ingress/request-total limit: AdmissionGate additionally supports bounded waiters.

The current deployment test (`tests/test_deployment_invariants.py:16–36`) checks manifest strings and resource limits, not actual server executor sizes. The live intake fixture sets extraction=2 (`tests/test_smoke_document_intake.py:29`) but its tests assert intake/ownership responses, not effective worker count. Thus those contracts can pass while the defect remains.

## Smallest candidate (not applied)

Replace only the extraction-worker assignment, add its startup validation **before** `_extraction_pool` construction, and narrowly correct the adjacent comment if needed:

```python
EXTRACTION_WORKERS = (
    int(os.environ["AXIOM_EXTRACTION_WORKERS"])
    if os.environ.get("AXIOM_EXTRACTION_WORKERS", "").strip()
    else max(4, min(32, (os.cpu_count() or 2) * 2))
)
if not 1 <= EXTRACTION_WORKERS <= 32:
    raise ValueError("AXIOM_EXTRACTION_WORKERS must be between 1 and 32")
```

This preserves the exact old automatic sizing expression for unset/empty input, treats whitespace-only input as blank per the requested policy, respects explicit 1..32 without a four-worker floor, and rejects zero/negative/>32 before constructing these executors. Noninteger input raises ValueError from int at startup; a uniform custom error for malformed input would require additional handling and is not needed for the minimal candidate. No helper, runtime environment parsing, queue/pipeline/evidence changes, or admission changes are required. Environment settings are startup settings; they are not re-read during lifespan restarts.

## Compatibility findings

An exact-variable search over the working tree, including hidden working-tree files but excluding `.git` and node_modules, found these consumers: Dockerfile, compose, server assignment/comment, the two tests above, `session24_torture.py` (8), `scripts/session21_local_stress.py` (4), `scripts/launch_tcp_audit.py` (8), and `docs/axiom/SESSION-021-LAUNCH-HARDENING.md` (configured-capacity restart promises). No documented/tested zero-as-auto usage was found. This is a working-tree finding, not proof about untracked external deployment environments or all historical commits.

Compatibility changes must still be acknowledged:

| Input | Existing behavior | Candidate behavior |
| --- | --- | --- |
| unset or empty string | automatic host default, floor 4/cap 32 | unchanged |
| whitespace-only | startup int conversion failure | automatic default (requested blank semantics) |
| 1, 2, 3 | silently floored to 4 | respected exactly |
| 4..32 | respected | unchanged |
| 0 (also padded zero) | automatic default | startup failure |
| negative | silently floored to 4 | startup failure |
| >32 | accepted, no explicit upper cap | startup failure |
| malformed integer / decimal | startup failure | startup failure |

If an external operator used 0 for automatic mode, they must unset the variable or leave it blank. Old accidental acceptance of negative or >32 is also intentionally removed. Python int syntax continues to accept surrounding whitespace, signs, and integer forms it previously accepted; strict decimal-only lexical parsing is outside this candidate.

Automatic sizing remains host-visible, not cgroup-aware. That known characteristic is preserved for compatibility; the explicit deployment value fixes this particular mismatch. New default discovery or resource-auto-tuning is outside scope.

## Independent candidate risks

1. **Lower throughput is possible.** Actual extraction threads fall from 4 to 2, and metadata threads from 4 to 2 through the unchanged derived formula. Work/metadata backlog may increase even if CPU contention decreases. No latency, p99, throughput, zero-5xx, or resource-containment improvement is established by this fix.
2. **Backpressure shifts.** Admitted extraction work falls from 8 to 6. Remaining traffic can wait in the unchanged bounded admission queues; shedding and deadline distribution may change. Do not expand queue depth or alter rejection/deadline semantics to compensate.
3. **External config compatibility.** Zero/negative/>32 become fail-start settings. No in-tree zero-auto contract was found, but external environments are unknown. Invalid startup should name the variable for diagnosability.
4. **Default remains CPU-count-based.** Explicit config is authoritative; this does not establish container-aware defaults or certify 768M memory safety.
5. **Restart and dependent sizing.** Lifespan recreates extraction/metadata/evidence executors using their configured constants (`overlay/server.py:180–192`), so the candidate must not introduce environment re-reading on restart. The metadata count change is an intended derived consequence, not an additional edit.
6. **Evidence must distinguish defect repair from optimization.** Manifest-only tests and prior successful intake are inadequate actual-configuration oracles. Avoid interpreting any difference in final-cycle SLO outcomes as a guaranteed benefit or moving the baseline to hide regressions.

## Frozen admission invariants

Keep all of the following unchanged:

- `_extraction_slots` and `_EXTRACTION_CAPACITY` are created from the same `EXTRACTION_WORKERS + _EXTRACTION_QUEUE_DEPTH` expression (`server.py:406–408`); only the input worker constant changes.
- `AdmissionGate()` remains the same scheduler (`server.py:689`, `overlay/admission.py`): max_waiters=192, per_tenant=96, keyed by loop and lane semaphore; round-robin tenants, FIFO within tenant, no newcomer bypass of existing waiters, bounded pending futures, cancellation unlink and simultaneous-grant cleanup.
- Permit.release remains lock-protected/idempotent, releases the lane semaphore once, and triggers the same coalesced loop wake (`admission.py:35–48,91–109`). Do not change wake scheduling/timing instrumentation.
- `_bounded_worker_call` acquires before submission, releases on submit failure, and attaches release to worker-future completion (`server.py:797–819`). Cancellation must not invent early release of running native work.
- `_document_call` retains exactly one completion-owned extraction permit across metadata resolution and CPU processing. Its composite future remains shielded from request cancellation, and release remains attached to composite terminal completion (`server.py:828–897`). Metadata can neither expand admission nor skip the CPU-stage ownership/path revalidation.
- Timeout/disconnect behavior remains unchanged (504/499), as do AdmissionFull 503 and Retry-After handling; no retry loops, new sleeps, early success, or swallowed errors.
- Evidence uses the unchanged separate executor/semaphore (2 under deployment config); pipeline gate remains 2. No borrowing of extraction permits, default-executor escape, or alteration of shutdown order.
- Shutdown continues to join metadata before extraction before evidence, then close durable stores; restart uses the configured constants (`server.py:180–208`).

Existing static references for scheduler behavior include `tests/test_load_admission_primitives.py` (coalesced wakes, cancellation/FIFO, timing and lane independence) and `tests/test_disconnect_admission_race.py`. They were inspected, not run.

## Parent pre-edit decision gate / reserved final cycle

Before editing, parent should approve the **actual configuration** baseline expectation: explicit 2/2/4/2 currently yields extraction=4, metadata=4, permits=8, pipeline=2, evidence=2. Ideally confirm from an already retained runtime oracle; none was generated here. A live oracle must observe the imported production assignment/executors and pristine semaphore capacity, not merely reimplement the expression or reread manifest text. Semaphore `_value` is capacity only at pristine startup/quiescence, never during active requests.

Recommended final-cycle coverage after parent acceptance (not executed here):

- Startup configuration matrix: explicit 1/2/3/4/32; unset/empty/whitespace; CPU defaults with None/1/2/high CPU counts; invalid 0/negative/noninteger/>32.
- Exact deployment oracle: extraction constant and pool `_max_workers`=2, metadata constant and pool `_max_workers`=2, pristine extraction slots and capacity=6; queue=4, pipeline gate=2, evidence pool/slots=2.
- Repeat lifespan recreation at the same configured worker counts, without runtime environment re-read or permit reset.
- Retain existing admission completion/cancellation/disconnect/lane-isolation contracts. More than six requests need not immediately 503: the separate bounded waiter mechanism is frozen.

No server cycle, diagnostic cycle, installer cycle, or workload was consumed by this review. Parent edit/review/testing remains outstanding.
