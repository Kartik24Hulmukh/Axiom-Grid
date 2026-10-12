# Axiom V8.2 — read-only causal/design load review

## Decision

**Keep launch NO-GO and reserve the final server5 cycle.** The frozen trace establishes two response-header transport failures on previously established HTTP/1.1 connections. It does not establish an HTTPX defect, a keepalive-expiry incident, or GIL starvation as their root cause. The independent Node client establishes a separate server-side hostile-phase tail above 200 ms with no recorded admission wait. Neither finding explains the other.

The smallest safe runtime candidate is a denied-path stat short-circuit, described below. Its correctness rationale is concrete; its ability to close either launch blocker is not demonstrated. Do not spend the last runtime cycle as a speculative transport fix.

This review performed local file reads, source inspection, dependency/version introspection, and arithmetic checks only. No workloads, tests, service launches, dependency installation, network/provider requests, repository edits, diagnostic changes, or budget resets were performed. The only deliverable written is this report. Diagnostic implementation remains **5/5 frozen**; inherited server4/helper1 accounting is unchanged. Tests and 120 scripted identities are not humans.

## 1. Provenance and limits

- Current checkout: `/data/axiom-integration`, clean, HEAD `27e9f8e0854b9d8b00ac64162d686d2fb7b791d5`; tree `61ad975fc0668ea818fc9fff216a35fad4ec9f2d`.
- The V8.1 follow-up report records remote PR33 head `922abacbf5a67b7b5608f9a7699eacab37c9c679` with that same tree. This review verified the local tree, not the remote through a new network request.
- Frozen traced producer report records `6fde2297fe341bdf4b97c536945243592118f994`. That commit object is not available in this recovered checkout; a requested historical diff could not be performed. Do not silently treat the frozen run as a new measurement of HEAD.
- The native and untraced TCP reports record `376c575af45290f034c3f933b2ee044d5f2b3d14`. That object is available. Its diff to HEAD is empty for `overlay/server.py`, `overlay/request_policy.py`, `scripts/launch_torture.py`, and `scripts/benchmark_ingress.mjs`. This removes drift in those inspected files, not every environment or dependency confounder.
- Current actual installed sources in both `/data/axiom-venv` and `/data/axiom-minvenv`: HTTPX **0.28.1**, httpcore **1.0.9**, Uvicorn **0.51.0**, AnyIO **4.14.2**. The inspected full venv has h11 **0.16.0**, Python **3.13.14**, and an enabled GIL (`Py_GIL_DISABLED=0`, `sys._is_gil_enabled()=True`). Neither venv currently has uvloop or httptools. These are present-installation observations, not proof of every historical run's package state.
- Installed Uvicorn `protocols/http/auto.py` and `loops/auto.py` consequently select h11 and asyncio today. The release report explicitly says a separate accelerator experiment failed and its added packages were removed.

Sources: `/data/axiom-v8-delivery/Axiom-Grid-V8-Report.md`, `Axiom-Grid-V8.1-Followup-Report.md`, `evidence/V8_LATENCY_COUNCIL.md`, the three producer reports discussed below, their retained trace/log, and the current scripts/runtime/installed package sources.

## 2. What the frozen transport trace actually establishes

Inputs: `evidence/axiom-v8-traced-tcp-100.transport.json`, `axiom-v8-traced-tcp-100.json`, and `axiom-v8-traced-tcp-100.server.log`.

The five timed phases contain **4,500 requests**. The sidecar has **4,510** aggregate requests: those timed calls plus eight failed startup `/readyz` polls, one successful readiness call, and one metrics call. Aggregates cross-foot to 4,510. Its retained exception records independently cross-check to eight ConnectErrors, one ReadError, and one RemoteProtocolError. The phase report has exactly **two status-0 failures**, both during mixed personas. None of the transport details or trace events was dropped; **2,926 ordinary details** were dropped. Do not infer distributions from that selected detail sample.

| Failed call | Total request time | First header-send event | Header receive start → failure | Observed failure |
| --- | ---: | ---: | ---: | --- |
| `/correct` | 367.967 ms | 273.564 ms | 319.298 → 343.542 ms | HTTPX ReadError → httpcore ReadError; trace's immediate lower cause AnyIO BrokenResourceError |
| `/api/source/{doc_id}` | 170.465 ms | 48.828 ms | 70.580 → 121.661 ms | HTTPX RemoteProtocolError → httpcore RemoteProtocolError; trace's immediate lower cause absent |

For both calls:

1. Header and body send traces complete.
2. No TCP-connect/start-TLS trace occurs, and no trace event was dropped.
3. Failure occurs while receiving response headers, before any recorded successful response-header completion.
4. `response_closed` runs afterward as error cleanup.

With the installed httpcore connection path (`_async/connection.py:69–106`), a connection without an established underlying HTTP connection emits connect events before the HTTP/1.1 send events. Their absence strongly supports **reuse of an already established pooled connection**, not a fresh connect failure. It does not identify the socket, its previous response, or its idle age.

The 273.564/48.828 ms gaps precede the first traced send. They can include pool acquisition, client scheduling, and untraced client work; the wrapper emits no pool-wait timing. They are **not** measured server policy latency. Completed writes mean the local transport accepted the writes, not that the peer parsed the request or sent a response.

### Exception mechanisms: narrow causal conclusions

- Installed AnyIO `_backends/_asyncio.py:1256–1261,1326–1351` stores a protocol error in `connection_lost(exc)` and raises BrokenResourceError on receive when no queued data remains and that stored exception exists. httpcore `_backends/anyio.py:25–40` maps it to ReadError; HTTPX `_transports/default.py:74–95` maps the httpcore type to its public counterpart. Thus this trace identifies a **broken stream on the read path**. The diagnostic stores only the immediate cause class, not the deeper socket exception/errno. A TCP reset is plausible, but unproved.
- httpcore `_async/http11.py:209–240` raises RemoteProtocolError either from h11 protocol parsing or from an empty read while awaiting a response. AnyIO clean EndOfStream is converted to `b""` by the backend. The observed class is **consistent with a peer close before headers**, but the diagnostic intentionally omits exception messages, so the specific “Server disconnected without sending a response” branch cannot be distinguished from another h11 RemoteProtocolError.
- Error cleanup closes the non-completed HTTP/1.1 cycle. It is an effect of failure, not evidence that pool cleanup initiated it.
- A header-read failure is an **unknown request outcome**, not a retry authorization. Although these particular synthetic correction IDs are designed to return 404, the same failure class on a real mutation would not establish non-execution.

### What server evidence does and does not corroborate

The retained log has 7,769 JSON lines, 900 WARNING records, and response-start/completion-message counts **200:2702, 422:900, 404:898, 499:120**. The producer's metrics snapshot has one fewer 200 because its metrics response is counted after that snapshot is constructed. These totals are consistent with the two missing timed 404 responses. All-server `errors_total=0` and the unhandled-exception marker gate pass.

However, `RequestPolicyMiddleware.policy_send` logs “request completed” **before** `await send(message)` and increments metrics at `http.response.start`, not after successful body delivery. A completion message is not a TCP-delivery receipt. The sidecar has no request IDs/socket IDs to join either failed call to a server record. Aggregate consistency does not prove whether either request entered ASGI, where a connection closed, or why.

The two failures occur in mixed personas **before** the script deliberately abandons 120 sessions. `launch_torture.py` awaits completion of all personas before opening/closing the abandon connections. That later deliberate-close phase cannot cause these earlier failures. Eight readiness ConnectErrors are startup polling observations, not timed transport losses.

Also, `error_latency_ms` in both producers filters status ≥400: **status 0 is excluded**. The frozen 4,831.152 ms error maximum is a completed error-response latency, not either transport failure's latency. The separate status-mismatch gate correctly remains failed.

## 3. Keepalive lifecycle: viable race, not demonstrated cause

Actual source root: `/data/axiom-venv/lib64/python3.13/site-packages/`.

### Client

- `httpx/_config.py:173–182`: `Limits` defaults `keepalive_expiry=5.0`. The torture script sets max connections and max keepalive connections to concurrency, leaving expiry at five seconds.
- `httpcore/_async/http11.py:243–256`: only a completed bidirectional h11 cycle becomes IDLE; the client then starts its idle expiry clock.
- `httpcore/_async/connection_pool.py:270–339`: pool assignment removes closed/expired connections and chooses available same-origin connections.
- `httpcore/_async/http11.py:274–294`: `has_expired()` checks both the monotonic idle deadline and idle socket readability, which can reveal a peer disconnect. `_backends/anyio.py:85–94` delegates readability to a raw-socket poll. This is a point-in-time check, not an atomic reservation against a future peer close.
- `httpcore/_async/http11.py:65–86`: starting a request sets the connection ACTIVE and clears its client idle deadline. There is no periodic five-second client timer that kills an active response read.
- `httpcore/_async/connection_pool.py:225–239`: ConnectionNotAvailable can cause reassignment before successful handling; it is not retry of the observed ReadError/RemoteProtocolError after sending.
- HTTPX transport defaults retries to zero. httpcore's configured connection retries apply to connection establishment, not replay of these header-read failures. The existing wrapper neither replaces transport nor adds retries.
- Normal pooled response release follows stream close (`PoolByteStream.aclose`, `_async/connection_pool.py:409–422`). The producer uses non-streaming `request` and reads the body before giving back its semaphore slot. There is no visible early slot-release/unread-body defect here.

### Server

- `uvicorn/config.py:228`: default keepalive timeout is five seconds; neither existing producer passes a keepalive override.
- `uvicorn/protocols/http/h11_impl.py:322–338`: on response completion the server schedules a five-second `call_later` idle close.
- `:172–176`: receiving new data cancels that timer before parsing.
- `:364–372`: the timer sends h11 ConnectionClosed and closes the transport.
- `:522–525`: response completion may also close for MUST_CLOSE/no-keepalive; shutdown has its own closure path.

Server idle time starts at response completion; client idle time starts after it consumes/closes that response. Equal nominal values therefore do not synchronize their deadlines. A peer-close-versus-reuse race remains possible between the client's availability check and server receipt/cancellation of the idle timer. A delayed client or server event loop can widen that opportunity.

**Missing proof:** connection identity, previous-response end time, client idle age/expiry decision, server timer firing, socket error/FIN/RST, and paired event-loop lag. The failed request itself lasted less than five seconds, but that neither proves nor disproves a five-second *preceding idle* expiry. A slow actively processed request is not automatically subject to Uvicorn's idle timer: new incoming data cancels it. Do not convert “GIL can delay callbacks” into “keepalive kills slow extraction.”

No timeout/expiry change, retry, client replacement, HTTPX downgrade, or server dependency upgrade is justified by this evidence.

## 4. Native hostile tail with admission zero

The frozen native full report has hostile **500×422 +100×404**, zero transport errors, client error maximum **260.434 ms**, policy-to-header maximum **222.834 ms**, and admission-wait maximum **0 ms**. The native accelerator report also fails the unchanged <200 ms gate, with hostile client max **345.861 ms**, policy max **326.561 ms**, admission max **0 ms**. These are separate runs, not a matched accelerator-benefit experiment.

This proves that a server-policy interval exceeded 200 ms independently of HTTPX. It does **not** establish which hostile variant produced the maximum, nor that the slowest client request was the slowest policy request. Never subtract these aggregate maxima to estimate network time.

The server's `app` clock begins inside ASGI policy and stops before logging and header transmission (`overlay/request_policy.py:38–77`). It includes awaited metadata work, scheduling delays, validation and app execution. It excludes earlier socket/ASGI scheduling, the subsequent completion-log formatting, and actual header/body delivery. Node's timer includes the HTTP-agent/socket path through response-body end (`benchmark_ingress.mjs:34–68`).

Zero admission time means no recorded gate enqueue→grant wait, rounded to the report's precision. Five hostile variants fail ingress/schema validation **without acquiring an extraction permit**. The valid string `/etc/passwd` reaches `_document_call` and path metadata, then returns 404. A permit acquired immediately also records zero. Neither case excludes metadata executor waiting or event-loop contention.

The metadata pool has `max(1,min(4,EXTRACTION_WORKERS))` workers, while extraction permits include the CPU workers plus configured queue capacity (`overlay/server.py:384–420`). `_submit_document_stages` submits metadata only after one permit is acquired; it has its own bounded-admitted executor backlog (`:828–877`). `resolve_sandbox_path` performs canonical resolution/fixture-root resolution and currently evaluates `resolved.is_file()` **before** checking `permitted` (`:647–680`). A denied target stat is unnecessary. Filesystem latency, cold thread creation, metadata backlog, and delayed delivery of future completions are concrete candidates, not measured breakdowns.

Hostile precedes extraction_burst and personas in both producers, and the health phase does not submit document pipeline work. Therefore **later extraction work, evidence publication, and mixed-persona CAS cannot explain the earlier hostile-only tail**. Readiness does startup/store/path checks, not the measured memo extraction pipeline. Unknown external host load/background work is not ruled out.

### GIL and event-loop paths

- Current Python has the GIL enabled. ThreadPoolExecutor lanes isolate queues, not Python interpreter execution. `orchestrator_lock` is actually an alias for `_BoundedGate`, a semaphore admitting multiple pipelines (`server.py:723–746`), not a single global mutex serializing all CPU work.
- Classifier keyword/regex scans, text ingestor chunk/dataclass loops, orchestrator loops/grounding, and publication serialization include Python work (`kairo/core/classifier.py`, `kernel/sidecar/ingestor.py:79–170`, `orchestrator.py:65–245`). They plausibly compete with asyncio during mixed workloads. There is no per-thread/GIL timing here to quantify that competition.
- Tiny hostile payloads still undergo synchronous `_contains_surrogate`, error sanitation, `jsonable_encoder`, JSON rendering, and warning logging on the event-loop path (`server.py:94–125,1743–1785`). Their individual cost is unmeasured; attributing >200 ms to one scan or encoding call is unsupported.
- `_NonBlockingQueueHandler` makes sink writes asynchronous, **not formatting**. It installs JsonLogFormatter on QueueHandler; installed stdlib `/usr/lib64/python3.13/logging/handlers.py:1473–1509` formats during producer-side `prepare`. Validation WARNING formatting is within the app interval; completion INFO formatting is after the app sample but before header send, and may delay other tasks.
- Filesystem, socket, lock waits and some extension operations can release the GIL. Installed NumPy headers provide thread-release macros, but that is not proof this hostile route calls NumPy or releases the GIL. No NumPy operation lies in the inspected hostile rejection path. The independent “native” result means **Node's HTTP client**, not a GIL-free server pipeline.
- Mixed source/correction calls additionally share EvidenceStore's RLock with publication and review transactions (`evidence_store.py:188–224,256–284`). Review opens `BEGIN IMMEDIATE` before discovering a missing extraction. This can delay mixed requests; it cannot explain the preceding hostile phase or establish a transport-close mechanism.

## 5. Minimal falsifiable next test — proposal only, not executed

With the existing scripts and frozen telemetry, no test can conclusively attribute a specific pooled close to idle expiry. The minimal useful question that *is* falsifiable is:

> Does the independent client's hostile >200 ms server-policy tail reproduce in a fresh process without any successful extraction/persona/abandon phase?

Use the existing **ingress-only default** of `benchmark_ingress.mjs`, at the same concurrency 100, on unchanged HEAD and the same dependency environment:

```sh
cd /data/axiom-integration
PYTHON=/data/axiom-venv/bin/python node scripts/benchmark_ingress.mjs \
  --repo /data/axiom-integration --concurrency 100 \
  --output /data/axiom-v82-native-ingress-only-100.json
```

This is a proposed later-authorized local-only run. Do not execute under this read-only review. Preserve the inherited environment/settings rather than adding log-level, timeout, worker-count, BLAS, transport, threshold, or retry overrides. Record that environment's relevant non-secret settings and dependency versions before any authorized run. Both producers already remove the provider key/test-mode flag internally; do not introduce provider/network traffic.

The script's default performs readiness, health1000, hostile600, metrics and shutdown; omission of `--full` selects an existing mode, not an edited producer or changed payload mix. It reduces work but does not reduce concurrency or the hostile request count.

- **If hostile policy max ≥200 ms with admission max zero:** recurrence independently confirms an ingress/metadata/scheduling tail without successful document pipeline work. It falsifies the claim that prior heavy extraction is necessary for this tail. It still cannot distinguish metadata wait from event-loop/GIL/logging delay.
- **If client max ≥200 ms but policy max <200 ms:** the observed violation is outside the captured policy maximum in this run; no per-request decomposition follows from unpaired maxima.
- **If both remain <200 ms:** this bounded sample does not reproduce the failure. It does not erase the frozen failure, certify the full workload, or prove a fix.
- **Important:** ingress-only mode does **not** construct the full `diagnostic_gates`/`passed_requested_bounds`. Its exit zero is not a strict latency pass. Evaluate the unchanged <200 ms requirement from the reported hostile distribution and retain telemetry/log/shutdown evidence. Do not modify the producer to add gates.

For transport recurrence on the current tree, a separately authorized rerun of existing `diagnose_launch_transport.py --repo ... --concurrency 100 --output <new path>` retains the exact full Python producer and its gate result. It costs a full workload, not diagnostic implementation, and still lacks socket idle identity/timer/errno observations. A disappearing or recurrent error is not a keepalive causal experiment. Reserve it for a bounded baseline/acceptance plan, not an unlimited retry-until-green search.

To decide the precise transport mechanism would require explicitly authorized additional socket lifecycle observations that the frozen sidecar does not provide. Do not add them silently, rename the diagnostic, or reset its 5/5 budget.

## 6. Safe candidate and server5 spending rule

**Candidate, not implemented:** inside `resolve_sandbox_path`, replace the conjunction

```python
if resolved.is_file() and permitted:
```

with

```python
if permitted and resolved.is_file():
```

The same canonical path is still resolved and authorized; successful permitted paths still require `is_file()`. Denied candidates still end in 404. This prevents an unnecessary target stat after a negative authorization decision. It does not remove `Path.resolve()` or all filesystem I/O and does not bypass admission. It has no claimed direct effect on pooled response-header disconnects.

If the parent explicitly elects to spend server5, limit it to this one runtime change and an agreed bounded validation plan. Keep:

- one extraction permit **before** metadata submission;
- completion-owned release and shielding of the composite future;
- CPU-stage re-resolution of the original reference before bounded byte reads;
- credential/tenant, upload custody, TTL, path containment, byte caps and evidence CAS/atomicity;
- unchanged gates, <200 ms bound, status expectations, no timed transport losses, zero all-server 5xx, resource/shutdown requirements, and both independent full producers for actual acceptance.

Inspect existing preflight/admission/disconnect/security regression coverage without editing its ground truth. An eventual narrow-test pass cannot substitute for the failed full load gate or human evidence. Preserve every failed checkpoint and exact environment/source identity.

**Recommendation remains not to spend server5 yet:** the candidate's safe behavior is apparent, but the trace does not connect the unnecessary stat to the worst hostile response, and it supplies no transport remedy. Do not consume the last runtime opportunity on process-pool rewrites, more threads, cache/bypass lanes, pre-admission pathname shortcuts, review-transaction redesign, quieter logs, larger timeouts/thresholds, or deleted admission guards. Those are not causal fixes demonstrated here.

## Bottom line

Established: two pooled header-read failures; a distinct independent server-policy hostile tail above 200 ms; zero recorded hostile gate waiting; and a concrete unnecessary denied-path stat.

Unestablished: the offending socket's close reason, a five-second expiry event, an HTTPX implementation fault, the specific GIL/metadata/logging contribution, and any validated fix of either launch blocker.

The remaining work is an explicitly authorized bounded reproduction/attribution decision, not another silent diagnostic cycle or a manufactured pass. **NO-GO and all inherited freezes remain intact.**