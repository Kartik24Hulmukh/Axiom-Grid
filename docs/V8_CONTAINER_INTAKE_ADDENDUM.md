# V8 container-intake follow-up — launch remains NO-GO

## Observed failure and reproduction

On published head `9ef9ff99df218bdf4df7bce4df036efe011253e1`, remote CI completed seven checks successfully and failed `requested-load-bounds` and `overlay-container`. The container image build and read-only non-root startup/readiness steps succeeded; its authenticated PDF/DOCX step failed. Public job metadata establishes the failed step; detailed logs returned HTTP403, so its exact original traceback is not attested.

The unchanged probe was independently replayed against the verified source and a real local server. It raised HTTP404 when passing its generated temporary-file path directly to `/api/extract-document`. That path is outside the authorized corpus/owned-upload namespace. This is consistent with the remote failure, not a claim that inaccessible remote logs were read.

## Minimal correction

- Generate the same real compressed PDF and actual DOCX.
- POST each document's bytes to `/api/documents?filename=...` under the same bearer.
- Check byte accounting and use the exact returned `uploaded:` opaque reference for extraction.
- Preserve memo/nonempty-field assertions and add a real grounded UNCLASSIFIED value assertion.
- Keep a separate real-socket regression proving an authenticated arbitrary temporary-file path still returns404.
- Preserve Docker stdin execution: `__name__ == '__main__'` calls main; no repository-path or `__file__` assumption.

Only the smoke producer and a new regression module changed. No server/auth/admission/store/threshold/workload or existing guard changed. No provider call, exposed credential, retry or widened file allowlist was used. Independent read-only council review found no blocking issue; it did not execute tests or attest the container.

## Narrow verification and retained mistakes

- Baseline: unchanged probe reproduced authenticated tempfile404 over a real socket.
- Initial new narrow run: one passed/one failed, because the probe asserted `upload:` instead of the actual `uploaded:` API prefix. One import-order lint finding was also retained.
- Corrected narrow run: two passed in2.38s, with ResourceWarning and pytest unraisable warnings as errors; E9/F/I lint and compilation passed.
- Positive test executes real upload, storage, isolated PDF/DOCX parsing and grounded extraction. Negative test verifies denial rather than bypassing it.
- Parent strict/expanded revalidation and the exact-image final-head CI replay are separate gates; their results will be recorded in PR comments/evidence, not inferred from the narrow pass.

The computer reverted to an earlier checkpoint during continuation. Recovery fetched and verified PR head9ef9ff99/tree924502367278bf856fe2155ed06c06679a918b98 and restored the published checksummed archive. Lost pending probe edits were reconstructed without resetting any inherited server or diagnostic cycle budget. The first post-rollback log-redirection failure ran no lint/tests; it is not counted as a validation pass.

## Release decision

This corrects a probe/API-contract mismatch; **only a successful authenticated PDF/DOCX exact-image rerun can close the remote container gate**. Previous source-tree equality and CI results belong to their original SHA. Verify the new complete remote tree and all new-head checks separately.

Loaded errors above200ms, two classified but causally unresolved timed transport losses, training/platform/operational/credential/human evidence gaps and the diagnostic5/5 freeze remain. The PR stays draft, main remains unmerged, and no launch/100x/traction certification follows.
