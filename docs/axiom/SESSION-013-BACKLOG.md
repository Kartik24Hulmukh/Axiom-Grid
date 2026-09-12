# Session 013 — remaining backlog and acceptance criteria

Sources reviewed in full: both task attachments; HANDOFF-001 through HANDOFF-004;
SESSION-012-REAL-MODEL; LAUNCH-GATES. The main-branch session-012 “no code backlog”
claim is contradicted by those sources and by reproduced defects. This list
supersedes that conclusion, not the historical evidence.

| Priority | Work package | Session 013 disposition | Required closure evidence |
|---|---|---|---|
| P0 | Focused compile/test gates | Runtime and Linux overlay validation; see session report | Exact final commit green CI and qualified native platform matrix |
| P0 | Unix pairing | Implemented no-follow descriptor traversal, owner/mode/link/type/length checks, bounded locking, atomic publish, explicit recovery | Adversarial OS review, filesystem/platform matrix, crash/load/property coverage |
| P0 | Windows pairing | Remains unsupported, explicitly fail-closed | Windows CSPRNG + per-user ACL/keychain, native lifecycle tests |
| P0 | Credential lifecycle | Stop-all/rotate/restart runbook; no silent repair of disclosed credentials | Coordinated live rotation/revocation UX and native tests |
| P0 | Cancellation | Existing API/UI retained and tested | Bridge request-order races, stale cancellation, daemon disconnect behavior under load |
| P0 | Installed-model validation | Re-executed with real explicitly installed small CPU fixture | Launch model/OS choice, minimum hardware, peak RAM, first-token metrics, human usefulness ratings |
| P0 | Native preview | Linux build/smoke tracked separately | Unicode manual copy, focus/hotkey/clipboard matrix, clean-machine startup/shutdown, GTK diagnostic investigation |
| P0 | Model onboarding | Inventory/readiness only | Explicit selection, approved download and progress, license/disk/offline policy and tests |
| P0 | Safe insertion | Disabled; not implemented or claimed | Choose OS and two editors; bind process/window/element/revision and approval hash/session/expiry; replay defense, immediate revalidation; undo and clipboard restoration; races, permissions, Unicode/graphemes, process exit and human edits |
| P1 | Resilience | Five-second shutdown drain added; actual SIGTERM/stalled-body tests | Fuzz/property, chunk/timeout/load coverage and adversarial bridge races |
| P1 | GhostSession encapsulation | Open | Make mutable state private; guarded transitions; migrate all callers and tests |
| P1 | Workspace extraction | Open | Import/dependency analysis, isolate Tauri, retire unused legacy surfaces/claims without breaking retained behavior |
| P1 | Security/privacy | Pairing threat boundary documented, local log scan | Local adversary, model compromise, prompt injection, persistent logs, observed egress, dependency audit and SBOM |
| Release | Distribution | Not release-ready | Signed/notarized packages, checksums, upgrade/rollback/uninstall and clean-machine evidence |
| Market | Partner validation | External gate remains open | 5–10 target users, repeated use, measured time saved, willingness-to-pay interviews |

## Execution order

1. Land reviewed security/shutdown fixes only after focused CI. Preserve the earlier
   real-model-hardening fixes; do not reset main or overwrite the independent docs.
2. Choose launch OS/minimum hardware and model. Complete Unix security review or
   implement Windows protected storage before selecting Windows.
3. Finish model onboarding and native manual-copy preview qualification.
4. Build safe insertion as a separately reviewed end-to-end transaction; keep it
   disabled until the real two-editor acceptance matrix passes.
5. Encapsulate/extract legacy code, expand resilience and audit dependency/egress.
6. Qualify signed distribution and partner usefulness before production claims.

Focused tests do not certify inherited workspace suites or universal zero
regressions. This sandbox cannot supply signing identities, partner interviews,
or genuine minimum-hardware/platform qualification by inventing evidence.
