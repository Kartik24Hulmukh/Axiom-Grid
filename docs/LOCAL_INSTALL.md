# Reviewed local developer setup

The root installers are not a distribution/authenticity authority. Do not pipe downloaded source into a shell or bypass PowerShell execution policy. Review a local checkout at an independently chosen revision before running code. These scripts do not clone, download/execute Rust or Ollama installers, pull models, probe services, launch applications, change PATH/startup entries, or rewrite home/app configuration.

Only the Linux unprivileged developer path is enabled. Windows, macOS and unknown systems fail closed because this checkpoint does not establish their installation behavior. `install.ps1` always exits nonzero without installing anything. Previous ghost-typing and “ready in any app” promises do not apply to Axiom-Grid's READ + SUGGEST preview.

## Trust and prerequisites

- Python 3.11+ and its `venv`/`ensurepip` tooling must already be present. `--rust-local` additionally requires an existing working Cargo/toolchain and all locked dependencies cached locally.
- Explicitly acknowledge both reviewed source and reviewed prerequisites. The flags record your local trust decision, **not** signature verification. No signing keys/authorities are invented by the installer.
- For Python setup, prepare a complete, compatible reviewed local binary-wheel directory (one selected version per package) including sidecar requirements, test requirements and pytest tooling. There is no network resolution or source-package build fallback; missing wheels fail. The requirements are not a fully hash-pinned release lock. This script does not establish wheel/toolchain authenticity.
- Source/wheel paths and existing components must not be symlinks. Source/wheel trees must be user-owned and not group/world writable, with regular files/directories only. Source inputs remain executable trusted code. Keep the checkout, prerequisite tools/caches, wheelhouse and destination parent private and stable throughout installation. Checks are not a race-proof sandbox against another process running as the same user or root.
- Destination must be a new directory outside the checkout/wheelhouse, under an existing user-owned, non-group/world-writable parent. Reuse/overwrite (including existing `.venv`) is refused. Failed setups retain their private partial output for diagnosis; select a new destination for retries. Nothing is installed into global Python or a home config path.

## Local Python dependency workflow

From the reviewed checkout, with an already provisioned wheelhouse and private destination parent:

```bash
bash install.sh --reviewed-checkout --reviewed-prerequisites \
  --wheelhouse /absolute/private/reviewed-wheels \
  --destination /absolute/private/new-axiom-venv
```

This preserves the previous local sidecar/test dependency preparation and the required kernel/packs/bench imports plus corpus integrity smoke gate. pip uses `--no-index`, binary wheels only and `--no-deps`, with external pip configuration disabled. All wheels in the explicitly reviewed directory are installed as local files, then `pip check` must pass; dependency metadata does not trigger remote URL resolution. No pip self-upgrade or automatic network prerequisite installation occurs. Missing tooling/dependencies and smoke/test failures are fatal. The prepared Python environment is not a running overlay, signed application, full regression-suite result, or OS support attestation. Review the existing README for the separate overlay runtime lane (`docker/requirements-runtime.txt`).

## Local Rust developer installation

```bash
python3 -I install.py --rust-local --reviewed-checkout --reviewed-prerequisites \
  --destination /absolute/private/new-axiom-rust
```

This retains the existing `phantom-core` local Cargo installation workflow, using `--offline --locked`, selecting only `kairo-phantom` (not the debug binary) and placing outputs/target state in the new destination. A successful Cargo exit and binary existence are required. The binary is not executed and no config is generated. Offline Cargo resolution does not sandbox build scripts or prove zero egress of arbitrary reviewed source/dependencies. Native desktop prerequisites, UI permissions, separate MCP builds, model provisioning, actual launch and read-back remain unverified/manual gates; no automatic support or successful launch is promised.

## Evidence limits

The installer regression tests replace subprocess command boundaries and use inert fixtures. They are hermetic unit checks, **not actual clean-host OS installation tests**, signed-artifact verification or platform support evidence. Bash syntax is checked separately. PowerShell is inspected as source only when no PowerShell runtime is available. Historical corpus/CI/platform statements elsewhere are not new installer attestations.
