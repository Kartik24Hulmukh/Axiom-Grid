# Axiom-Grid verified hardening checkpoint — 2026-10-01 (Asia/Calcutta)

**Decision: NO-GO for GA or automatic merge. Engineering preview/review checkpoint only.**

- Remote base: `8f381cf219098d03c0ae2d440681ed59beeaf99a`.
- Tested code checkpoint: `2d90ff35f5f26e3f6f09d96600386a59abecd040` on `harden/axiom-grid-v1-launch`.
- Delivery adds a documentation/evidence checkpoint after this code SHA. No GitHub push, PR, merge, deployment, live model call, customer outreach, grant submission or real-human recruitment occurred.
- Nine attached Markdown/catalog files and the replacement source zip were inspected; duplicate premortem copies recorded. All supplied credential values were treated as exposed and were not used.

## Completed, concrete changes

1. Applied the supplied bundle on the exact public base, after recording untouched failures.
2. Repaired a real browser parser failure that prevented Process Document from running. Replaced dynamic HTML/inline handlers with text nodes and listeners; removed external font loading; served one explicit public script under self-only script CSP.
3. Removed falsely verified simulated desktop writes. Native desktop execution is unavailable and fails closed. Importing the overlay no longer forces model-test mode.
4. Bounded complete preview I/O and execution in the same worker admission envelope as extraction. Cancellation/submission failure permit regressions passed. Completed preview provenance is bounded to the latest 128 graphs plus active work; durable SQLite history is not treated as a memory leak or silently deleted.
5. Fixed unsafe live-dict action lookup, caller/ingestor document identity mismatch and fabricated source-render URLs. Real extraction fields now link to retained source text/geometry; unknown/expired source evidence returns 404. No invented image or verified highlight is returned.
6. Hardened Melious destination configuration and refused bearer redirects. Tested actual loopback HTTP 429/503 cascades, cooldown, Qwen route, concurrent failures and permit/spend cleanup; not a real provider/model-quality test.
7. Implemented Open Receipt v0.1: bounded signed observations, SHA-256 linear hash chains, Ed25519 signatures, signed checkpoints, pinned-key verification, offline CLI, concurrent/tamper/property tests and synthetic public sample. It is not a Merkle tree, execution witness, citation certificate or zero-egress proof.
8. Inspected actual OpenBot AuditEvent types at upstream `afe623366945d6378dde5ea9c46322ac856c3047` (MIT). Added offline event export adapter and generic Opik/Helicone JSON-trace adapters. These are not live every-action SDK hooks or upstream-merged integrations.
9. Added real browser and strict-load CI producers. Optimised tiny local contexts to skip optional native compression while preserving exact text/geometry; reported token counts in this path are estimates, not provider admission bounds.
10. Restored accidentally base64-encoded ignore rules. Ran checksum-verified Gitleaks v8.30.1 (MIT) against tracked HEAD and full history, retaining redacted findings and explicit triage.

## Validation ledger

| Population | Fresh result | Scope/limits |
|---|---|---|
| Untouched focused baseline | 361 passed, 2 failed | Unreadable-file oracle and fixture fingerprint |
| Untouched broad baseline after available dependencies | 1,171 passed, 12 failed, 4 skipped | Initial attempt first failed collection due missing networkx; installation issue not silently treated as a code defect |
| Untouched real browser | Script syntax error; Process Document did nothing | One actual Chromium run |
| Final isolated focused gate | **418 passed, 0 failed** | Strict resource/unraisable warnings; one dependency deprecation warning |
| Final broad Python `tests/` | **1,183 passed, 0 failed, 4 skipped** | Skips: training dataset release asset, unavailable LibreOffice, missing PDF form fixture, missing cross-platform workflow |
| Kernel + packs | **215 passed, 0 failed** | Overlaps focused population; do not sum these counts into unique tests |
| Rust preview runtime | **28 passed**; fmt and Clippy clean | `axiom-runtime`, toolchain 1.98.1; not every legacy/Tauri crate or OS |
| Existing desktop JavaScript suite | **17 passed** | Does not prove native desktop writes |
| Real browser E2E | **6 passed** | Includes one explicitly isolated intercepted-response XSS oracle; other flows use actual local API |
| Dependency consistency | `pip check`: no broken requirements | Declared broad native embed dependency eventually built; no skipped install represented as completed |
| Literal 100x scaling | **Unverified** | 100 clients is not 100 times a measured production baseline |
| 100 actual humans | **Not performed** | 120 scripted IDs, six behaviour templates, 20 sequential interactions each are synthetic, not recruited people |

An earlier focused run overlapped other CPU-intensive validation and failed its surrogate P50 gate (212.07 ms). The last serial run passed unchanged at the same code checkpoint. That earlier failure is preserved, not erased or fixed by relaxing the threshold. The much stronger TCP bounds below still fail. No unsupported full-denominator/100%-green-platform claim is made.

## Matched local TCP measurements — not production capacity

One serial pair, same two-CPU host, one synthetic auth key with its quota raised to 20,000/minute to isolate admission rather than quota rejection, 100 concurrent-client limit, 4,500 measured calls per revision plus 120 deliberate socket abandonments. Startup/readiness/metrics calls and abandoned sockets are excluded from those 4,500 measured calls. Quantiles use nearest-rank per phase, not pooled per-phase percentiles. Three P95 phases worsened; two improved. Status populations differ because source responses were corrected; error-only percentiles must not be interpreted as identical pre/post cohorts.

| Phase | Before P50/P95/P99 ms | After P50/P95/P99 ms | Before/after req/s | After status counts |
|---|---|---|---|---|
| health | 238.46/2143.75/3471.34 | 477.85/2284.38/3332.19 | 166.61 / 125.12 | {"200": 1000} |
| hostile | 274.31/1142.56/1932.49 | 642.87/2309.44/2701.80 | 231.37 / 107.48 | {"404": 100, "422": 500} |
| extraction_burst | 1877.30/7447.01/8409.35 | 2618.64/8326.46/9451.31 | 24.76 / 19.80 | {"200": 42, "503": 258} |
| 120_synthetic_personas | 4440.70/13352.35/14597.95 | 4212.66/12582.10/13452.73 | 17.83 / 18.88 | {"200": 1130, "404": 400, "422": 400, "503": 470} |
| post_abandon_recovery | 1710.59/2761.08/2777.82 | 1908.79/2344.10/2354.05 | 45.08 / 50.68 | {"200": 200} |

- 503 counts: **726 before / 728 after**. These are explicit admission failures, not automatically process panics, but fail the requested zero-5xx gate.
- Worst measured after error response: **5994.479 ms**, versus requested <200 ms.
- RSS: before **69.89–130.15 MiB**; after **69.84–120.82 MiB**. One short observation cannot establish a leak-free ceiling or 24-hour stability.
- FD snapshot after workload/client closure: **11 → 110**. This snapshot was taken without a demonstrated quiescence/drain barrier; it does not diagnose 99 leaked sockets, but cannot pass the requested return-to-idle proof.
- Shutdown wait: **4385.262 ms**, return code **-15**, timeout **False**. Application-shutdown completion marker **False**. Expected SIGTERM and async log loss may affect this marker; the clean-shutdown proof gate remains failed, not described as a confirmed timeout/crash.
- Observed unhandled ASGI/task/fatal-Python markers: zero in this bounded sample. Not a universal zero-crash guarantee.

Strict gate ledger: `{"clean_shutdown": false, "fd_returns_to_idle": false, "loaded_error_max_below_200ms": false, "no_harness_error": true, "no_status_mismatches": false, "no_unhandled_exception_markers": true, "workload_complete": true, "zero_5xx": false}`.

## Catalog integration and secret-scan log

- Actual test-only Playwright 1.63.0 dependency/lock and actual Chromium workflows; no framework vendoring.
- Actual Gitleaks v8.30.1 binary checksum and MIT license verified. Default rules plus explicit Melious-token rule used, not a broad suppressing allowlist.
- HEAD: nine generic-rule findings were inspected as synthetic attack/test strings, a public file checksum and an identifier false positive. Redacted findings/triage remain available; no assertion that a heuristic scan proves absence of all secrets.
- Full history: 12 findings including **one confirmed historical Melious-token finding** in `scripts/session21_melious_torture.py`; other findings remain documented as legacy test/pattern material. Removing a credential from HEAD cannot revoke it, clear forks/copies or undo chat exposure.
- Existing OTel/W3C correlation, JSON logging, health/readiness/Prometheus retained. Real SDK in-memory tracing tests passed; no production OTLP collector receipt was obtained.
- Unrelated voice/trading/offensive/platform repositories were not installed; no catalog curl-pipe installer was executed.

## Blocking definition-of-done gates

1. Owner revokes/reissues both exposed credentials, audits usage and stores replacements securely. No fresh securely provisioned GitHub/model credentials were present here.
2. Resolve loaded latency/admission behaviour against approved burst/shedding SLOs; verify drain/quiescence and logging reliability; run repeated workload tests, replica chaos and 24-hour soak.
3. Close four skips and test all supported OSes, native desktop writer/read-back, legacy/Tauri builds, clean installs, signed binaries, actual deployed website and rollback path.
4. Live provider catalog/quality/failover and capped spend testing with rotated credentials; production tracing exporter and external independently pinned receipt verification.
5. Consented real-human feedback and real pilots/traction; no invented adoption, compliance certification, fundraising terms or revenue.
6. Required checks/review on protected main at final PR SHA. Do not auto-merge this checkpoint merely because focused tests pass.

See `docs/RESEARCH_EXECUTION_LEDGER.md` for the entire research deliverable/gap mapping. Remediation was checkpointed within the five-cycle cap per failing module; the failed operational bounds are escalated rather than hidden with sleeps, mock success, changed thresholds or more unbounded retry cycles.

CSV null error maxima mean no error response was observed in that phase, not a measured zero-millisecond recovery. The benchmark table grain is revision × phase; numeric values are not identity keys.
