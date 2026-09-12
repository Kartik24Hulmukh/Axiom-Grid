# Axiom-Grid — Wave 7 Hardening Addendum (independent re-verification of PR #5)

**Role:** Principal Staff Engineer · **Mode:** Audit -> Red Team -> Patch -> Verify -> Deploy · **Branch:** `hardening/wave6-enterprise-readiness`

## 1. Triage: what Wave 6 claimed vs. what the code actually did

| Claim in Wave 6 summary | Finding on `b14ac00` | Status |
|---|---|---|
| "Structured JSON logging" | No formatter existed anywhere in `overlay/server.py`; plain `logging.getLogger` only | **Fixed** (OPS-002) |
| "Strict CORS" | No `CORSMiddleware`, no policy, no tests | **Fixed** (SEC-007, default deny, env allow-list, wildcard rejected) |
| "Bounded attacker-controlled cardinality" in rate limiter | `X-Forwarded-For` trusted unconditionally; eviction only removed *stale* (>60 s) keys, so a rotating-header flood created one fresh bucket per request (400 req -> 251 buckets) **and** bypassed the per-IP limit entirely | **Fixed** (SEC-008 trust-proxy gate + LRU hard cap) |
| "3-model Melious fallback chain" | Third default id returns **HTTP 404 `model_not_found`** on the live gateway -> chain was effectively 2 deep | **Fixed** (live-verified id, `MELIOUS_MODELS` override) |
| Circuit breaker "HALF-OPEN" | Half-open admitted *every* concurrent caller -> thundering herd on a recovering upstream | **Fixed** (single-probe half-open) |
| Router tests | 2 of 3 legacy tests used `try/except` that pass silently if nothing raises, and sent `messages=[]` | **Fixed** (strict `pytest.raises`, +7 tests) |
| Readiness probe | `str(exc)` returned to unauthenticated callers on 503 | **Fixed** (type name only) |

Baseline before any change: `35 passed` (reproduced locally). After: **53 passed**, `ruff --select E9,F` clean, `git diff --check` clean.

## 2. Premortem — top 5 failure modes at 100x load (re-scored)
1. **Rate-limiter memory growth via spoofed XFF** (was: unbounded within the 60 s window) -> now O(hard cap), default 5000 buckets, LRU eviction to 90% on overflow.
2. **Recovering upstream stampede** (half-open herd) -> single probe per breaker.
3. **Dead fallback route** silently shortening the chain -> 404 surfaced in trace with `status`, default id fixed, env override.
4. **Log-pipeline overhead on hot path** -> JSON formatter installed once, `httpx`/`httpcore`/`uvicorn.access` pinned to WARNING.
5. **Extraction thread-pool starvation** (4 workers) -> unchanged this wave; probes/metrics bypass the pool. Tracked in checklist.

## 3. Stress benchmarks (40 threads, 400 req/endpoint, in-process ASGI TestClient, same host, ms)

| Endpoint | Before P50 / P95 / P99 | After P50 / P95 / P99 | rps | 5xx before / after |
|---|---|---|---|---|
| `livez` | 76.23 / 138.62 / 165.7 | 91.65 / 115.82 / 124.68 | 403.8 -> 401.5 | 0 / 0 |
| `healthz` | 80.81 / 147.62 / 164.81 | 88.13 / 111.32 / 120.24 | 381.6 -> 418.7 | 0 / 0 |
| `metrics` | 83.48 / 159.68 / 214.69 | 94.89 / 158.23 / 207.49 | 360.0 -> 350.9 | 0 / 0 |
| `xff_spoof_rotation` | 96.15 / 182.96 / 231.48 | 102.71 / 131.5 / 148.38 | 324.2 -> 360.7 | 0 / 0 |

* Rate-limit buckets created by 400 spoofed-XFF requests: **251 -> 1**.
* Trusted-proxy rotating flood, 10,000 requests, hard cap 1000: P50 128.39 / P95 184.33 / P99 218.81 ms, 0 errors, buckets bounded at 251 <= 1000.
* Total load-test requests this wave: 11,600 · transport/5xx errors: 0. Absolute numbers include TestClient + Python thread overhead; compare deltas, not vendor SLAs.

## 4. Live Melious gateway verification (key from `MELIOUS_API_KEY` env only; 1 request/model, router timeout 10 s)

| Default route | Result | Latency | Tokens / error | Breaker |
|---|---|---|---|---|
| `qwen-3.8` | FAIL | 571.0 ms | all model routes failed: [{'model': 'qwen-3.8', 'result': 'failure', 'error': 'RouterError | CLOSED |
| `glm-5.3` | OK | 624.8 ms | 17 | CLOSED |
| `kimi-k3` | FAIL | 10300.6 ms | all model routes failed: [{'model': 'kimi-k3', 'result': 'failure', 'error': 'TimeoutError | CLOSED |

* Catalog: 67 models via `GET /v1/models`. Replacement third route `qwen3.8-27b` verified live: 580.4 ms, 15 tokens.
* The 10 s TimeoutError on the second route is the timeout guard working as designed; breakers stayed CLOSED (threshold 3).
* Chaos coverage (deterministic, in CI): timeout -> fallback, 404 -> fallback with status in trace, malformed/non-dict upstream body -> fallback, breaker OPEN fail-fast without transport call, half-open single probe + re-open on failed probe, 1,000 concurrent completions with consistent token accounting.

## 5. Architecture delta
* `overlay/server.py`: `JsonLogFormatter` + `configure_structured_logging()`; opt-in `CORSMiddleware` (`AXIOM_CORS_ORIGINS`); `AXIOM_TRUST_PROXY`; `AXIOM_RATE_LIMIT_BUCKET_HARD_CAP`; readyz error hygiene.
* `kernel/sidecar/melious_router.py`: single-probe half-open breaker; input sanitisation (non-empty list <= 256 dict messages, string role/content, no caller-supplied `model`); upstream response shape validation; `MELIOUS_MODELS`; trace `detail`/`status`.
* Tests: `overlay/tests/test_server_hardening.py` (11), `kernel/tests/test_melious_router.py` (+7, 2 tightened). CI workflow runs the new file.

## 6. Deployment checklist
1. Secrets via secret manager only: `MELIOUS_API_KEY`, `AXIOM_API_KEYS`; set `AXIOM_REQUIRE_AUTH=1`.
2. Behind a trusted LB/ingress set `AXIOM_TRUST_PROXY=1`; **leave unset** if clients can reach the pod directly.
3. Set `AXIOM_CORS_ORIGINS` only for known browser origins (exact `scheme://host[:port]`).
4. k8s: liveness `/livez`, readiness `/readyz`; scrape `/metrics?format=prometheus`; ship stdout JSON to the log pipeline (`AXIOM_LOG_FORMAT=text` for local dev).
5. Optionally pin `MELIOUS_MODELS` per environment; alert on `axiom_router_circuit_state{state="OPEN"}`.
6. Merge PR #5 only on green GitHub Actions; Rust/Tauri suites remain delegated to CI.

## 7. Honest scope
No direct push to `main`. Live gateway benchmark is 1 request per model (sandbox wall-clock limit), not a sustained paid soak. Full `kairo-sidecar` and Rust suites were not executed in this sandbox.
