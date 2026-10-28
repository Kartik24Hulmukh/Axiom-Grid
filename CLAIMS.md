# Axiom-Grid — Release-Specific Claims Register

**Controlling profile:** authorized explicit-text engineering preview.
**Status:** not production-qualified. This register supersedes broad launch claims
in historical reports. Test source is not proof of passing tests; see the branch's
[latest continuation verdict](docs/CONTINUATION_VERDICT.md) for executed evidence.

| Claim | Evidence type | Boundary / limitation |
| --- | --- | --- |
| Preview accepts explicitly supplied text and displays a suggestion | `phantom-overlay/dist/app.js`, frontend tests | Mocked IPC tests do not prove a live model or compiled native app |
| Preview has no automatic-insertion UI command | Frontend/native command-allowlist source guards | Source-level guard, not whole-host behavior certification; legacy source still exists |
| Taskbar-visible, non-topmost default window | Tauri configuration and source guard | Native window behavior still needs target-OS verification |
| Clear session clears displayed context/result and suppresses late output | Frontend tests | No claim of secure RAM/clipboard/backend-log erasure |
| Generation/cancel/readiness are explicit requests | Frontend tests | Cancel acknowledgement is not measured backend-compute termination |
| Benchmark reports ingestion/signing measurements only | Benchmark code and regression tests | No semantic/citation quality or reliable tail SLA from small samples |
| Report verification requires caller-supplied trusted public key | Benchmark negative tests | Trust provisioning/rotation remains deployment responsibility |
| DSSE parsing and trusted authentication are distinct | DSSE negative/positive tests | Callback/key policy is caller responsibility; module tests are not independent interop certification |
| Extraction route reuses a single captured-byte parse with IDs/hash/page/bbox retained | Real spawned-parser and synthetic no-inference HTTP regressions | POSIX resource boundary, not OS sandbox or durable source retrieval |
| Loopback smoke evidence rejects malformed counts/cancellation and inconsistent reported model identity | Offline probe-unit fixtures | Tests of the probe, not an observed runtime/model deployment |
| Ignore rules cover private keys/env/build outputs | `git check-ignore`, source guard | Ignore rules neither revoke leaked keys nor remove historical tracked secrets |

## Explicitly forbidden release claims

- Production-ready, certified, compliant, injection-safe or universally reliable.
- Any-app Ghost typing, supported automatic desktop mutation or guaranteed undo.
- Cryptographic proof of no network traffic or a whole-machine air gap.
- Every agent action captured/signed or a shipped end-to-end OpenBot integration.
- Signature validity equals answer correctness, supported citations or legal quality.
- A local URL proves the backend computes locally.
- Legal-v3's same-host role keys are independent administrative principals.
- Legal-v3 bundle integrity verification reruns complete artifact-effect checks.
- Current native/full-suite pass counts inferred from old documents or test files.
- Guaranteed 100× impact, traction, revenue or billion-dollar outcome.

## Research surfaces that remain restricted

Legal-v3's execution-time expected edits derive from writer-reported applied edits.
Its bundle verification uses embedded keys and can infer execution pass from
integrity checks without rerunning readback. Events are synthesized after execution.
This is useful research, not independently complete approved-intent verification.

`/api/extract-document` now reuses one validated ingestion graph for classification
and orchestration; it does not reparse the source in the parent. Default POSIX process
mode parses captured bytes and has bounded JSON result validation. Thread mode is
explicit development-only. This is not an OS sandbox: child filesystem/network
privileges, ancestor-path races/local compromise, other ingestion routes, durable
source retrieval, tenant isolation and full-service intake qualification remain
outside this fix. Do not expose the whole Python service under a sandbox claim.

The loopback probe checks reported HTTP/model-metadata consistency, not real model
weights/locality, no-egress, native UI behavior, useful output or backend compute
termination. Exact-token evidence redaction is not universal DLP or secure erasure.

Legacy Phantom capture/injection/write code is not the focused preview. Keep it
out of the preview release and do not present its component tests as native E2E.

## Required evidence for a future claim

Record exact commit/build, dependency/model digests and licenses, OS/hardware,
commands, full denominator including failures/skips, raw result artifacts, threat
model, observation boundary, independent reviewer where relevant, and limitations.
Unknown/unsupported must not inherit pass. Correct false claims or remove the
unsupported feature rather than broadening the promise.
