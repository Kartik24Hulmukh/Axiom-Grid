# Native bridge recovery diagnostics

Scope: the existing foreground, explicit-input/manual-copy preview. This changes
recovery messages, not runtime permissions, authentication, model selection or
production qualification. No new dependency or automatic repair is introduced.

## Pairing recovery

| Code | Meaning and operator action |
|---|---|
| `PAIRING_OVERRIDE_INVALID` | An explicit token override is empty, malformed or non-Unicode. Correct or deliberately remove it. No file fallback occurs. Never paste tokens into issue reports. |
| `PAIRING_MISSING` | Protected pairing storage was not found. Start the runtime under the same authorized user and supported configuration. |
| `PAIRING_STORAGE_INVALID` | Storage contents, ownership or permissions are unsafe. Stop and inspect with the authorized administrator; do not silently chmod, regenerate or bypass checks. |
| `PAIRING_PERMISSION_DENIED` | Access was denied. Resolve the authorized user's access; do not run the preview with elevated privileges merely to bypass this check. |
| `PAIRING_IO_FAILURE` | Other storage failure. Inspect storage locally without publishing paths or credentials. |
| `PAIRING_USER_DIRECTORY_MISSING` | Configure a supported user directory. |
| `PAIRING_STORAGE_UNSUPPORTED` | Protected file pairing is unsupported on this platform. An explicitly provisioned valid override is supported, but does not qualify platform credential storage. |

Recovery must not delete or rewrite an existing pairing file automatically.
Missing storage is distinguished from invalid storage. The client does not expose
resolved paths, filesystem exception text, token values or nested source errors.
Shared pairing validation remains unchanged; the bridge additionally rejects a
non-Unicode override before the shared loader can fall back to storage.

## HTTP and transport diagnostics

Non-2xx responses, including redirects, are rejected before JSON decoding. Their
bodies are not read into diagnostic errors. Redirect following and proxy discovery
remain disabled. Messages include the operation and numeric status, then a fixed
code and explanation.

| Status / failure | Code |
|---|---|
| 401 | `PAIRING_AUTH_FAILED` |
| 403 | `POLICY_DENIED` |
| Preview 400 / 413 | `PREVIEW_INPUT_REJECTED` |
| 429 | `RUNTIME_BUSY` |
| 499 | `CANCEL_REQUESTED` |
| 502 | `BACKEND_RESPONSE_INVALID` |
| 503 readiness / preview / cancel | `READINESS_UNAVAILABLE` / `PREVIEW_UNAVAILABLE` / `CANCEL_UNAVAILABLE` |
| Other 5xx | `RUNTIME_SERVER_ERROR` |
| Other non-2xx, including 3xx | `HTTP_UNEXPECTED_STATUS` |
| Client initialization | `HTTP_CLIENT_SETUP_FAILED` |
| Timeout / connection failure / other transport | `TRANSPORT_TIMEOUT` / `TRANSPORT_CONNECTION_FAILED` / `TRANSPORT_FAILED` |
| Malformed success JSON or unexpected success schema | `RESPONSE_DECODE_FAILED` |

Preview 503 cannot distinguish service unavailability from an expected-model
identity rejection using the current status-only protocol. Its explanation states
that ambiguity; it does not claim to diagnose weights or backend authenticity.
A response-body read failure may be classified as transport rather than decoding.
The client does not preserve raw reqwest/serde errors in the returned error chain.

Cancellation remains best effort: the public generation call returns its existing
user-cancellation message and deliberately discards cancellation-ack errors.
Thus the internal cancel diagnostic mapping is **not** a newly exposed UI channel.
Neither a 499, an acknowledgement, nor dropping a connection proves backend compute
termination, server slot release or erasure. Existing lease ownership is retained.

## Validation and limits

`axiom-runtime/tests/native_bridge_recovery.rs` includes the actual production
bridge and shared pairing module. Synthetic loopback contracts cover status
mapping, success-shaped error bodies, malformed success schemas, sanitized
Display/Debug/source chains, connection failure, readiness timeout, invalid
Unicode/non-Unicode override admission, file fallback refusal, unsafe/malformed/
missing storage and subsequent successful calls. Unix storage cases use temporary
fixtures, not real user credentials. Existing eight lifecycle tests remain intact.

Run with the locked runtime profile:

```sh
cargo test --manifest-path axiom-runtime/Cargo.toml --locked --test native_bridge_recovery
```

Tests and formatting/Clippy/build outcomes must be associated with the exact
published head before merge. Source inspection is not compilation. Mocks do not
establish native Windows/macOS storage, desktop UI, real-model behavior, offline
execution, memory erasure or production readiness. Permission-denied and generic
storage-I/O branches are not exhaustively exercised by the portable contracts.
No message claims universal secret redaction: the guarantee is that these new
bridge diagnostics carry only fixed text and HTTP status, not raw failure objects.

See [ownership](NATIVE_BRIDGE_LIFECYCLE.md),
[device qualification](DEVICE_QUALIFICATION.md), and
[release qualification](RELEASE_QUALIFICATION.md).
