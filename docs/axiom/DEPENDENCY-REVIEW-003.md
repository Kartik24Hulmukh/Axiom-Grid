# Focused dependency review — chunk 003

cargo-audit 0.22.2 was run against both independent lockfiles. Raw timestamped database metadata and findings are in `evidence/runtime-audit.json` and `evidence/desktop-audit.json`.

- Runtime: zero entries in vulnerability list; **one unmaintained warning**, `smallstr 0.3.1` (RUSTSEC-2026-0215), through inherited CRDT regression dependency `yrs`.
- Desktop: zero entries in vulnerability list; **six unmaintained warnings and one unsound warning**. `glib 0.18.5` RUSTSEC-2024-0429 affects `VariantStrIter` iterator implementations; Tauri's Linux GTK dependency requires upstream compatibility review. Unmaintained packages are `proc-macro-error` and five `unic-*` crates.
- No advisories were suppressed and no forced incompatible dependency override was applied. A zero vulnerability-list count is **not a clean security bill**, particularly with an unsoundness advisory.
- `npm install --package-lock-only --ignore-scripts` reported zero npm vulnerabilities after removing the unused shell plugin. This is not a complete supply-chain audit.

Before production: trace each warning's exact reachable path, remove runtime CRDT dependencies if unnecessary, upgrade compatible Tauri/GTK stack when fixed, document residual risk with an owner and expiry, generate per-artifact SBOMs, and audit OS libraries and signed binaries. Inherited root workspace was not audited by these focused checks. No signed artifact exists yet.
