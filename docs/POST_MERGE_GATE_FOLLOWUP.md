# Post-merge latency gate follow-up

## Observed failure, not a retry target

PR34 integrated reviewed head461b9a71c8e08ac360c1dd3934f3d026aac38916 at
main merge b7d497aef4d236c290b360e5bb330012bf585fb7 after all six PR checks
passed in run40747890382. Git verification proves the merge source tree is
identical to the reviewed head. The subsequent main run40749401103 FAILED:
512passed,1failed,1warning in32.91s. Its unchanged600-request/100-thread
surrogate-burst P50<200ms assertion measured225.070125ms
(P95=471.655426ms,P99=513.604529ms). PR success did not establish a stable
latency result. Production qualification remains blocked; no rerun-until-green
is used as a fix. Earlier local201.674716ms failure remains in release notes.

The repository's pre-existing dynamic GitHub Pages website automation ran
successfully at the merge. This is website publishing, not a desktop/fleet
installation or proof of product qualification.

## Narrow remaining transport change

The follow-up extracts auth/rate no-await gate blocks into synchronous helpers
returning the same early response or None for delegation. Legacy async callables
remain and use those helpers. Small pure-ASGI adapters invoke the helper and
pass accepted scope/receive/send unchanged, without body buffering, new tasks,
exception interception or cancellation suppression. Their registrations occupy
the original positions; tracing, when explicitly enabled, is otherwise unchanged.

Fail-closed401/503, tenant state, all configured digest comparisons, exemptions,
rate429/Retry-After, sliding-window expiry, bucket eviction/caps, proxy/IP keys,
shared lock and dynamic globals must remain unchanged. Static AST checks compare
the original gate blocks, allowing only successful delegation to return None.
Independent contracts and strict warning gates are required before publication.

Source note pointers are compacted, with the file-level path to
SERVER_SOURCE_NOTES.md preserved; two long explanatory comments are retained
verbatim as note27. This transport-only change has identical Python AST.

The latency workload, quantiles, threshold, CI warning/error propagation,
validation hygiene, request/rejection logging and branch protections are not
weakened. No production, offline, real-model, installer, user-value or traction
claim follows from an in-process service test.

## Follow-up local validation result

The final auth/rate candidate passes the unchanged full service gate:
**573passed,1skipped,1existing dependency warning in29.39s**, with
ResourceWarning and pytest unraisable warnings treated as errors. JUnit
verification confirms the ORIGINAL surrogate-burst600request/100thread/P50<200ms
test passed (not skipped). The only skip is the realchmod integration on a
privileged-readablehost; the separate deterministic PermissionError test passes.
No exact passing quantile is claimed because the unchanged test emits values
only on failure. This is one scoped run, not a stable production SLO proof.

Independent contracts:181passed,1existing warning in0.84s, including61new
auth/rate cases plus prior response/guard/hygiene contracts. Helper ASTs match
baseline gate logic after delegation normalization; key extraction/authentication
and client-key ASTs are unchanged. Fail-closed gates, all-key comparisons,
dynamic policy/state/limits, expiry/eviction/caps, lock release, streaming,
cancellation and full-stack order were independently checked.

Selected assurance passes **383 tests**, both configured lint gates, source and
whitespace checks. These counts overlap; do not sum them. Pre/post-suite source
fingerprints are identical; the latency test, CI workflow and dependency lock
are byte-identical to the merged baseline. No retries-until-green or weakened
gates were used. Source-note pointer compaction is Python-AST-identical.

Exact-head remote CI and subsequent main-push CI remain separate requirements.
A passing local run does not erase earlier failures or certify real sockets,
compiled desktop interaction, real local models, disconnected-network behavior,
clean-host installers, external security or customer/business value. No
production desktop/fleet rollout or100x/traction guarantee is authorized.

All seven bounded local downstream checks pass on this executable source:
concurrency posture, undrained-log/shutdown spike, health/readiness/metrics and
security-header smoke, deterministic memo fixtures, adversarial memo fixtures,
synthetic authenticated loopback traffic and mixed local stress. These are
fixture/loopback checks, not model/native/offline/production certification.
