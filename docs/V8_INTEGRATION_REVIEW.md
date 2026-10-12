# V8 integration review — draft only, launch NO-GO

## Outcome

This candidate preserves current upstream main `aa386b49f19e160491a8e7225cc01b391ae2e522` and the recovered local hardening work. It is an integration review, not production authorization. Main's newer AES-GCM export, fail-closed authentication, OpenBot adapter and verifiable benchmark were merged rather than overwritten. The only merge conflict was README wording; the resolution distinguishes the Rust receipt lane from the Python overlay API.

The validated runtime revision is `6fde229`; `f4a7da6` then pins the already-tested Model2Vec 0.9.0 interface. Final browser and loader/diagnostic replays ran after that pin. The final documentation commit does not alter runtime.

## New remediation

- Serialize cold SQLite WAL/schema setup across processes. Do not close duplicate live database descriptors that release process-wide POSIX locks.
- Integrate bounded metadata-then-CPU document routing. One logical extraction permit is acquired before metadata and held until native completion; CPU work revalidates the original reference. Frozen admission guards were not weakened.
- Disable unauthenticated LAN sync rather than advertise it as safe.
- Close denied-egress probe sockets on every exit path in owned oracle helpers and tests.
- Load real local Model2Vec assets through the public StaticModel constructor with explicit config/tensor lifetimes. Tensor, tokenizer, config, metadata and encoded outputs match the real upstream loader exactly on the retained assets. No model mock, network fallback or installed third-party source patch is used. Compatibility is pinned to tested 0.9.0, not claimed for the prior >=0.1.1 range.
- Correct the imported demo-name regression by executing the actual `kairo.cli redline --help` command. Do not invent an `axiom.cli` module just to match branding.
- Add bounded diagnostic-only HTTPX/httpcore traces around the unchanged TCP producer. No retry or gate modification. Reserve retention for late status-0 failures after ordinary details fill.
- Make CI/Makefile shell-gate calls explicit `bash` invocations. Gate contents, warning policy and strict thresholds remain unchanged.

## Validation and scope

| Gate | Result |
| --- | --- |
| Established strict pre-push gate | 582 passed; lint and runner compilation passed |
| Expanded offline Python scope: overlay/tests, kernel/tests, packs, tests, bench, OpenBot, imported export security and memory tests | 1,827 passed, 2 skipped under ResourceWarning and pytest unraisable warnings as errors |
| Real browser functional suite | 9 passed |
| Authenticated browser suite | 11 passed |
| UX/a11y automated suite | 23 passed |
| Final pinned-loader and diagnostic contracts | 18 passed |
| Resource council complete narrow suite | 49 passed |
| Original producer instrumented 100-client workload | FAILED: two timed transport losses and >200 ms loaded errors |
| Whole-repository collection with --import-mode=importlib | 3,762 collected; collection only, not a full execution pass |

Suites overlap; do not add these counts. Browser tests and 120 deterministic identities are not recruited humans. The two broad skips remain the missing authoritative training release asset and missing actual cross-platform workflow. The Starlette deprecation warning remains visible. Rust/native platform/container/remote checks are not locally certified.

### Failed evidence retained

- Earlier expanded strict run: 10 failed, 1 error, 1,790 passed, 2 skipped. Root causes included real config/socket resource lifetime defects and the imported nonexistent demo-module assertion. Fixed without filtering warnings or weakening denied-egress assertions; successful expanded replay above is separate evidence.
- Initial root collection: two duplicate module-name errors. Importlib-mode collection resolves naming, but all 3,762 cases have not been executed.
- Resource cycle1 selector typo ran no tests; cycle2 retained 48 pass/1 new test-method AttributeError; authorized cycle3 corrected that new test and passed all49.
- Supplemental import-order lint reports two I001 findings in frozen diagnostic files. Mandatory E9/F and diagnostic contracts pass. Do not label every lint policy green; no further diagnostic implementation cycle is authorized here.
- Unchanged native workload failed before and after isolated uvloop/httptools installation. Accelerators were removed and not added to production dependencies.

## Wire benchmark (instrumented, local loopback only)

Tracing adds overhead. This is attribution evidence, not a deployment-equivalent untraced benchmark or matched performance A/B experiment. The original workload, counts, expected statuses and <200 ms maximum error bound were retained.

| Phase | Requests | Status counts | Overall P50 / P95 / P99 ms | Error max ms | Throughput req/s |
| --- | --- | --- | --- | --- | --- |
| health | 1000 | 200:1000 | 121.878 / 534.56 / 818.836 | — | 532.97 |
| hostile | 600 | 422:500, 404:100 | 140.504 / 552.526 / 840.535 | 1109.136 | 477.97 |
| extraction_burst | 300 | 200:300 | 3700.077 / 3835.001 / 3888.503 | — | 26.47 |
| 120_synthetic_personas | 2400 | 200:1200, 422:400, 404:798, 0:2 | 56.616 / 4287.283 / 4434.844 | 4831.152 | 72.26 |
| post_abandon_recovery | 200 | 200:200 | 877.072 / 2172.157 / 2362.007 | — | 81.09 |

Resource sample: RSS floor 74,539,008 bytes / ceiling 100,954,112 bytes; FD floor17 / ceiling118; thread ceiling15; 919 samples. FD returned to idle, no observed 5xx/unhandled markers, worker/state shutdown markers passed. These are bounded-run observations, not proof of zero leaks or a 24-hour soak.

Two timed mixed-workload failures were retained: `/correct` raised httpx.ReadError/httpcore.ReadError with an anyio.BrokenResourceError at response headers; source lookup raised httpx.RemoteProtocolError/httpcore.RemoteProtocolError at response headers. Eight separate startup connection-refused polling observations are not counted as timed workload failures. No transport detail was dropped; 2,926 ordinary details were dropped by the explicit cap. The diagnostic captures neither request bodies, credentials nor exception messages. Header-read failure classification does not establish the root cause or outcome of an unobserved mutation.

### Benchmark deltas

No credible matched latency/RAM/throughput improvement delta is asserted. The retained pre-integration untraced HTTPX run and this instrumented run differ in tracing and source; native-client samples use another producer. Raw P50/P95/P99 and resource evidence are retained for comparison, but subtracting them would not isolate an architectural effect. A quiet, deployment-equivalent matched baseline/candidate run is still required.

## Five-point council premortem and disposition

1. **Cold-start lock loss / corruption:** WAL activation before serialization and duplicate FD close hazards. The serialized setup/lstat fix closes the observed local failure; concurrency and custody tests remain active.
2. **Worker starvation / unsafe bypass:** missing-source denial queued behind CPU. Staged bounded metadata preserves admission and CPU revalidation; local scheduling is improved, full wire SLO remains failed.
3. **Resource lifetime / false clean tests:** leaked config handles and denied sockets. Explicit ownership plus strict warnings and real-model equality close the reproduced narrow failures.
4. **Security regression during publication:** newer main security commits absent from recovered branch. Merged and preserved them; no snapshot overlay from an obsolete base. Broader IAM/key custody/licensing/installers still require owner validation.
5. **Evidence loss / false launch claim:** finite diagnostics filled before late failures, or synthetic users labeled humans. Priority transport retention implemented; failed outcomes remain failed; evaluation/traction claims remain blocked.

## repos.md integration log

Reviewed the local catalog and prior council decisions. Reused existing Playwright/axe, OpenTelemetry and workload tools. Added only a pinned official Gitleaks8.24.3 scanner to the isolated workspace after checking its published release checksum; not a new application dependency. No gratuitous catalog framework was integrated. The local model loader reuses existing model2vec/safetensors/tokenizers assets and APIs, not new weights or an unverified download.

Redacted directory scan found15 findings: 12 tracked checksum/identifier/test or mock-key contexts and3 untracked bytecode duplicates. Review identified no live credential among those12 by context; this is not a clean scan or proof of revocation. Incremental history scan before final additions found one checksum-context finding. Existing chat and historical Melious exposure remains an incident-response blocker. No exposed credential or live provider call was used.

## Publication contract

GitHub MCP push_files constructs text snapshots and cannot preserve the reconstructed local commit graph. This candidate intentionally uses mode100644 for the two changed shell scripts and explicit bash invocations. The review branch starts from the integrated upstream main; untouched newer-main files must be retained. Publish sole-writer logical batches, then fetch and compare the complete remote Git tree against the normalized local candidate. A draft PR alone is not tree verification or a passing remote CI result. Never force-push, bypass checks, or merge a failed candidate.

The original atomic local commits and incremental bundle remain separate provenance. Do not export all history/refs or republish credential-bearing base objects as a sanitized artifact.

## Remaining launch blockers / required owner inputs

- Resolve both timed transport failures causally; diagnostics budget is frozen at5/5, requiring an explicit new investigation authorization rather than silent reset. Server/helper inherited budgets remain server4/helper1; no new server runtime cycle was consumed here.
- Pass unchanged <200 ms loaded error maximum in deployment-equivalent conditions, plus matched performance and soak/leak evidence.
- Supply/revoke/audit safe provider credentials and verify actual provider-supported model IDs, quotas, routing, token budgets, 429/5xx failover and circuit breakers. No assertion that requested frontier aliases are live or supported.
- Supply authoritative training release assets, supported cross-platform build/signing infrastructure, remote Rust/Python/Node/browser/container checks on a frozen SHA, clean-host installation and upgrades.
- Resolve PyMuPDF/EbookLib distribution policy, unverified/mutable installers, OS keystore custody, reviewed OIDC/JWKS/MCP authorization, person-level IAM, storage/TLS/key management and retention/erasure.
- Prove backups/restores, rollback, telemetry backends and monitored deployment/24-hour soak.
- Supply consented human participants and an approved evaluation/deployment profile; validate demand/commercial traction without fabricated metrics.

**Decision: draft integration review only. NO-GO for merge, production deployment, live sensitive intake, GA or 100x/traction claims.** Passing scoped tests does not waive any failed or unexecuted launch gate.
