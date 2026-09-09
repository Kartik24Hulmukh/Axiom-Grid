# Handoff 001 — fork boundary

## Completed chunk

- Source imported from Kairo-Phantom commit `8975743` with history and MIT license preserved.
- Local origin changed to Axiom-Grid **before any write/push**. Source repository untouched.
- Axiom branch: `main`.
- Archived 18 inherited workflows and prior README/packaging/quickstart/release documents under `docs/inherited/`.
- Replaced root positioning with an honest engineering-preview scope; excluded build outputs from Git.

## Why not mass-delete source immediately?

The inherited core has extensive cross-module dependencies. Blind deletion would break the overlay and retained Ghost implementation. The next chunk isolates a buildable launch slice first; only then remove legacy modules with import/dependency checks. Archived workflows do not execute.

## Next chunk

See `HANDOFF-002.md`: independent local-only runtime, IPC boundary, preview UX, session/Unicode fixes and regression evidence. Legacy source is not approved for release.
