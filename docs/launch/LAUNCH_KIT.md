# Axiom-Grid — Engineering Preview Launch Kit

**Do not publish as a production launch.** The requested zero-5xx and sub-200ms loaded-error gates remain open. This kit replaces obsolete ghost-writing, trained-model, Merkle-receipt and installer promises.

## Positioning

Signed, offline-verifiable observations for agents that touch documents. The narrow wedge is captured trace export plus pinned-key verification, not a new general-purpose computer agent or a compliance certification.

## What can be demonstrated

- Actual local document extraction, safe source-text inspection and correction recording.
- Explicit OpenBot AuditEvent or Opik/Helicone JSON export into bounded Ed25519-signed linear hash chains.
- Offline CLI verification against an owner-pinned public key and retained checkpoint.
- A separate legal-redline CLI that produces new local output artifacts under its own manifest format.

The overlay cannot write into desktop applications: Accept fails closed. There is no live every-action OpenBot hook, external witness, Merkle tree, OS-wide zero-egress certificate, trained-model performance proof or verified signed installer in this preview.

## Preview checklist

- [ ] Rotate exposed provider and GitHub credentials; review audit logs and history copies.
- [ ] Close load, soak, platform, independent-verifier and deployment gates on the actual release SHA.
- [ ] Capture a real consented agent trace; use an owner-provisioned key, not the sample key.
- [ ] Have another evaluator verify the export with an out-of-band public key and retained checkpoint.
- [ ] Record the actual workflow, including rejected/tampered verification and unsupported writes.
- [ ] Confirm published site, repository, documentation and download links actually work.
- [ ] Review preview wording and launch scope before posting. No outreach, grant filing or public launch has occurred.

## Candidate Show HN draft — not submitted

**Title:** Show HN: Axiom-Grid — offline-verifiable signed observations from agent trace exports

I am building an engineering preview for teams that need portable evidence from document-agent workflows. It exports captured audit/trace JSON into signed observations and verifies integrity offline against a pinned public key and checkpoint.

Signatures do not prove that an agent executed an action, captured all activity, cited correctly or complied with a regulation. The adapters currently consume exports; they are not live instrumentation. The desktop overlay is read-and-suggest only, and high-load launch gates remain open.

I am looking for feedback on the export format, pinned-key workflow and independent reproduction—not claiming customer traction or production readiness.

## Reproducible demo

```bash
pip install cryptography
python scripts/axiom_receipts.py verify examples/receipts/sample.json \
  --public-key examples/receipts/sample-public.pem \
  --checkpoint examples/receipts/sample-checkpoint.json
```

This is a synthetic signed sample. Provision a private key separately to export real captured events; follow `docs/RECEIPT_ADAPTERS.md`. Never publish a private key. Record an actual successful verification plus tamper rejection rather than animating a verification badge.

## GTM experiments — hypotheses, not results

1. Recruit consenting design evaluators with real exported traces; do not label scripted identities human testers.
2. Define activation as a real export verified in another environment with an independently pinned key.
3. Track export/verification success, time-to-first-verification, usability failures and repeat usage.
4. Test willingness to pay for a scoped provenance/evidence bundle. Research pricing and pilot targets are hypotheses, not revenue or bookings.
5. Recheck current grant eligibility and legal/equity terms before any founder-approved submission.

No testimonials, user counts, trained-model metrics, paid pilots, deployments or funding outcomes are asserted. See the current verification report and `LAUNCH-BLOCKERS.md`.
