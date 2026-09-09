# Launch decision — NO-GO for a production ghost-typing release

Target dates from the requested September 9, 2026 planning context: Wednesday September 16 or Thursday September 17. Dates are a planning target, not a reason to waive safety gates.

| Gate | Current evidence | Required before claiming production |
|---|---|---|
| Focused runtime compiles and passes tests | Local pass: 17 Rust tests, Clippy, debug build | Clean-machine CI and platform matrix |
| Preview UI logic | 5 Node tests pass | Native Tauri build and real keyboard/manual-copy UX |
| Real local model | Mock loopback integration only | Installed-model end-to-end run on minimum hardware, p50/p95 latency and RAM measurements |
| Safe insertion | Intentionally disabled | Target handle + element identity + selection revision, explicit approval, pre-insertion revalidation, abort on focus change, native undo validation |
| Model onboarding | Explicit configured model, no silent pull | Inventory UI, errors/progress, approved download and license/disk checks |
| Privacy | Fixed loopback client, no proxy/redirect/fallback | OS/network observation on clean machine, audit all model/runtime egress; no cryptographic zero-egress claim |
| Authentication | Manual local random token | OS-protected per-user pairing and lifecycle/rotation |
| Distribution | Bundling disabled | Signed/notarized installer, checksum/SBOM, upgrade/uninstall/rollback tests |
| Extraction | Independent runtime excludes legacy launch surface | Remove unused source and simplify Tauri workspace after native build validates dependencies |
| Market | Hypothesis only | 5–10 target users, observed repeat use, measured time saved and willingness-to-pay interviews |

Launch a limited, clearly labeled design-partner preview only after real-model + native-UI gates pass. Do not promise Word/PPT/Canva/Figma automation until per-app tests demonstrate it. Prefer one OS and two ordinary text editors for the first insertion release. Do not position the product for covert exam assistance.


## Chunk 003 update — September 9, 2026

- PASS: extracted native workspace builds on Linux without inherited core dependencies; native unit test and warnings-denied Clippy pass.
- PASS: authenticated model inventory, exact tag matching, missing/error states and response bounds covered by tests.
- PASS: real Linux native desktop → bridge → runtime → Ollama → displayed preview; review/discard and owned-process shutdown exercised.
- PASS (limited): real `qwen2.5:0.5b` API smoke completed three fixtures. This validates connectivity, not usefulness.
- FAIL: exact Unicode fixture and semantic fidelity on the tested 0.5B model. Do not ship this model as default. Validate a stronger model and representative held-out editing dataset.
- PARTIAL: launcher provisions fresh non-persistent credentials and cleans up owned children. OS-protected pairing is still missing.
- PENDING: Windows/macOS native behavior, signed/notarized packaging, updates/rollback, clean-machine installs, OS-level privacy tests, dependency-advisory triage and safe target-bound insertion.

**Production ghost-typing release remains NO-GO.** A supervised technical preview is useful for design-partner evaluation, with manual copy only and conspicuous quality warnings. No evidence supports “100x traction” or universal app compatibility.
