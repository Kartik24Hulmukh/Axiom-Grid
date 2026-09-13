# v1.0-PROD independent release review

Status: NO-GO. Baseline commit c1fbe270ee7144a1ff3cd85c5a77735cd499969a.

## Frozen baseline
128 focused tests passed with ResourceWarning and unraisable exceptions fatal; 17 Node tests passed. Broad overlay/kernel lint: 89 findings. Repository-wide collection: 2563 tests collected, 41 errors (missing dependencies and missing packs.wedge). Rust toolchain unavailable locally. Existing PR #11 CI failed on import order.

Baseline probe harness: 2000 requests/100 threads, P50 103.18ms, P95 136.43ms, P99 167.48ms, 1088.1 RPS; **only 1350 HTTP 200, 150 HTTP 404, 500 HTTP 429**. Zero transport errors is NOT availability. RSS 78.3→100.3 MiB. Short probe-only test is NOT a 100x mixed workload or uptime certification.

## Premortem (hypotheses, not all resolved)
1. Admission overload: bounded extraction slots shed 503; rejected useful requests consume the availability error budget.
2. SQLite concurrency/lifecycle: shared connections, close without coordinating workers, repeated ASGI lifespans leave closed references.
3. Router failure amplification: per-route timeouts compound, malformed choice bodies pass shallow validation, no enforced completion budget.
4. False-positive release gates: benchmark counts HTTP 404/429 as successful transport and always exits zero; no defined baseline RPS or soak.
5. Deployment mismatch: process-local quota/circuit states multiply across workers; demonstration inference and absent unified OTel cannot establish production E2E.

## Safety
Credentials were present in supplied certification/chat. Rotate both credentials; never copy attachments into git. Do not delete the SQLite database during rollback. Preserve and snapshot durable state.
