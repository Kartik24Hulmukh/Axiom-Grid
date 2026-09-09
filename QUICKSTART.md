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
export KAIRO_OFFLINE=1
cd axiom-runtime
cargo run --locked
```

`AXIOM_MODEL` must match an entry in `ollama list`. Never paste your GitHub token into `AXIOM_API_TOKEN`: it is a separate random local IPC secret. Missing/invalid settings fail startup. Keep the token out of screenshots, logs and committed files. Provision a fresh token each launch.

The service binds only to `127.0.0.1:7437`. `/health` is process liveness. Authenticated `GET /readiness` queries Ollama’s local inventory and reports whether the exact configured tag is installed, plus local model names, sizes and digests. It never downloads a model. If a model is absent, generation returns an actionable error rather than downloading it or calling a cloud provider.

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

The overlay checks the authenticated readiness endpoint on startup, shows the exact configured model, and fails closed until that tag is installed. Use **Retry check** after an explicit `ollama pull`. Paste the instruction and selected text, choose **Generate preview**, review, and manually copy. **Discard** hides the preview and rejects late results; it does not terminate inference already executing inside Ollama. No automatic insertion or ambient application capture is enabled. The native Ctrl+Space shortcut currently only shows the window; it does not invoke generation.

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

The focused runtime sends supplied text only to the fixed loopback model endpoint, bypasses environment proxies and refuses redirects. This is not an OS-enforced network sandbox or enterprise zero-egress attestation. A compromised local process or model daemon remains in the threat model. Native IPC credentials supplied through environment variables need replacement with OS-protected pairing before enterprise deployment.
