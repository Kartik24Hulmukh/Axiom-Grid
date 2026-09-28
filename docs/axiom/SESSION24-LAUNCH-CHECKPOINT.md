# Axiom-Grid launch hardening checkpoint — NO-GO

Date: 2026-09-16. Target launch: September 17–18, 2026.
Audited main: `831b26fda3918219308edd5c0320dafce2f423c0`.
Branch: `harden/axiom-grid-v1-launch`. No release merge is authorized by these results.

## Executive decision

**Do not launch or auto-merge.** Focused tests pass, but the full suite is not green, loaded error latency exceeds 200 ms, and the real extraction queue sheds 79/200 requests as HTTP 503 in the measured burst. These are intentional admission rejections, not demonstrated crashes. Zero crash markers were observed, but zero socket/coroutine leaks and production-scale readiness are NOT proven.

This was one agent evaluating product, architecture, and red-team perspectives—not an independent council or 100 real people. The harness runs 120 deterministic synthetic clients (eight behavior classes, distinct seeds), not 120 independent human evaluations. 100 concurrent requests versus one client is a concurrency comparison, not evidence of 100x production traffic or horizontal scalability.

## Inputs and baseline freeze

Both attached Python harnesses were inspected and hashed in `baseline_manifest.json`. Both index 600 fuzz requests into only 552 bodies; running the original reproduces `IndexError`. They also discard intermediate request outcomes, hardcode recovery 5xx to zero, suppress server logs, label a final RSS snapshot a ceiling, and do not enforce all claimed gates. The original therefore cannot produce a trustworthy launch pass.

`repos.md` is absent from the ZIP and recursive repository tree. **No catalog integrations claimed.** Existing upstream libraries were installed directly to reproduce the app: pytest/pytest-asyncio, Hypothesis, FastAPI, psutil, pdfplumber, python-docx, OpenTelemetry SDK, and additional domain test dependencies. Versions are in `environment.txt`. No speculative plugin or connector was added, and no license provenance was attributed to a missing catalog. `requirements.lock` contains version ranges rather than a reproducible lock.

Baseline before runtime edits: 9 failures / 345 passes in kernel+overlay+packs due to missing PDF dependencies. After installing PDF dependencies and adding the existing concurrency test scope: 360 passed, with resource warnings fatal. Main's latest CI had failed the Wave11 lint gate on import ordering and a broad exception catch.

## Delivered changes

- `fix:` sort server imports and narrow validation serialization recovery to expected encoding/type/value/recursion exceptions; restore the existing lint gate without disabling it.
- `test:` replace unreliable attached-harness assumptions with `scripts/launch_tcp_audit.py`: loopback-only real TCP, authenticated requests, temporary isolated state, real memo pipeline input, 100-client ingress and extraction queue bursts, 120 seeded synthetic journeys, 300 sockets abandoned without reading, all returned response outcomes counted, sampled RSS/FD/thread observations, four probes, failure exit codes, explicit missing-evidence gates, and 14 audit regressions.
- Shutdown completion is observed after the real ASGI lifespan exits. Uvicorn 0.51 re-raises SIGTERM after graceful cleanup, so `-15` alone is not proof of a crash; a lifecycle marker is also required. Async log queues may lose final shutdown text, so that text is not used as proof.
- Existing circuit breakers, durable spend ledger, JSON stdout logging, and opt-in OpenTelemetry are retained and tested, not replaced by cosmetic mocks. Production telemetry deployment/exporter receipt was not performed.

## Five-point premortem and disposition

| Lens / failure vector | Evidence and disposition |
|---|---|
| Product: false launch confidence and broken journeys | Original harness crashes; replaced with fail-closed audit and explicit synthetic scope. Browser navigation to local app blocked by environment. Real browser/manual UX validation remains open. |
| Architect: starvation and queue overload | Real extraction burst: 121 accepted, 79 HTTP 503 at 100 clients. Bounded admission works, but capacity/SLO target fails. Do not blindly enlarge queues. Profile worker service time and size per tenant/replica. |
| Chaos: malformed JSON, lone surrogates, abandoned sessions | 720 fuzz responses: 610×422, 90×400, 20×404; no transport errors or exception markers. 300 raw-socket abandonments sent. Existing surrogate latency regression fails under competing host load. |
| Architect: memory, coroutine/socket cleanup | RSS sampled; final FDs 12→11 and real lifespan completes. Short runs do not prove leak freedom; coroutine census, sustained soak and replica crash/restart testing remain open. |
| Founder/security: spend, model availability and red release gates | Four real bounded model calls pass; existing fault-injection tests cover 429/5xx/half-open/budgets. Full-suite red and exposed credentials block release. Rotate both supplied credentials immediately. |

## Measured benchmark deltas

Baseline and verified runs used the same loopback workload, with no external model calls. They are single runs, not statistically controlled performance claims; later queue audit competed with other host work. The runtime patch is a validation/lint correction, not an optimization.

| Scenario | N | Baseline P50/P95/P99 ms | Verified P50/P95/P99 ms | Baseline → verified req/s |
|---|---:|---|---|---|
| Health, one client | 200 | 0.977 / 1.388 / 2.193 | 1.091 / 1.420 / 1.613 | 905.95 → 856.84 |
| Health, 100 clients | 1000 | 109.253 / 198.089 / 202.110 | 100.836 / 184.412 / 192.284 | 811.43 → 847.70 |
| Fuzz, 100 clients | 720 | 172.449 / 250.099 / 252.140 | 166.812 / 251.418 / 254.911 | 537.32 → 522.21 |
| 120 synthetic clients | 3000 recorded responses | 89.393 / 1429.172 / 1845.605 | 91.730 / 1566.603 / 1899.170 | 324.41 → 306.69 |
| Recovery after load, one client | 120 | 1.737 / 2.279 / 3.546 | 1.752 / 2.404 / 3.572 | 405.20 → 371.74 |

Sampled RSS baseline 97.93–164.29 MiB; verified 97.75–165.81 MiB. Verified FDs 12→11 after bounded drain observation, lifespan shutdown 0.164 s. No transport errors / 5xx in the 5,040 recorded-response workload (plus 300 abandoned sockets and uncounted warmup/probes).

**Expanded queue audit (final workload):** 5,240 recorded responses plus 300 abandonments. Extraction queue N=200, concurrency=100: 121×200 / 79×503, P50=327.324 ms, P95=546.260 ms, P99=603.741 ms, 252.95 req/s. Overall sampled RSS 97.62–168.26 MiB; shutdown 0.214 s; FDs 12→11; no exception markers. Queue run exits failure. Unsaturated recovery max=83.152 ms, P99=3.495 ms, but saturated fuzz P95=367.744 ms. **Sub-200ms recovery under all load conditions is not achieved.**

## Validation matrix

| Validation | Result |
|---|---|
| Focused kernel, overlay, packs, concurrency, new audit tests | **374 passed / 0 failed**, isolated repeat, 23.50 s, ResourceWarning and PytestUnraisableExceptionWarning fatal |
| Same focused scope under simultaneous TCP load | **373 passed / 1 failed**: surrogate burst P50 about 233 ms exceeds 200 ms. Preserved, not hidden by isolated repeat. |
| Audit gate unit tests | 14 passed |
| Wave11 changed-file lint | Pass (two baseline violations fixed) |
| Full collection, original environment | 3,068 collected; 28 collection errors (missing deps plus duplicate test module names) |
| Full suite, importlib mode + partial deps | 228 passed / 20 failed / 4 skipped; stopped at 20 failures |
| Full suite, additional documented deps | **827 passed / 20 failed / 17 skipped**, 29.93 s; stopped at 20 failures. EPUB, podcast, media, and trace/PII receipt paths remain failing. Not an exhaustive final failure count. |
| Node preview regressions | 17 passed |
| Undrained stdout/stderr stress | 2,000/2,000 health responses 200; 1,716 log records shed; shutdown 0.164 s; post-warmup RSS growth 7,274,496 bytes |
| Auth gauntlet | 1,000 requests / 100 threads, ten traffic classes, no transport errors; all invariants passed |
| Browser E2E / native desktop / Rust | Not executed here (local browser target blocked; Rust toolchain absent). Prior remote CI evidence is not a substitute for validating this head. |

## Melious production smoke and routing

GET `/v1/models`: HTTP 200, 329 ms. All four configured default model IDs were present. Four sequential **real router** calls used 128 max completion tokens each, no retries, timeout 10 s / total budget 12 s, local admission ceiling 1,000 tokens per router. Returned usage: 28, 73, 236, 50 total tokens (387 combined); all reservations settled to zero. Latencies in default order (GLM-5.3, GLM-5.3 Flash, Kimi K3, Qwen 3.8 27B): 9,185.439 / 1,330.005 / 3,750.507 / 875.500 ms. Exact provider IDs are in the JSON evidence. No claims about fictional/unverified model identity beyond provider catalog and responses.

This is bounded production smoke, **not production gateway torture**. 100-worker router fallback, cooldown, half-open, usage validation and spend tests ran locally with explicitly injected faults. We did not deliberately overload a shared external provider or incur uncontrolled spend. Fleet monetary caps require provider-side billing enforcement; estimates and a SQLite ledger alone are not hard billing guarantees.

## Merge and launch gate

Branch synchronized with audited main without overwriting existing branch history. Atomic fix/test/evidence commits are proposed via a PR. Auto-merge intentionally withheld: definition of done is unmet even if focused CI turns green. No secrets are committed. Revoke/rotate the user-posted GitHub PAT and Melious key; use scoped CI secrets thereafter.

Required next steps: provide `repos.md`; provision the complete supported test environment; fix remaining domain and trace failures; establish a production baseline and SLO definition separating admission rejection from crash; run repeated isolated and contended tests, multi-replica/long soak tests and actual browser/human UX; verify deployed telemetry; rerun CI on the exact candidate; only then review merge/release. Convergence: no module underwent more than five remediation cycles (harness checkpointed after five load runs); failing full-stack modules escalated rather than patched blindly.

## Reproduction

```sh
python3 -m pytest --import-mode=importlib -q --maxfail=20
python3 -m pytest kernel/tests overlay/tests packs/tests tests/test_concurrency_safety.py tests/test_launch_tcp_audit.py -q -W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning
python3 scripts/launch_tcp_audit.py --output runs/launch-tcp.json
python3 scripts/stress_wave11.py
python3 scripts/stress_sec006_gauntlet.py 1000 100
node --test phantom-overlay/tests/app.test.cjs
```

Evidence is under `docs/axiom/evidence/session24-launch/`. Original attachments are not silently edited; the new harness replaces their faulty measurement design.
