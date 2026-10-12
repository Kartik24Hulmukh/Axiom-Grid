# Axiom-Grid V8.2 root installer review

Base: 27e9f8e0854b9d8b00ac64162d686d2fb7b791d5. Assigned worktree was absent; independent local `--no-hardlinks` clone created at `/data/axiom-v82-installers`. Shared checkout untouched.

## Before-edit audit and budgets

Source history counts: install.sh 4, install.ps1 3, install.py 2, tests/test_packaging.py 1, docs/inherited/PACKAGING.md 1. Maximum 5 revisions/module: install.sh has only one remaining edit revision. New direct guide/tests start at zero. Maximum two implementation+narrow-check cycles; no inherited wider budget reset. Initial baseline: 18 packaging tests passed, log `/data/axiom-v82-installer-baseline.log` retained.

- Bash: promoted mutable curl-pipe execution; CWD-based root selection/auto mutable clone; lexical Python version comparison; existing `.venv`/activation symlink risk; unrestricted pip downloads/upgrades; false Linux/platform install success and desktop claims.
- PowerShell: unverified rustup exe downloaded/executed in shared temp; undefined ScriptDir used before resolution; mutable clone; no reliable native exit checks; Ollama live endpoint/model downloads and machine-level environment writes; user/global Python pollution; forced binary/plugin/MCP config overwrites; false launch claims. No source symlinks found at base.
- Python: shell=True with CWD-dependent cargo install; check=False accepts missing cargo as success; live Ollama endpoint; unchecked home/config symlink traversal and overwrite-by-race; unsupported skip-build success and desktop launch promise.
- No signature authority or release authenticity evidence available. Existing Linux test results do not attest clean-host installers. Windows/macOS automated installation must fail closed; local Linux workflows may remain explicitly acknowledged developer operations, not signed release installation.

## Implementation plan (cycle 1)

Local reviewed-checkout/prerequisites acknowledgement; Linux-only developer paths; offline binary-wheel Python environment preserving imports/corpus smoke gate, or offline locked single-binary Cargo install to a fresh explicit destination. No auto clone, bootstrap download, model pull, runtime launch, shell subprocess, home/config/PATH mutations. Reject root, source/path symlinks, unsafe ownership/write access, reused destinations and remote requirement directives. Keep prerequisite failure fatal. Stub command-boundary tests are hermetic unit checks, never clean-host/platform attestation. Bash syntax only, PowerShell source checks only (pwsh unavailable).

## Cycle 1 result (retained failure)

Bash syntax PASS. Narrow tests: **48 passed / 1 failed**, exit 1. Failure is the new test harness reading captured output twice in an `or` assertion (second read is empty), not an installer command. Full diagnostic preserved in `/data/axiom-v82-installer-cycle1.log`. No installer entrypoints/toolchain/pip commands actually executed. PowerShell runtime unavailable. Existing packaging checks retained and strengthened: imports/corpus gate inspected in shared engine; Linux assertion now requires explicit non-attestation rather than historical positive CI language.

Checkpoint cycle 1 before correction; install.sh reaches revision count 5 and must not be edited again. Cycle 2 will correct the harness and enforce `--no-deps` with explicitly enumerated reviewed wheels plus `pip check` so wheel dependency metadata cannot introduce remote URLs through pip dependency resolution.

Cycle-1 commit initially failed because the independent clone had no Git author identity. Failure retained; retry uses an explicitly labelled automation identity scoped to this clone only, not the user's identity or global configuration.

## Cycle 2 and final checkpoint

- Corrected the capture assertion without relaxing the claim being checked.
- Closed pip wheel-metadata URL resolution: `--no-deps`, explicit reviewed local wheel files, and fatal `pip check` before import/corpus smoke gates. Complete compatible wheels are prerequisites; no online fallback.
- Added Cargo version/install exit propagation, Python import-environment sanitization and unsafe destination-parent checks.
- Narrow cycle 2: **54 passed / 0 failed**, exit 0, `/data/axiom-v82-installer-cycle2.log`. Bash syntax, Python AST syntax and `git diff --check`: PASS. These are mocked command-boundary/source checks, not installer execution or clean-host attestation. Previous 48/1 failure and initial author-identity commit failure are retained above and in the cycle-1 log.
- Two implementation+narrow cycles consumed: STOP/checkpoint. No full suites, benchmarks, installer processes, Cargo/pip installs, endpoints, Rust/Ollama downloads, privilege escalation, PR/push/merge or shared checkout writes.

## Remaining blockers / non-claims

1. No signed installer verification or agreed signing authority, trusted published artifact/checksum channel, complete hash-pinned Python release lock, or independently authenticated wheel/toolchain/cache provenance. User review flags are acknowledgement, not cryptographic verification.
2. No actual clean Linux/macOS/Windows installation/run evidence. Windows/macOS root automated paths are intentionally blocked; PowerShell runtime unavailable (source-only inspection).
3. Linux offline developer provisioning can fail for absent/incompatible wheels, caches, native libraries or tooling; this is correct fail-closed behavior, not a promised launch. Full sidecar/test requirements are inherited broad manifests; runtime overlay is a separate requirements lane.
4. No desktop support, GUI launch/read-back, model provisioning, MCP integration, full regression or production readiness proven. Rust outputs are local developer binaries only, not executed.
5. Path checks assume a stable private user-controlled checkout/wheelhouse/destination parent. Same-user/root mutation races and arbitrary build-script network behavior are not sandboxed; no OS-level zero-egress guarantee is claimed.

Atomic commits: cycle 1 `000f26d`; cycle 2 to be recorded after commit below. install.sh was not changed in cycle 2, preserving its max-five history budget.

Final cycle-2 commit: `4b6efdd8c0f8c7baf13fb51c57d7a7b05aedd922` (cycle 1: `000f26d`). Isolated branch `harden/axiom-v82-installers`, working tree clean. Final revision counts: install.sh **5/5**; install.ps1 **4/5**; install.py **4/5**; tests/test_packaging.py **2/5**; tests/test_root_install_boundaries.py **2/5**; docs/inherited/PACKAGING.md **2/5**; docs/LOCAL_INSTALL.md **2/5**. Shared checkout HEAD remained `27e9f8e0854b9d8b00ac64162d686d2fb7b791d5`. No further edits/tests are authorized within this two-cycle slice; residual release/platform gates remain blocked, not waived.
