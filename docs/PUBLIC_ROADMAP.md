# Axiom-Grid — evidence-led roadmap

**Current state: authorized engineering preview, not a production launch.**
This replaces the older Kairo roadmap's unsupported “shipped air-gap,” universal
signed-audit and v1-launch claims. Historical implementations and passing unit
checks are not proof of native/offline qualification.

## Product boundary

The current desktop preview accepts explicit user context and displays a
suggestion for manual copying. No covert installation, background capture,
automatic typing, application control or exam-policy bypass is approved. Use only
on authorized devices and permitted tasks. See [AUTHORIZED_PREVIEW.md](AUTHORIZED_PREVIEW.md).

The repository also includes a separate document-service path and inherited
research/legacy components. Their capabilities must not be conflated with the
native preview's shipping surface.

## Priority 1 — trustworthy release decisions

- Fail closed when evidence is missing, malformed, synthetic, stale or mismatched.
- Keep deterministic regression checks separate from real-device qualification.
- Retain existing performance workloads and thresholds; report failures honestly.
- Remove fabricated certification and unapproved signing success paths.
- Complete build-specific license, dependency and model-asset review.

## Priority 2 — one qualified end-to-end device profile

Select one OS, hardware configuration, backend and exact model artifact. Test the
actual compiled UI, pairing, inference, cancellation, shutdown, disconnected cold
start and failure handling. Establish backend/model provenance and enforce network
policy at an appropriate boundary. Loopback transport and self-reported identity
are not attestation. Measure latency, memory, thermals and failure rates on the
specified profile before setting a customer promise.

## Priority 3 — controlled distribution and customer validation

After target-device gates pass: sign/notarize the actual installer, verify clean
install/update/uninstall and rollback, secure pairing/key custody, retention and
crash handling, and obtain independent security review. Run a small consent-based
pilot for a clearly permitted task; measure repeat use, task time saved, output
quality and willingness to pay before expanding scope.

## Deferred until justified

Fleet rollout, silent installation, autonomous application control, marketplaces,
large swarms and enterprise compliance claims are not launch prerequisites.
Additional features must address demonstrated user needs without expanding the
preview's authority accidentally.

No roadmap item promises a release date, valuation, “100×” improvement or traction.
[Release qualification](RELEASE_QUALIFICATION.md) lists the evidence boundary.
