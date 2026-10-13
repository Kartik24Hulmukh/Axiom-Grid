# V8.8 textual platform-claim checkpoint

## Fix and actual evidence

The existing Linux README honesty guard previously executed only `pass` when a
line contained a verified ghost-typing claim. This did not enforce its stated
contract. The current README did not advertise that false claim; this correction
protects a guard against future explicit unqualified assurances.

An exact-source temporary-layout negative test froze the failure before editing:
**4 failed, 18 passed, 1 skipped** across the original module and new contract.
After the guard correction, the identical selection produced **22 passed,
1 skipped**. Four intentionally false verified claims must trigger actual
`pytest.fail`; seven explicitly negative or non-native qualifications remain
accepted. Source bytes are copied unchanged, no native platform behavior is
mocked, and import-time `sys.path` mutation is restored by the test harness.

The classifier is deliberately lexical, not a general natural-language truth
parser. It removes explicit `not`/`never [CI-]verified` phrases, checks whole-word
`verified`, and allows `pending`, `scaffold`, and `compile-only` qualifications.
This is not evidence that any qualified statement is true or that live desktop
support works. Other existing guards and the missing-workflow skip are unchanged.

## Additive enforcement and limits

`platform-claim-contract.yml` selects only the actual guard module and rejection
contract, with read-only contents permission and a five-minute job. Python 3.13,
pytest 9.1.1 and Ruff 0.16.10 are selected; dependencies/action references are not
an immutable transitive/hash-pinned supply-chain guarantee. No existing workflow,
strict gate, status, workload, expected response or latency threshold was changed.

The unchanged local strict gate passed **686 tests and 44 subtests**, plus three
absent-engine/real-PDF checks; lint and compilation passed. The existing Starlette
deprecation warning remains. Counts overlap and are not full-suite, platform,
soak, training or production certification. Generated benchmark files were
retained externally then restored; no benchmark delta is published.

Recorded original guard history supports a **1 -> 2/5** source revision; new
contract/workflow/document each start at one. No runtime budget is reset.

## Separate failures and owner evidence

Prior published head `cbaa1d79` retains 11 successful checks and one failed
`requested-load-bounds` check. Its run has an existing load artifact, but public
artifact download requires authentication (401); job logs require admin rights
(403). Artifact name references merge commit `2b90cecf`, whose tree equals the
published/local `cd49e4a` tree and whose parents are main `aa386b49` and review
head `cbaa1d79`. Metadata provenance is verified; artifact contents, individual
Python/Node outcomes and remote timings are not yet verified. Do not relabel
historical/local failures as current CI stdout.

Independent static review also identified an edit-conflict reload that omits the
human/not-re-grounded confidence annotation, a stale Reject path without its own
explicit CAS recovery, and a PPTX upload/picker versus ingestor mismatch. These
are unexecuted reproduction recipes, not fixed runtime or new test results.
Frozen runtime/browser lanes remain unchanged.

Production launch and merge remain NO-GO. Existing failure/cancellation/custody,
credential revocation, legal/transitive distribution profile, provider controls,
training assets where required, clean native-platform install, encryption/IAM,
deployment/soak/rollback and consenting human/customer evidence remain separate
requirements. Neither lexical guards nor simulated personas establish native
support, traction, product-market fit or a 100x claim.
