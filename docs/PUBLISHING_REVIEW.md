# Review publication scope

## Current publication update

A reviewed ASGI candidate now removes four middleware task wrappers while
preserving scoped request/header/security/logging/metrics contracts. Its
independent118cases and selected322-test profile pass, but the unchanged full
local gate still fails the latency requirement:511passed,1failed,1skipped,
P50=201.674716ms against<200ms on the2CPU host. This failure is retained, not
rounded down or retried away. See RELEASE_GATE_FOLLOWUP.md for every iteration
and qualification boundary. Exact final-head remote CI must be assessed anew;
preview-code integration is not production release or a hardware-independent
SLO claim. The source/workflow latency gate is unchanged.

### Earlier publication and lint-repair snapshot

PR36 is now merged into the assurance REVIEW branch at
8c7aad8d2ed853cb55682ed8c25750321a9a427a. The stack was explicitly unstacked
using GitHub's UI, which confirmed base branches and commit histories were
unchanged. The normal MCP merge then succeeded. Independent fresh-checkout
verification shows only the script's100644-to-100755 mode changed relative to
dd0e92c; script blob8c2cadb932acb3c17c6cbdf2ccedaae57fe9a0eb is unchanged.
Direct `./scripts/axiom-live-e2e.py --help` exits0 without inference/network.
The historical metadata blocker below is therefore CLOSED.

Authenticated CI inspection of run40739547947 showed395 service tests passed
in20.54s. The later strict changed-file lint gate failed on three server findings
(two import orderings and the asyncio.TimeoutError alias), not a failed service
test. This update fixes those three findings and pins Ruff0.17.3. Both Python
lint gates are now included in the selected assurance runner, preventing this
coverage gap. Final-head CI remains required; the earlier local latency miss
is still disclosed in RELEASE_GATE_FOLLOWUP.md, not rewritten as a success.
This snapshot precedes any main-branch integration; inspect actual GitHub state
for merge status. Production/model/native/offline qualification is not implied.

Review branch: `fix/authorized-preview-assurance-2026` in
`Kartik24Hulmukh/Axiom-Grid`. Original baseline:
`aa386b49f19e160491a8e7225cc01b391ae2e522`.

Implementation/continuation verdicts and delivered manifests are historical local
validation snapshots created before GitHub publication. Their statements that no
push had occurred refer to that snapshot. Use the actual GitHub PR/commit/check
state for current publication and merge status. Publishing is not deployment,
production approval or a claim of issue-free behavior.

The selected profile passed191 tests locally before publication, including on the
replayed source tree. The broader overlay run had211 passes and2 failures; no
full-suite, native UI, real-model, offline, installer or traction certification
follows. Remote CI and required reviews must be assessed before merging; no
repository protection or failed-check threshold should be bypassed.

The GitHub MCP input-size limit required long explanatory server comments to be
preserved in SERVER_SOURCE_NOTES.md. Executable Python AST equality was checked
before/after that relocation, and the selected profile rerun. This is a comment-
only transport accommodation, not a change to parser/security behavior. The PR
contains the actual source diff, including this relocation.

The exposed chat credential was not used or tested. Publication uses the user's
connected GitHub MCP authorization. No automatic desktop typing, hidden install,
assessment aid, production deployment or security-policy bypass is introduced.

## Historical publication metadata blocker (closed above)

The connected MCP uploader changed `scripts/axiom-live-e2e.py` from mode100755 to
100644 while uploading its unchanged validated bytes. Invoking it explicitly with
Python, as documented/tested, works; direct `./scripts/axiom-live-e2e.py` execution
requires restoration of its executable bit. This is NOT silently normalized as an
expected source-tree match. The draft PR must retain this blocker until a mode-
preserving Git write restores100755. All other supplied content matched the local
validated source. No merge/deployment should be inferred from publication.

## Historical follow-up

See RELEASE_GATE_FOLLOWUP.md for the corrected permission regression, unchanged
latency failure, reproducible runtime CI and mode-only PR #36. The mode repair is
verified but its stacked merge is blocked by the connected MCP endpoint; it has
not yet been applied to this review branch.
