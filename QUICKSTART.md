# Axiom-Grid engineering preview

**Explicit input → local model → review/discard. No automatic insertion.**

## Requirements

- Rust 1.98.1, Python 3.10+, and platform Tauri 2 build prerequisites.
- Ollama running on `127.0.0.1:11434`; an exact model tag already installed.
- Linux: `libwebkit2gtk-4.1-dev libayatana-appindicator3-dev librsvg2-dev patchelf`.
- Node 22+ only for frontend tests or the optional Tauri CLI development workflow.

The extracted desktop and runtime have independent Cargo workspaces and lockfiles. They do not compile the inherited core, MCP servers, swarm or plugins.

## Build and launch

From the repository root:

```sh
cargo build --manifest-path axiom-runtime/Cargo.toml --locked
cargo build --manifest-path phantom-overlay/src-tauri/Cargo.toml --locked
python3 scripts/axiom-launch.py --model YOUR-EXACT-INSTALLED-TAG
```

Use `ollama list` to find the tag. Axiom never installs or downloads a model. Model provisioning is your separate, explicit operation with Ollama; review the model license and download size first.

The launcher creates a fresh random IPC token, passes it only in the two child process environments, waits for authenticated readiness, and stops its owned runtime when the desktop closes. It refuses an occupied port and does not attach to or kill other services. It bypasses HTTP proxies and rejects redirects. The token is never printed, saved or sent to JavaScript. **This is not OS-keychain pairing:** same-user privileged processes and environment inspection remain threats. Never use GitHub credentials as IPC tokens.

`--runtime` and `--desktop` allow trusted release-binary paths. Do not point them at untrusted executables. No signed release installers are available yet.

## Use

1. Choose **Check local models**. The configured exact tag, installed inventory and disk sizes are displayed. “Installed” is not an inference/quality or memory-readiness guarantee.
2. Paste an instruction and only the selected text you want the model to read.
3. Choose **Generate preview**. Read the result and check facts and exact meaning.
4. Select the result and copy manually using Ctrl+C / ⌘C; or choose **Discard**.
5. Close the window to stop both launcher-owned processes.

Discard rejects late results but does not cancel computation already inside Ollama. Ctrl+Space only shows the window; a hotkey conflict no longer prevents normal startup. No focus switching to other apps, ambient capture or automatic typing occurs.

Linux native window, authenticated readiness, real-model generation, discard and owned-process shutdown were exercised in this run. Windows/macOS runtime behavior and packaging remain unverified; compilation CI has been added for all three platforms.

## API-only mode

```sh
export AXIOM_API_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
export AXIOM_MODEL='YOUR-EXACT-INSTALLED-TAG'
cargo run --manifest-path axiom-runtime/Cargo.toml --locked
```

Use the same shell credential from another trusted native client:

```sh
curl --noproxy '*' http://127.0.0.1:7437/readiness -H "Authorization: Bearer $AXIOM_API_TOKEN"
curl --noproxy '*' http://127.0.0.1:7437/materialize -H "Authorization: Bearer $AXIOM_API_TOKEN" -H 'Content-Type: application/json' --data '{"context":"Rewrite clearly: We are doing the work now."}'
```

`/health` is unauthenticated process liveness only. `/readiness` is authenticated and checks the exact configured tag via a bounded, three-second inventory request. It does not load, download or benchmark a model. `/materialize` limits input to 16,000 Unicode scalars / 64 KiB JSON, model output to 256 KiB, and allows one generation with a 90-second timeout. UI maxlength is conservatively measured in UTF-16 units. Native bridge responses are bounded to 512 KiB to accommodate escaped JSON.

## Validation

```sh
cargo fmt --manifest-path axiom-runtime/Cargo.toml --check
cargo test --manifest-path axiom-runtime/Cargo.toml --locked
cargo clippy --manifest-path axiom-runtime/Cargo.toml --locked --all-targets -- -D warnings
cargo fmt --manifest-path phantom-overlay/src-tauri/Cargo.toml --check
cargo test --manifest-path phantom-overlay/src-tauri/Cargo.toml --locked
cargo clippy --manifest-path phantom-overlay/src-tauri/Cargo.toml --locked --all-targets -- -D warnings
node --test phantom-overlay/tests/app.test.cjs
python3 tests/test_axiom_launcher.py
```

Explicit real-model smoke (stop other runtimes first; uses synthetic fixture text only):

```sh
python3 scripts/axiom-real-model-smoke.py --runtime axiom-runtime/target/debug/axiom-grid --model YOUR-EXACT-INSTALLED-TAG --output real-model-results.json
```

The tested `qwen2.5:0.5b` completed inference but failed exact Unicode and semantic-preservation checks; **it is not approved as a default product model**. See `docs/axiom/evidence/real-model-smoke.json`. Timings are shared-container observations, not promised latency.

## Privacy boundary

Requests use fixed loopback endpoints with no redirects, proxies or cloud fallback. No supplied text is persisted by the focused runtime. Ollama’s own logging/storage is separate. This is not an OS network sandbox, enterprise compliance certification or proof of zero egress. See [launch gates](docs/axiom/LAUNCH-GATES.md).
