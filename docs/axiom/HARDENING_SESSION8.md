# Session 8 — gateway race fencing and launch checkpoint

Date: 2026-09-15. **NO-GO for enterprise/public launch; do not merge.**
Target: `harden/axiom-grid-prod`; audited origin `69300b5`, main `645595a`.
Existing release PR: https://github.com/Kartik24Hulmukh/Axiom-Grid/pull/19 (draft).

## What changed

Unlike Sessions 6/7, this increment does not touch signed oracle files. Their
claimed local commits are not in this fresh clone or the remote branch. The eager
oracle-import coupling remains an open dependency gate; changing it requires
maintainer re-signing, not bypassing the pinned signature test.

Three gateway concurrency root causes were reproduced before remediation:

1. An old successful response (including reasoning-budget exhaustion) closed a
   circuit that a newer concurrent failure had just opened. Per-circuit epochs
   now fence stale state transitions while still accounting valid response usage.
2. A cancelled half-open transport escaped ordinary Exception handling and left
   `probing=True` forever. Finally-based cleanup now reopens the circuit and
   returns its probe lease; cancellation still propagates, and inflight capacity
   is returned by the existing outer finally.
3. A retry waking from backoff bypassed a circuit opened by another request.
   Retry admission now rechecks epoch, OPEN state, cooldown, and remaining time.

Six new deterministic regression cases cover old success/budget responses,
old failures during another probe, cancellation, retry races, and 100 callers
contending for exactly one half-open probe. Events/barriers impose causal order;
no arbitrary sleeps or production mock paths were added. Test doubles inject
failures only at the existing transport boundary; they are not model validation.
Convergence: two implementation/test loops for this gateway component, below five.
State is still process-local: this is NOT distributed breaker/quota fencing.

## Verification and dependency audit

- Before change: 42 existing gateway tests passed in 1.83s.
- New reproductions: 3 failures (stale successes + cancellation), then a separate
  retry-admission failure. Raw failure logs retained.
- Final `python3 -m pytest kernel/tests overlay/tests -q --import-mode=importlib`:
  **200 passed in 13.49s**, including new regressions, gateway fuzzing, admission,
  probe and telemetry tests. This is not the full product suite.
- Ruff passed on all three changed Python files; `git diff --check` passed.
- Full-repo collection: **2,637 tests collected, 37 collection errors in 8.10s**.
  This host is missing domain dependencies including docx/openpyxl/pptx/duckdb.
  Do not interpret collection as executed test passes. Full integration/E2E,
  desktop/Rust/platform matrix and supported embed-anything/ONNX stack remain unverified.
- `pip check`: no broken requirements among installed packages; this does NOT
  mean all required product dependencies were installed. Exact environment saved.
- Existing JSON stdout logging, W3C trace continuation, `/healthz` and `/readyz`
  were exercised locally through overlay tests. No collector deployment or
  production telemetry/alert proof was performed.

## Measured benchmarks — scope matters

### Real local HTTP extraction: 1,000 requests, 100 clients, one worker

| Metric | Observed |
|---|---:|
| 200 / 422 / 404 / capacity-503 | 50 / 100 / 2 / 848 |
| Successful extractions / all requests | **5.0%** |
| Successful extractions / 800 valid input attempts | **6.25%** |
| All-response P50 / P95 / P99 | 1,027.79 / 2,205.33 / 8,036.21 ms |
| Successful P50 / P95 / P99 | 7,480.59 / 8,559.07 / 8,660.89 ms |
| Total / successful throughput | 54.33 / 2.72 req/s |
| Sampled server RSS floor / peak | 77.57 / 109.11 MiB |
| Unexpected HTTP outcomes | 0 |
| Health after / shutdown | healthy / 0.214s, SIGTERM exit -15 |

Capacity still fails the inherited >=50% success gate. Zero unexpected HTTP
outcomes is not evidence of zero internal panics, nor does accepted load shedding
prove usable 100x capacity. This harness suppresses server output; do not infer
absence of internal errors from that. No extraction remediation was made here.

### Router bookkeeping comparison: baseline vs candidate

20,000 calls/run, deterministic in-process transport, 100 executor workers,
three fresh processes per revision. Medians of run-level statistics follow;
these are NOT pooled percentiles or end-to-end model/API latency.

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| P50 ms | 0.0237 | 0.0831 | +250.63% |
| P95 ms | 11.2834 | 11.6083 | +2.88% |
| P99 ms | 18.6703 | 32.0402 | +71.61% |
| Throughput req/s | 16,258.57 | 14,299.50 | -12.05% |
| Sampled process RSS envelope MiB | 24.52–62.06 | 24.58–63.05 | see raw runs |

Every 100-worker run completed 20,000/20,000 without router/unexpected exceptions;
FD count stayed 4 -> 4. The RSS includes the client, queued futures and retained
results, not just the router. Scheduling noise is large; P99 is worse in the
candidate. This is a correctness fix, **not a claimed performance improvement**.
A 1-worker baseline/candidate control was also saved. 1 -> 100 executor workers
is 100x configured concurrency, not an established 100x business traffic SLO.

## Live gateway smoke, not torture

Catalog GET returned 200. Exactly four live completions used the supplied bearer
credential with 256-token caps, no retries, 12s socket/15s router budgets:

| Requested route | Outcome | Observed duration |
|---|---|---:|
| GLM-5.3 | RouterError, no HTTP status exposed | 12,351.99 ms |
| GLM-5.3 Flash | Nonempty success | 3,409.59 ms |
| Kimi K3 | Nonempty success | 4,945.02 ms |
| Qwen 3.8 27B | Nonempty success | 1,044.97 ms |

Exact configured model IDs and safe usage counters are in model-catalog.json /
live-smoke.json. Failed request cost is unknown; zero local token accounting
is not proof of zero upstream billing. No unbounded provider load was launched.
The single GLM error is not sufficient to diagnose its upstream cause.
429/5xx, malformed responses and fallback behavior have local regression
coverage; sustained live multi-replica recovery remains unverified.

## Five-point premortem / accountable launch gates

| Failure mode at 100x | Evidence / action | Owner / release gate |
|---|---|---|
| Worker starvation and lock convoy | 848/1,000 capacity 503s; 2.72 useful req/s | Architect: bounded domain pools, per-tenant fairness; >=50% successful extraction at 100 clients, separately hosted soak |
| Breaker races and distributed divergence | Local stale-response/probe/retry races fixed; no shared state | Architect: atomic replica-wide quota/breaker with TTL/fencing; failover and 429/5xx chaos proof |
| Cancellation leaks and memory growth | Probe lease + 100-slot recovery covered; FD stable in microbench | Red team: sustained cancellation soak with RSS, FD, child-process and permit recovery |
| Dependency/capability blast radius | Signed oracle eager imports remain; 37 collection errors | Maintainer: supported runtime lock, capability-scoped imports + authentic signature; all suites green without disabling gates |
| Telemetry backpressure / privacy | Local tracing tests green; no collector evidence | SRE: bounded exporter queue, sampling/cardinality budgets, redacted logs and dropped-span alert drill |

Security/release owner must also close SBOM/vulnerability disposition, tenant
isolation/opaque IDs, production-host proof, 60-minute canary and rollback drill.
The pasted GitHub and Melious secrets remain exposed and must be revoked/rotated.
They were used only for the user-authorized services; no secrets are included
in new files, PR text or git config. Do not repeat them in future checkpoints.

## Deployment, verification and rollback runbook

1. Rotate both credentials; inject new values via secret manager. Preserve the
   oracle signing key outside git. Do not deploy the current branch publicly.
2. Review PR #19 and this increment. Rebuild a supported, locked runtime and
   immutable image; run full unit, integration, E2E, security and platform suites
   on the exact candidate SHA. Keep the PR draft until all required checks pass.
3. In isolated staging configure auth, tenant isolation, resource/cost quotas,
   pinned catalog model IDs and OTel collector with bounded batch export.
   Verify authenticated happy/error flows, unauthenticated denial, JSON logs,
   trace continuity, readiness failure on critical dependency loss and liveness.
4. From a separate load host replay a representative, consented workload with
   documented baseline arrival rate. Ramp to 100x that rate under a fixed cost
   ceiling. Measure offered, admitted, rejected and successful rates separately;
   P50/P95/P99 by outcome; RSS/FD/children/permits. Abort on SLO or safety breach.
5. Run multi-replica 429/5xx/timeout chaos and cancellation storms; verify shared
   budgets and recovery. Do not treat shedding all requests as successful stress.
6. Only after all gates pass, run a 60-minute single-tenant canary. Record image
   digest, schema compatibility and previous known-good digest before promotion.
   Abort on privacy/auth failure, unexpected errors, stuck readiness, or scoped
   latency/capacity gate failure. Stop new admission, drain bounded work, restore
   the previous immutable image/config, and verify health plus a real user flow.
7. Obtain release-owner approval, update PR with exact CI/soak/canary evidence,
   then merge the verified SHA. No tag/deployment/merge is authorized by this
   checkpoint's results alone; the user's conditional merge gate is not met.

Founder track: retain a gated design-partner preview, not public production
claims. Recruit five reviewers for ten redacted memos each; measure median
review-time reduction (target >=30%), correction/refusal rate and week-one repeat
use. No traction, retention or “100x value” outcome has been measured this session.

Raw evidence: `docs/axiom/evidence/session8/`, with SHA256 manifest.
