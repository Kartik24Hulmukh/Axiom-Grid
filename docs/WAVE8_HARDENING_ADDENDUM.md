# Axiom-Grid Wave 8 — Premortem Remediation & Final Hardening Addendum

**Base:** `hardening/wave7-red-team-remediation` (`21dec6b`, PR #6) on top of merged Wave 6 (`main` = `4e304bd`).
**Mode:** Audit -> Red Team -> Patch -> Verify -> Deploy.

## 1. Baseline (reproduced before any change)

| Gate | Result |
|---|---|
| Overlay + router + kernel pytest | **90 passed** in 8.10 s |
| 100x stress gate (`stress_test.py`, 300 mixed req / 30 threads) | 16/16 probes, 166.12 req/s, P50 25.24 / P95 964.01 / P99 984.53 ms, 0 crashes |
| Wedge F1 (`eval_wedge.py`) | 0.996 |
| Adversarial F1 (`eval_adversarial.py`) | 0.977 (gate >= 0.80) |
| GitHub Actions on PR #6 head (`21dec6b`) | success (both jobs) |

## 2. Wave 8 premortem findings -> fixes

| # | Finding on the Wave 7 branch | Severity | Fix |
|---|---|---|---|
| OPS-004 | `_extraction_pool` (4 workers) fronted by an **unbounded** executor queue: under a sustained spike requests pile up, latency grows past any SLO, clients time out while the server burns CPU on dead work | High (latency collapse) | `BoundedSemaphore(workers + AXIOM_EXTRACTION_QUEUE_DEPTH=16)` admission control -> fast **503 + Retry-After: 1** load shedding; `extraction_shed_total` surfaced in `/metrics` (JSON + Prometheus) |
| OPS-005 | Router `RLock` acquisitions were **unbounded**: a single stuck critical section parks every concurrent caller forever (100x premortem: silent global stall) | High (availability) | Every `acquire()` is bounded by `acquire_timeout=5.0` -> `RouterError("router saturated")` instead of an infinite wait; half-open probe uses a **shorter `probe_timeout`** (default timeout/2) so a hung recovering upstream cannot stretch tail latency; final `RouterError` now propagates the last upstream HTTP `status` |
| SEC-009 | 4 error paths returned raw `str(exc)` / resolved server paths to API clients (`/api/extract-document` read error, pipeline 500, ask-document 500, figures 500) — same information-disclosure class Wave 7 fixed on `/readyz` but left elsewhere | Medium | All four now return static detail strings; full context stays in the server-side exception log |
| OPS-003 | No request correlation: support tickets could not be joined to the JSON log stream | Medium (operability) | `X-Request-Id` middleware: honours a bounded (<=64 char) client id, mints a uuid otherwise, **sanitizes CR/LF/colon** (log-injection / response-splitting guard), echoes on every response, and the governor emits one structured JSON `request completed` line per request with `request_id`, `path`, `status`, `latency_ms`, `client` |

## 3. Verification after fixes

| Gate | Result |
|---|---|
| pytest overlay + kernel (incl. 8 new Wave 8 regressions) | **98 passed** in 10.69 s (baseline 90) |
| `ruff check --select E9,F` on changed files | clean |
| 100x stress gate re-run | 16/16 probes, 134.66 req/s, P50 36.02 / P95 1217.71 / P99 1257.80 ms, 0 crashes, status mix unchanged (200/404/422/429 = 100/103/81/16) |
| Wedge F1 / adversarial F1 re-run | 0.996 / 0.977 — unchanged |
| Live Melious gateway (key from env only, 1 req/model, 10 s timeout) | `[redacted]-5.3` **OK** 552 ms (35 tok, 14 reasoning) · `[redacted]-k3` **OK** 1116 ms (147 tok, 16 reasoning) · `[redacted]-27b` **OK** 624 ms (33 tok, 16 reasoning) — full 3-deep fallback chain live-verified |
| Supplied-secret scan of diff | clean (keys consumed from env only; CI never sees them) |

Stress throughput dipped 166 -> 135 req/s: the expected cost of one JSON log line + one header write per request (OPS-003). Tail-latency behaviour under overload is now *bounded by design* (OPS-004/OPS-005) rather than best-effort; absolute numbers include TestClient/thread overhead — compare deltas.

## 4. Architecture delta

* `overlay/server.py`: request-id middleware (OPS-003); per-request structured completion log; extraction backpressure semaphore + shed counter (OPS-004); static client-facing error detail (SEC-009 x4); shed counter in `/metrics` JSON + Prometheus exposition.
* `kernel/sidecar/melious_router.py`: bounded lock acquisition (OPS-005), half-open probe deadline, upstream `status` propagation on terminal `RouterError`.
* `overlay/tests/test_server_wave8.py`: 8 regressions (request-id echo/mint/sanitize, no-leak read error, fast 503 shedding + counter + Prometheus exposition, lock-saturation fail-fast + recovery, probe-deadline + re-open).
* `.github/workflows/axiom.yml`: overlay gate now runs the Wave 8 test file.

## 5. Deployment checklist (delta over Wave 7)

1. Optional: tune `AXIOM_EXTRACTION_QUEUE_DEPTH` (default 16) to pod CPU; alert on `axiom_extraction_shed_total` growth — that is the horizontal-scale trigger.
2. Optional: set `MELIOUS_ACQUIRE_TIMEOUT`-equivalent via constructor (`acquire_timeout`) if the sidecar SLO is tighter than 5 s.
3. Front proxies may pass `X-Request-Id` through; ids longer than 64 chars or containing control chars are replaced, so log joins stay safe.
4. Everything from the Wave 7 checklist still applies (trust-proxy gate, CORS allow-list, `/livez`/`/readyz` probes, secret-manager-only credentials).
