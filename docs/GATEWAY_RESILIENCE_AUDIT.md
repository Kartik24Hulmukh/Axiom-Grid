# Gateway resilience — scoped local audit

Scope: `kernel/sidecar/melious_router.py` and dedicated gateway tests/docs only.
Base: `4f3a822`, isolated `council/gateway-hardening` worktree. No server,
admission, UX, remote, or provider mutations. This is not a launch/load pass.

## Demonstrated gaps and implemented behavior

- **Per-attempt spend:** one call reservation formerly financed multiple billed
  rejected responses/fallbacks. Each additional dispatch now settles the prior
  attempt and re-admits against committed + reserved spend. A ceiling refusal
  propagates without contacting the next route or counting it as upstream failure.
  The initial reservation is still made before request metrics, preserving existing
  admission semantics. Durable ledgers now record a separate row per dispatch.
- **Hidden reasoning:** explicitly reported reasoning is a lower bound on completion
  tokens. Missing/understated completion and total counts cannot erase that lower
  bound or bypass the requested completion limit. Reasoning is not double-counted.
  Existing empty `length` responses remain fail-fast budget errors, with usage billed.
- **Request budgets:** validate before spend reservation; include tools/message
  metadata in the existing heuristic and the router-added model field in the wire
  byte limit. UTF-8 validation and actual serialization now use the same encoding.
- **Retry-After:** finite numeric/date values are bounded to a local one-hour route
  cooldown. Invalid, absent, past or zero delays on 429 get a one-second cooldown.
  A 429 never sleeps a worker or retries within the same completion. This is an
  explicit availability policy: delays above one hour are truncated, not a claim
  of provider permission to retry sooner. Operators must use provider-side quotas.
- **Deadlines:** call time starts before validation/reservation; state-lock waits
  share the remaining total budget. Half-open timeout cannot exceed a route's own
  timeout. The stdlib HTTP transport interrupts trickled headers/bodies by shutting
  down its connected socket on the per-exchange monotonic deadline. Its watchdog
  is joined before response/socket closure and before releasing the inflight slot.
- **Cancellation:** `complete(..., cancel_event=threading.Event())` supports explicit
  cancellation at admission, state-lock waits, retries/backoff and connected HTTP
  I/O. It stops fallback dispatch, releases reservations/slots and the half-open
  probe lease. The token is not serialized into provider options. Cancelling a
  running `Future` does not terminate native work or release its capacity early.
- **Redaction:** sanitized traces are no longer undermined by a chained raw
  transport exception in formatted traceback logs. HTTP status metadata is retained
  only for integer 100..599 codes. Error response bodies are not read or echoed.
- **Model validation:** identifiers must be non-empty, unique ASCII-safe names
  (200-character maximum), preventing accidental string-as-chain and metric-label
  injection. `discover_models()` explicitly fetches a byte/deadline/slot-bounded
  `/models` snapshot; `validate_models()` requires exact configured IDs in that
  well-formed, nonempty, unique catalog. Neither method runs implicitly. A reported
  completion `model` must match the requested ID; absent metadata remains supported.

Existing 5xx-first-fallback behavior, final-route bounded retries, generation-fenced
circuit transitions, single half-open probe and healthy budget-error recovery are
retained. Loopback tests exercise these rather than adding a second router.

## Reproduction

From the isolated worktree, using the existing virtualenv:

```sh
/data/axiom-third/venv/bin/python -m pytest -q \
  kernel/tests/test_gateway_resilience_http.py \
  kernel/tests/test_melious_router*.py \
  kernel/tests/test_melious_local_http.py \
  kernel/tests/test_router*.py \
  kernel/tests/test_launch_hardening_ag07_08_09.py \
  kernel/tests/test_session21_isolation_and_timeouts.py \
  -W error::ResourceWarning \
  -W error::pytest.PytestUnraisableExceptionWarning
/data/axiom-third/venv/bin/ruff check --select F \
  kernel/sidecar/melious_router.py kernel/tests/test_gateway_resilience_http.py
git diff --check
```

The new tests use actual `ThreadingHTTPServer` loopback sockets and synthetic
credentials, including 503/429 faults, slow headers/bodies, catalog corruption,
reported model mismatch, billed invalid responses, deadline/cancellation cleanup,
100 simultaneous callers with exactly one recovery HTTP request, and a durable
per-dispatch ledger. Some boundary/redaction checks use injected transports;
those are not represented as real-network evidence. Timing assertions are scoped
functional bounds (<500 ms with deliberately short deadlines), not wire SLOs or
load certification. Test counts and retained failed iterations are in the handoff
review, outside this source worktree.

## Remaining limits / compatibility

- DNS resolution and pre-watchdog TCP/TLS connection establishment use synchronous
  OS/stdlib calls; socket timeouts and post-connect checks are **not** a hard
  wall-clock cancellation guarantee for those phases. TLS, independent-host faults,
  long soak and parent broad/final load remain unverified here.
- Custom injected transports must honor their timeout; the router cannot preempt
  arbitrary Python/native work. Server disconnect propagation needs a caller-owned
  cancellation Event; this audit deliberately does not edit server wiring.
- Token estimates are not a tokenizer/context-window bound or provider monetary
  cap. Role/model templates and Unicode can exceed the heuristic. Reported usage
  can exceed reservations, and missing/malformed usage or lost/error responses
  cannot prove zero provider spend. Provider budgets/reconciliation are still needed.
- Breakers and cooldowns remain process-local. SQLite spend coordination only works
  for replicas sharing a suitably reliable file; not independent-host HA.
- Direct `http.client` deliberately ignores ambient HTTP proxy configuration and
  never follows redirects. Deployments requiring a proxy need an explicitly audited
  transport. Header parsing retains stdlib limits; the configured byte budget bounds
  response bodies, not a custom aggregate header-memory budget.
- Strict model IDs/response-ID equality can reject provider aliases that were
  silently accepted before. Resolve exact catalog/response IDs explicitly; do not
  loosen this to claim unverified aliases work. Historical default labels are
  still unverified. A local fixture catalog is not evidence of live availability,
  answer quality, permission, pricing or provider compatibility.

## Catalog decision

Read the supplied repository catalog and research execution ledger. Existing
stdlib HTTP/threading/SQLite solve the observed gaps without a framework install.
`decolua/9router` would introduce a separate router/runtime rather than fix this
Python boundary; k6/xk6 are unnecessary for the deterministic local fault oracle.
No upstream code was downloaded or integrated, and no new license/security approval
is inferred. The existing Gitleaks binary is reused solely for a redacted scoped
file scan; it is not a provider connector or a full-history secret audit. No new
runtime dependencies, SaaS collectors, external calls or remote mutations.

## Recorded verification

Runtime/test commit: `d82273f4e72c53bd044787df4256367aa833f62e`.
Existing baseline: **123 passed**. Final same-source strict focused run:
**162 passed**, including **39 dedicated new cases**, with one existing
Starlette TestClient deprecation warning. ResourceWarning and unraisable-exception
warnings were errors, not ignored. Scoped Ruff `F` checks and whitespace checks
pass. Existing Gitleaks 8.30.1 reports zero findings on the three scoped files;
this does not scan existing repository history or revoke historical credentials.

The retained first fault suite failed 21 of 22 cases against the base. Later tests
caught a state-lock cancellation delay, a new test's unclosed SQLite connection
(corrected using explicit close), and understated reasoning accounting. All failed
iterations remain in the outside-worktree evidence directory; no gate was waived.
Production source changed in three bounded cycles; the dedicated test module in
five. Parent-owned broad/final full-load verification is still required.
