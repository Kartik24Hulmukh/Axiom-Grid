# Authorized explicit-text preview

This profile is for an owned or expressly authorized device and permitted tasks.
An IT-approved installation and permission to use AI in an assessment are separate.
It is not a hidden overlay, auto-typing product or fleet deployment package.

## Boundary

- Visible taskbar window; no topmost default.
- Only explicitly supplied input; no other-app capture.
- Review and manual copy; no automatic insertion, file edits or message sending.
- No shell/filesystem/clipboard/screen permissions granted by the preview capability file.
- Generate, readiness and discard/cancel are separate requests.
- Clear session clears the displayed fields, not every possible copy of data.
- Missing prerequisites and unsupported platforms are failures, not fake successes.

The source remains a monorepo containing legacy automation and separate document
services. The tests guard the focused preview's allowlist, not the entire repository
or all transitive native code. Bundling remains disabled; no signed installer or
clean-host native release has been validated by this change.

## Before a real-model demonstration

1. Identify the exact authorized device, task, OS, build, backend and model.
2. Approve model/dependency/content rights and privately provision IPC credentials.
3. Qualify backend cloud settings, assets and model identity. Loopback is not provenance.
4. Test disconnected cold starts, missing assets, failure/cancel/quit and resource release.
5. Observe network behavior under an IT-controlled boundary and state its limits.
6. Test session separation, actual retained files/logs, uninstall and rollback.
7. Use a mock exercise; disclose manual copying, failures and any human intervention.

No hardware minimum or performance SLA is established here. Measure the full stack
with normal foreground applications on the slowest intended supported device.
A local-network server is a different multi-user architecture, not an offline toggle.

## Production blockers still open

Actual target-device window behavior and real-model native E2E; backend/weight
authenticity beyond reported identity checks; disconnected E2E; secure Windows
automatic pairing; private-key custody;
full-service parser/OS sandbox qualification (one extraction route now uses a
validated single child parse; see PARSER_BOUNDARY.md); legal-v3 trust/effect semantics; installer signing/upgrade/
uninstall; dependency/model license review; external security review; retention and
incident operations; actual customer value, repeat use and economics.

Focused native CI builds/tests and expected-model report checks have passed their
scoped gates; they do not close the target-device, backend-attestation or offline
items above. See MODEL_IDENTITY_POLICY.md and RELEASE_QUALIFICATION.md. The opt-in
DEVICE_QUALIFICATION.md collector gathers bounded profile information only.
