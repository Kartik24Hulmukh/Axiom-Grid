# Axiom-Grid engineering preview

## Requirements

- Rust 1.98.1 (pinned in `axiom-runtime/rust-toolchain.toml`).
- Ollama installed and running on **127.0.0.1:11434** with a model already installed. Pick a model appropriate for your measured hardware; no download occurs automatically.
- Optional desktop overlay: Node 22+, platform-specific Tauri 2 prerequisites. The native overlay has not been built or validated in this environment.

## Run the focused runtime (POSIX shell)

From the repository root:

```sh
export AXIOM_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export AXIOM_MODEL='YOUR-EXACT-INSTALLED-MODEL-TAG'
export AXIOM_MODEL_DIGEST='YOUR-INDEPENDENTLY-APPROVED-64-HEX-DIGEST'
cd axiom-runtime
cargo run --locked
```

`AXIOM_MODEL` is an exact 1–256 byte ASCII graphic name (no whitespace or implicit aliases). `AXIOM_MODEL_DIGEST` is mandatory: a bare 64-hex digest or `sha256:` plus 64 hex digits, normalized to lowercase. Obtain the expected identity through your approved artifact/backend qualification process; do not automatically trust the first inventory response. The placeholders above are intentionally not runnable model settings. See [model identity policy](docs/MODEL_IDENTITY_POLICY.md). Never paste your GitHub token into `AXIOM_API_TOKEN`: it is a separate random local IPC secret. Missing/invalid settings fail startup. Keep the token out of screenshots, logs and committed files. Provision a fresh token each launch.

The service binds only to `127.0.0.1:7437`. `/health` is process liveness. Authenticated `GET /readiness` queries the inventory and requires exactly one configured-name entry, positive size, and a valid digest matching the expected identity. It reports `expected_digest` and `identity_check_scope="reported-only"`. Every generation independently fetches fresh inventory before sending context and requires the response to report the exact configured model name. A policy mismatch gives readiness `200/ready=false` and generation `503`; malformed inventory or a missing/conflicting output model gives `502`. Nothing is downloaded automatically. Matching reports are not backend authentication or verification of model weights.

## Use the API

From another terminal with the same **local IPC token**:

```sh
curl --noproxy '*' http://127.0.0.1:7437/materialize   -H "Authorization: Bearer $AXIOM_API_TOKEN"   -H 'Content-Type: application/json'   --data '{"context":"Rewrite this sentence clearly: We are doing the work now."}'
```

Returns `suggestion`, Unicode scalar `char_count` and `word_count`. Review before copying. Input is limited to 16,000 Unicode characters / 64 KiB JSON; output to 256 KiB; one generation at a time; inference has a 90-second timeout. No text is saved by the focused runtime. Ollama's own storage/logging policy is outside this application's guarantee.

## Desktop overlay (unverified native build)

Start the core above, then from a terminal that has the **same** IPC token:

```sh
cd phantom-overlay
npm ci
RUSTUP_TOOLCHAIN=1.98.1 npm run dev
```

The overlay checks the authenticated readiness endpoint on startup, shows the exact configured model, and fails closed until the expected reported identity matches. Older name-only runtime responses are rejected as an incompatible protocol. Use **Retry check** after an explicit `ollama pull`. Paste the instruction and selected text, choose **Generate preview**, review, and manually copy. **Discard** hides the preview and rejects late results; it does not terminate inference already executing inside Ollama. No automatic insertion or ambient application capture is enabled. The native Ctrl+Space shortcut currently only shows the window; it does not invoke generation.

The Tauri project still lives inside the inherited workspace and requires separate platform build validation before distribution. Bundling remains disabled. Do not ship unsigned inherited artifacts.

## Verify

```sh
cd axiom-runtime
cargo fmt --check
cargo test --locked
cargo clippy --locked --all-targets -- -D warnings
```

From the repository root: `node --test phantom-overlay/tests/app.test.cjs`.

## Privacy boundary

The focused runtime sends supplied text only to the fixed loopback model endpoint, bypasses environment proxies and refuses redirects. This is not an OS-enforced network sandbox or enterprise zero-egress attestation. A compromised local process or model daemon remains in the threat model. The runtime supports per-user protected pairing; the environment token shown above is an explicit development override, not an enterprise credential-management recommendation. The `KAIRO_OFFLINE` environment flag does not enforce offline execution in this focused runtime; use independently configured and observed OS/network controls for that requirement.
