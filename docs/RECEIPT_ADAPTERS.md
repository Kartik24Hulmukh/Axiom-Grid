# Agent receipt export adapters

Working scope: **offline JSON export → signed observations → offline verification**. No live upstream service or LLM call is needed. No upstream framework is vendored.

## Reproduce the supplied synthetic sample

```sh
python scripts/axiom_receipts.py verify examples/receipts/sample.json \
  --public-key examples/receipts/sample-public.pem \
  --checkpoint examples/receipts/sample-checkpoint.json
```

The public key is a test fixture, not a trusted production identity. Its corresponding ephemeral private key was discarded. Modify an action or remove an entry: verification must fail.

## Export an actual upstream capture

```sh
# Owner-provisioned Ed25519 private key; never commit it.
chmod 600 /secure/receipt-private.pem
python scripts/axiom_receipts.py export capture.json --source openbot \
  --private-key /secure/receipt-private.pem --output receipts.json
python scripts/axiom_receipts.py verify receipts.json \
  --public-key /independently-pinned/receipt-public.pem
```

`capture.json` must be a JSON array. Output creation is exclusive; existing evidence is never overwritten. Export source choices: `openbot`, `opik`, `helicone`. A signing key is not an API credential and must be separately provisioned/rotated.

## Compatibility and gaps

- **OpenBot:** inspected `CopilotKit/OpenBot` HEAD `afe623366945d6378dde5ea9c46322ac856c3047`, MIT license, `server/src/audit.ts`, exported `AuditEvent` fields. Require `id`, `eventType`, `targetType`, `createdAt`, object `payload`. Commit to the complete supplied event, derive `refused`/`failed` only from event-name suffixes; otherwise say `observed`. Do not confuse an export adapter with a live every-action instrumentation hook. A real OpenBot deployment, authenticated paginated capture, and upstream PR remain unverified.
- **Opik/Helicone:** caller-supplied trace objects with a string `id`; hash the exact object, outcome `observed`. These are generic JSON-export adapters, not validated SDK integrations or claims of compatibility with every provider version. Live exporter integration remains pending.
- **Playwright:** actual browser E2E with pinned dev dependency in `tests/browser`; rapid-click, abandon, source, correction, and injection oracles. Not real recruited humans or a desktop OS UI certification.
- **Existing OpenTelemetry:** retained opt-in spans, W3C propagation, request IDs, structured logs and probes. No production collector receipt was captured here.
- **gitleaks/k6/artillery patterns:** fail-closed secret handling and explicit expected-status/latency gates in the existing and new local harnesses. No new runtime framework dependency.

## Browser regression command

```sh
npm --prefix tests/browser ci
npx --prefix tests/browser playwright install chromium
PYTHON=python3 npm --prefix tests/browser test
```

Six browser tests include one **isolated intercepted-response XSS oracle**. The other tests use the actual local API. Browser binaries are test-only, not runtime dependencies. Headless environment requirements must be installed on CI.

## Why no giant framework integration

The catalog contains unrelated trading, offensive research, voice, video and platform repositories. Those do not resolve the current receipt, latency, secret-management and desktop execution blockers. No `curl | bash` installer or unreviewed plugin was executed. Integrate live exporters only after a captured real upstream event and an external verifier reproduce the format.

## Preview worker and state bounds

`/demo` and extraction use bounded document-worker admission; source lookup and
review CAS use a separate bounded evidence-I/O lane. Cancellation never releases
a running native worker's permit early. Byte-bounded binary previews do not fall
back to another document's chunks.

Authenticated source/trace/review state now uses credential-scoped SQLite WAL:
default 128 completed graphs, one-hour API expiry, 16 MiB per graph and 64 MiB of
graph payload per credential. Reviews are separate from immutable source and
bounded to 8 MiB logical UTF-8 content per credential; graph retirement cascades
associated review rows. This is shared-local-volume state, not IAM, multi-host HA
or an append-only audit archive. Owned upload copies are separately quota/expiry
bounded and not encrypted at rest. API expiry is not proof of physical erasure
from copies, WAL, filesystem or backups; operators need a deletion/retention plan.

Signed receipt exports and independently retained checkpoints are a separate
explicit workflow, not automatic overlay capture. Short fd/RSS samples are not a
long-soak leak certification. See the current council checkpoint and scoped
evidence guide for exact limits and remaining gates.
