# V7 hardening checkpoint — release remains NO-GO

Date: 2026-10-03  
Branch: `harden/axiom-grid-v1-launch-v7`  
Base checkpoint: `1f31d5183dfabab08097479708f32ad7f6f0e991`

This checkpoint improves the declared deployment envelope and secret handling.
It does **not** certify general availability, production deployment, traction,
live-provider routing, recruited-human evaluation, or automatic merge.

## Changes

### Candidate capacity and shutdown

- Fixed extraction, pipeline, evidence, parser-memory, and parser-CPU limits in
  the deployment definition instead of deriving concurrency from host-visible
  CPU count inside a 2-vCPU container.
- Enforced the shutdown order:
  `45s compose grace > 40s Uvicorn grace > 30s extraction deadline`.
- Added static deployment contracts so drift fails tests.

### Operational telemetry

- Added `axiom_process_resident_memory_bytes` to the application-owned
  Prometheus exposition.
- Replaced an alert that depended on an undeployed container exporter.
- Corrected load-shedding guidance from 429/scale-up advice to the actual
  bounded 503 behavior and a hold/investigate response.
- Removed unsupported multi-replica and worker-scaling instructions from the
  candidate runbook.

### Deployment-key custody

- Added `AXIOM_API_KEYS_FILE`, with bounded regular-file, ownership, and
  read-only checks.
- Changed the candidate Compose topology from plaintext environment injection
  to a mounted runtime secret.
- Retained `AXIOM_API_KEYS` only for local/CI compatibility and remove it from
  the process environment immediately after loading.
- Reject ambiguous file-plus-environment configuration.

## `repos.md` integration decision

No new catalog repository was added. Existing Playwright, axe-core,
OpenTelemetry, and Gitleaks-related work already covers the relevant
capabilities. Adding another framework would not resolve the measured
latency, transport, deployment, identity, encryption, or human-evidence
blockers and would expand supply-chain risk.

## Five-point premortem

1. **Worker starvation / OOM:** host CPU discovery over-provisions a constrained
   container. Mitigation added: explicit 2-worker/4-queue candidate envelope.
2. **Forced shutdown during valid work:** supervisor grace is shorter than the
   application deadline. Mitigation added: tested strict timeout ordering.
3. **Invisible memory pressure:** an alert references metrics not actually
   deployed. Mitigation added: application-owned RSS metric and alert.
4. **Credential disclosure:** accepted keys remain visible in the container
   environment. Mitigation added: runtime secret file; inline fallback is
   cleared and excluded from the candidate manifest.
5. **False scale-out recovery:** operator guidance increases workers or replicas
   despite uncertified shared provenance. Mitigation added: single-replica
   boundary and hold/rollback guidance.

## Validation

### Passed

- Strict pre-push gate: **579 passed**; ruff gates and runner compilation passed.
- Authentication/deployment focused tests: **38 passed**.
- Admission/request-policy/metrics focused tests: **14 passed**.
- The storage cold-initialization test passes alone and the complete
  storage-boundary file passes **29/29**.
- Worktree was restored after test-generated benchmark reports; source changes
  were not hidden by report churn.

### Failed or incomplete

- Broad suite, twice: **1 failed, 1,545 passed, 2 skipped**. The same
  four-process cold-initialization test timed out only in broad-suite order.
  Its isolated pass does not replace the retained failures.
- The two skips still require the owner-provided training release asset and an
  actual supported cross-platform workflow.
- Browser suites were not rerun in this checkpoint.
- No full 100-client wire benchmark, quiet-window transport replay, 24-hour
  soak, multi-replica test, deployment, live-provider call, or recruited-human
  session was run.

## Remaining launch blockers

- Reproduce and resolve the broad-suite-only four-process initialization
  timeout rather than increasing its timeout without evidence.
- Integrate and independently verify the unavailable V6 admission and transport
  commits, or reimplement them with active safety tests.
- Resolve loaded error latency and the unexplained two-transport failure.
- Rotate every exposed historical credential and review provider/GitHub audit
  logs before authenticated continuation.
- Disable or harden unauthenticated LAN sync, fail-open RBAC/OIDC, insecure
  memory export, privileged unverified installers, and the PyMuPDF licensing
  contradiction in the wider product.
- Prove clean-host installation, storage encryption/key custody, person-level
  IAM, retention/erasure, TLS and telemetry backends, backup/restore, rollback,
  platform support, and a monitored soak.
- Complete consented human evaluation and commercial validation. Synthetic
  personas are not recruited people.

## Release decision

**NO-GO for merge to `main`, GA, sensitive paid intake, live-provider
enablement, or production deployment.** A draft review PR is appropriate only
after this branch is published through a secure, rotated GitHub credential and
remote CI is available. Do not bypass required checks or rewrite history.