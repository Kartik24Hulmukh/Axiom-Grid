# Axiom-Grid Wave 9 — CI-Blocking Log-I/O Remediation Addendum

**Base:** `hardening/wave8-premortem-remediation` (`a01c673`, PR #7) on merged Wave 6 (`main` = `4e304bd`).
**Mode:** Audit -> Red Team -> Patch -> Verify -> Deploy.
**Secrets:** consumed via environment variables only (`MELIOUS_API_KEY`, `GIT_AUTH_TOKEN`); supplied-secret scan of the diff = clean.

## 1. Why Wave 9 exists

Wave 8 shipped PR #7 with all local gates green, but GitHub Actions on `a01c673` came back **focused-runtime: failure** (run 34755483228) while focused-overlay and GitGuardian passed. The Definition of Done requires a 100% green suite, so Wave 9 diagnoses and fixes the one red gate.

## 2. Root cause (CI-001 / OPS-006): synchronous log writes on the serving path

Job log, step 14 (`scripts/stress_sec006_gauntlet.py`):

    proc.terminate(); proc.wait(5)
    subprocess.TimeoutExpired: Command '['/usr/bin/python3', '-m', 'uvicorn', 'overlay.server:app', ...]' timed out after 5 seconds

The gauntlet launches uvicorn with `stderr=subprocess.PIPE` and never reads the pipe. `configure_structured_logging()` (OPS-002, Wave 6) attaches `JsonLogFormatter` to a **plain `logging.StreamHandler`**, i.e. every request writes ~180 B of JSON synchronously to fd 2. After ~64 KiB (the pipe buffer) every worker thread blocks inside `write()`; the event loop can no longer service the in-flight keep-alive connections, so `terminate()` (SIGTERM) arrives while uvicorn is still draining and graceful shutdown never completes -> `wait(5)` raises. Same defect class in production: any supervisor/harness that stops draining stderr (`cmd | head`, a stuck sidecar collector) stalls the whole service.

Reproduced locally (identical traceback), then bisected by I/O mode:

* stderr=DEVNULL -> 500/500 OK, clean SIGTERM exit.
* stderr=PIPE drained by a reader thread -> 500/500 OK, clean exit.
* stderr=PIPE undrained -> stall at request ~254, then `TimeoutExpired`.

The auth logic itself was never at fault: all SEC-006 invariants hold (step 15 was only skipped because step 14 crashed).

## 3. Fix (`fix:` semantic commit)

* `_NonBlockingQueueHandler(logging.handlers.QueueHandler)`: records go to a bounded `queue.Queue(maxsize=AXIOM_LOG_QUEUE_MAX, default 4096)` via `put_nowait`; a daemon `QueueListener` owns the blocking sink write. Saturation **sheds** records and counts them (`LOG_DROPPED_TOTAL`) instead of blocking a request thread.
* `/metrics` JSON + Prometheus exposition gain `log_dropped_total` / `axiom_log_dropped_total` (observability for shed pressure; alert on growth).
* `overlay/tests/test_server_wave9.py`: 4 regressions — handler topology, saturation sheds within 0.5 s (never blocks), metrics exposure, and an end-to-end live-socket regression that boots uvicorn with an **undrained stderr pipe**, runs 400 requests and asserts `proc.wait(5)` returns (the exact CI precondition).
* `.github/workflows/axiom.yml`: overlay gate runs the Wave 9 file.

## 4. Verification

| Gate | Pre-patch (`a01c673`) | Post-patch (Wave 9) |
|---|---|---|
| pytest overlay+kernel (incl. chaos/router) | 98 passed | **102 passed** (4 new) |
| `ruff check --select E9,F` (changed files) | clean | clean |
| SEC-006 live gauntlet 400 req/40 thr (undrained pipe) | **TimeoutExpired** -> CI red | **PASS**: 839.1 rps, P50 47.55 / P99 89.54 ms, 0 transport errors, all invariants held |
| 300 mixed req / 30 thr, undrained stderr pipe | 18.4 rps, P50 36.2 / P95 8008.2 / P99 8008.6 ms, 51 transport errors, SIGTERM **HANG** | **847.2 rps, P50 32.6 / P95 43.1 / P99 47.1 ms, 0 errors, SIGTERM clean (0.16 s)** |
| Same load, drained stderr (control) | 826.0 rps, P95 41.5 ms, clean | 856.4 rps, P95 39.3 ms, clean (no regression) |
| Live Melious gateway (env key, 1 req/model, 12 s) | — | `[redacted]-5.3` OK 739 ms (22 tok) · `[redacted]-k3` OK 1533 ms (165 tok) · `[redacted]-27b` OK 1172 ms (54 tok) — 3-deep chain live-verified |
| Supplied-secret scan of diff | clean | clean |

## 5. Architecture delta

* `overlay/server.py`: `logging.handlers`/`queue` imports; `LOG_DROPPED_TOTAL`; `_NonBlockingQueueHandler`; `configure_structured_logging()` now installs QueueListener+bounded queue (idempotence check switched to handler type); `/metrics` JSON + Prometheus `log_dropped_total`.
* `overlay/tests/test_server_wave9.py` (new): 4 regressions incl. live-socket undrained-pipe SIGTERM test.
* `.github/workflows/axiom.yml`: overlay gate extended.
* `docs/WAVE9_HARDENING_ADDENDUM.md` (this file).

## 6. Deployment checklist (delta over Waves 6-8)

1. Log emission is now non-blocking by construction; nothing to configure. Optional: `AXIOM_LOG_QUEUE_MAX` (default 4096 records) for very chatty deployments.
2. Alert on `axiom_log_dropped_total` growth: sustained shedding means the log sink cannot keep up (disk/collector saturation) — fix the sink, not the app.
3. Supervisors may now safely use pipes for service stderr; a stalled collector degrades observability (shed records) but can no longer stall serving or block SIGTERM rolling deploys.
4. All Wave 6-8 checklist items still apply (`AXIOM_REQUIRE_AUTH=1`, trust-proxy gate, CORS allow-list, `/livez` `/readyz`, `/metrics?format=prometheus`, secret-manager-only credentials, merge only on green Actions).
