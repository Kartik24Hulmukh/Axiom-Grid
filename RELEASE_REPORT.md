# Release status — not production-qualified

The former September 2026 report's “PASS / cleared for release” verdict is
**withdrawn as qualification evidence**. It came from a deterministic regression
harness, could accept planted/default metrics, and labelled an unkeyed checksum a
signature. Historical text remains in Git history; it must not be used to approve
a production deployment.

Current authority: [docs/AUTHORIZED_PREVIEW.md](docs/AUTHORIZED_PREVIEW.md) and
[docs/RELEASE_QUALIFICATION.md](docs/RELEASE_QUALIFICATION.md).

- Passing focused CI establishes only the checks actually run at that revision.
- Deterministic benchmark success is not a real-model or native UI result.
- Cloud-tier policy rejection is not a network-egress measurement.
- A checksum is not authenticated signer approval.
- Missing, synthetic or self-reported data cannot establish production readiness.

**production_qualified: false**. Installer bundling remains disabled. No new
benchmark scores, test counts, real-device results or release clearance are
asserted by this document.
