# Server source implementation notes

Long explanatory comment blocks from `overlay/server.py` are preserved here to
keep that file within the GitHub MCP request-size limit. Short source pointers
retain each block's location. The executable Python AST is identical before and
after this comment-only relocation; no source directive or executable code moved.

These are historical source comments, not fresh validation or production evidence.
Claims about past performance/stress runs are not endorsed by preserving the text.
See CONTINUATION_VERDICT.md and current CI for actual observed results and limits.
The line ranges below refer to the pre-relocation file in the previous delivery.

## Note 1 — original source lines 46–55

```text
# ------------------------------------------------------------------
# SEC-015: lone UTF-16 surrogates (e.g. JSON "\udcff") are *valid JSON* and
# valid Python str, so they pass the byte-level SEC-014 sanitizer, but
# `str.encode("utf-8")` raises UnicodeEncodeError. Starlette's JSONResponse
# encodes inside `render()` in the ASGI send path -- *after* every handler
# try/except -- so one hostile escape turned every ingress route into a 500.
# Native fix: (a) the response layer is made total (it can never raise on any
# content), (b) ingress models reject surrogates up-front with an honest 422
# before the payload can reach sqlite3 / the pipeline, which would also panic.
# ------------------------------------------------------------------
```

## Note 2 — original source lines 165–167

```text
        # Recreate at the CONFIGURED capacity, not a hard-coded four: silently
        # reverting to four workers after a restart collapses extraction
        # throughput at the intended replica size (worker-starvation premortem).
```

## Note 3 — original source lines 174–176

```text
        # ASGI server has drained ingress; do not close state while work runs.
        # Running Python threads cannot be forcibly stopped: supervisors still
        # need a termination grace period for a genuinely hung native parser.
```

## Note 4 — original source lines 185–189

```text
# ZERO-DAY FIX (2026-09-16): safe RequestValidationError handler.
# ------------------------------------------------------------------
# OPS-002: structured JSON logging (one JSON object per line; safe for
# Loki/Datadog/CloudWatch ingestion). Opt out with AXIOM_LOG_FORMAT=text.
# ------------------------------------------------------------------
```

## Note 5 — original source lines 249–251

```text
    # Uvicorn installs its own synchronous stderr handlers before importing
    # the app. Route lifecycle/error logs through the same bounded queue too:
    # otherwise shutdown INFO messages can block behind a saturated sink.
```

## Note 6 — original source lines 267–272

```text
# ------------------------------------------------------------------
# SEC-007: strict, explicit CORS. Default is deny-all cross-origin: the
# overlay is same-origin by design. Operators opt in per-origin via
# AXIOM_CORS_ORIGINS (comma-separated, exact scheme://host[:port]). The
# wildcard "*" is rejected when credentials would be allowed.
# ------------------------------------------------------------------
```

## Note 7 — original source lines 337–339

```text
# ------------------------------------------------------------------
# Production hardening middleware (SEC-003/004, OPS-001)
# ------------------------------------------------------------------
```

## Note 8 — original source lines 341–346

```text
# SEC-004: regex-heavy packs run against a bounded thread pool so a hostile
# oversized document cannot monopolise the async event loop (CPU-starvation
# DoS guard). Bounded at 4 workers; 100x stress proved lock-safe behaviour.
# Capacity now scales with the host instead of being pinned at 4: a 16-core
# production box admits 32 concurrent extractions (8x) while a laptop keeps the
# old safe floor. Override explicitly with AXIOM_EXTRACTION_WORKERS.
```

## Note 9 — original source lines 356–360

```text
# OPS-004: backpressure on the extraction pool. A ThreadPoolExecutor queue is
# unbounded, so under a spike far beyond 4 workers requests pile up, latency
# balloons past any SLO, and clients time out while the server still burns
# CPU on dead work. A semaphore of workers + small queue turns overload into
# a fast, honest 503 (fail-fast, load-shedding) instead of a slow collapse.
```

## Note 10 — original source lines 376–379

```text
# AG-07: a hung or pathological parse must not hold the client (or the load
# balancer) hostage. The waiter gives up at this deadline with an honest 504;
# the admission slot is released by the worker's done-callback, never early,
# so capacity accounting stays exact. Expanded-work caps live in the ingestor.
```

## Note 11 — original source lines 383–387

```text
# ------------------------------------------------------------------
# OPS-003: request-id correlation. Honour a client-supplied X-Request-Id
# (bounded, sanitized) or mint one; echo it on every response so client
# support tickets can be joined to the structured JSON log stream.
# ------------------------------------------------------------------
```

## Note 12 — original source lines 462–481

```text
# ------------------------------------------------------------------
# SEC-006: bearer / API-key authentication for the public API surface
# ------------------------------------------------------------------
#
# Threat model: the overlay was born as a same-origin desktop sidecar, where
# the origin gate (SEC-002) is sufficient. The moment it is exposed as a
# network API every mutating endpoint (/demo, /apply, /correct, /api/*) is
# callable by anyone who can reach the socket. SEC-006 closes that.
#
#   AXIOM_API_KEYS      comma-separated list of accepted keys. When set, every
#                       non-exempt route requires `Authorization: Bearer <key>`
#                       or `X-API-Key: <key>`. Unset => local-first mode
#                       (auth disabled, origin gate still enforced).
#   AXIOM_REQUIRE_AUTH  "1"/"true" => production posture. If no keys are
#                       configured the API FAILS CLOSED with 503 on protected
#                       routes instead of silently running open.
#
# Keys are compared via sha256 digests with hmac.compare_digest (constant-time,
# length-independent). The digest prefix doubles as a stable per-tenant id so
# the rate limiter (SEC-005) can apply a per-key quota tier instead of per-IP.
```

## Note 13 — original source lines 559–561

```text
# ------------------------------------------------------------------
# SEC-005: token-bucket rate limiting (per-client-IP) production hardening
# ------------------------------------------------------------------
```

## Note 14 — original source lines 568–570

```text
# Hard ceiling on distinct buckets regardless of freshness: beyond this the
# least-recently-seen buckets are evicted so memory is O(hard_cap) even under
# a rotating-source flood (100x load premortem #1).
```

## Note 15 — original source lines 580–582

```text
    # SEC-006 tier: a valid API key gets its own (larger) bucket keyed by
    # tenant id, so one noisy tenant behind a shared NAT/LB IP cannot starve
    # the others, and per-tenant quotas can be metered/billed later.
```

## Note 16 — original source lines 586–590

```text
    # SEC-008: X-Forwarded-For is attacker-controlled unless a trusted reverse
    # proxy is guaranteed to overwrite it. Only honour it when the operator
    # explicitly declares that topology (AXIOM_TRUST_PROXY=1); otherwise a
    # client could rotate the header to mint a fresh bucket per request and
    # bypass the limit entirely while growing the bucket table.
```

## Note 17 — original source lines 692–697

```text
# --- Pipeline concurrency: launch-blocker #1 fix ------------------------------
# Previously every /demo and /apply call serialized on one global mutex, which
# shed 80-91% of requests under load. The shared services (ProvenanceLogImpl,
# MemoryStoreImpl) are now individually thread-safe (@synchronized_class), so
# the HTTP layer needs *bounded* concurrency to protect CPU/memory, not mutual
# exclusion. Tune with AXIOM_PIPELINE_CONCURRENCY.
```

## Note 18 — original source lines 1048–1050

```text
    # Admission covers all document I/O, classification and pipeline work.
    # Acquiring only at submit time let rejected requests fill the default
    # executor and retain full document strings before the capacity check.
```

## Note 19 — original source lines 1374–1376

```text
# ------------------------------------------------------------------
# Production ops endpoints: liveness, readiness, metrics
# ------------------------------------------------------------------
```

## Note 20 — original source lines 1396–1403

```text
# AG-09: readiness must not lie. The previous implementation cached one
# successful synthetic probe for the life of the process, so a pod whose
# parsers, state directory or worker pool later broke stayed in rotation.
# Now a verified-ready verdict is only trusted for READYZ_TTL_SECONDS, a
# failing verdict is cached briefly (negative TTL) so a load balancer polling
# many replicas cannot stampede the pipeline, and exactly one probe runs at a
# time per process (single-flight). Recovery is automatic: the next probe
# after the TTL re-validates and restores routing.
```

## Note 21 — original source lines 1530–1532

```text
        # Latency summary (Prometheus summary-style quantiles). Alerting on P95/P99 requires this
        # exposition; the JSON form alone is not scrapeable. Quantiles are over the bounded in-process
        # sample window, so each worker reports its own distribution (aggregate with max() by pod).
```

## Note 22 — original source lines 1545–1554

```text
# ------------------------------------------------------------------
# SEC-014 (zero-day): RequestValidationError serialization panic.
# FastAPI's jsonable_encoder renders raw bytes with `lambda o: o.decode()`.
# A client POSTing non-UTF-8 garbage (e.g. Content-Type:
# application/octet-stream) therefore raises UnicodeDecodeError *inside* the
# ASGI error path, which escapes Starlette as an unhandled 500 panic instead
# of an honest 422. We sanitize the validation payload (lossy-replace
# undecodable bytes, cap echoed blob size) before encoding, so malformed
# input always fails closed, fast, and without leaking a stack trace.
# ------------------------------------------------------------------
```
