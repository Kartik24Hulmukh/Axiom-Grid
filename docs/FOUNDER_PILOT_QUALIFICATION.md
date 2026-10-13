# Founder / product launch review — scoped, read-only

**Decision: NO-GO for GA. Conditional GO for consented buyer discovery and a low-risk, supervised offline evaluation; first paid pilot remains gated.** Sell an evidence-review workflow, not autonomous desktop execution or compliance. This is one independent reviewer’s analysis, not a convened council, buyer feedback, recruited-human result or funding outcome.

Review date: 2026-10-02. Requested base: `4f3a822`; inspected integrated working tree: `/data/axiom-third/repo`, HEAD observed during review `3cb10bb2205768d1ced1ebfcdf4cc4cf3767782d`. Runtime is advancing. Historical checkpoint results below are evidence from documents, **not fresh validation of this HEAD**. Parent owns final-SHA full tests and release verdict. No code, dependency, Git, remote, provider, outreach or grant mutations were performed; only this review artifact was written. No subagents were spawned.

## 1. Evidence and limits of this review

Read local sources:

- **S1:** `docs/RESEARCH_EXECUTION_LEDGER.md`, including original five-point premortem and scoped continuation.
- **S2:** `docs/PR_HANDOFF.md`; chronological hardening evidence, failed gates and superseded earlier handoff.
- **S3:** `docs/SCOPED_HARDENING_CHECKPOINT.md`; implemented owned-upload/CAS scope, actual known-ID/restart proof, retained failures and secret boundary.
- **S4:** root `README.md`; current public surface and historical status table.
- **S5:** `docs/RECEIPT_ADAPTERS.md`, `specs/OPEN_RECEIPTS_V0_1.md`, `scripts/axiom_receipts.py`, `kernel/core/receipt_adapters.py`, receipt implementation/test declarations.
- **S6:** `docs/launch/LAUNCH_KIT.md`, `site/index.html`, older `docs/LAUNCH_HANDOFF-2026-09-29.md`.
- **S7:** `overlay/server.py` owned-upload/review/source boundaries and `tests/browser/overlay.e2e.cjs` actual upload, repeat-review and conflict workflows.
- **S8:** repository `research-redteam-source.md`, read in full: an existing research critique, **not a recovered substitute for the original attachments**. Its external competitor, patent and regulatory assertions were not independently verified here and are not launch facts.
- **S9:** `/data/axiom-fourth/reviews/gateway.md`: contemporaneous local slice, not integrated release certification. No live model IDs validated.

**Original-research recovery:** Initial seven unique Markdown retrievals returned `file_not_found`; the parent then materialized all eight originals. Read scoped product directives, premortems, pricing, validation/kill criteria and 7/30/90-day requirements directly from each unique file; the two September 19 copies have identical SHA-256. **S10** denotes these recovered originals, listed below. This is focused research reconciliation, not fresh verification of their competitor, legal, funding, model or live-site assertions. Their own “verified” labels do not make those claims current facts.

| Original / directory under `/data/.agent-service/files/` | Read focus | SHA-256 |
|---|---|---|
| Council Verdict Sep-Oct 2026 / `70815b1f-e96a-43fe-8f03-bf53fbeea441` | Sections 1, 3–4, 6: receipt/OpenBot/benchmark bet, weekly proof gates | `64d7cbd3391a5d67a6d75a95723e0e88b89bda38df19c3b2fc123558358735c3` |
| GTM War-Room Final Research Summary and Action Plan / `bf6d852f-b984-49ae-8769-c06ccd200939` | Sections 2, 4, 5.2, 6: truth, premortem, price and validation | `ed26bb2268e31c6cc8a332fc7d922011c7c2026ce1c19d553fbe09e1c82e2cd2` |
| September 19 Premortem / `c8ed4d83-25f4-4dce-8b10-59ec984e8ff5`, duplicate `4bfabe61-d72f-476d-a66c-ee9bbd73296f` | Sections 1, 4, 6–8, 10: provenance bundle, buyer falsifier and launch | `e847eebc38a5ee40a5703b270076ca8995df54b6b65da5e724eb26dc2db2be73` (both) |
| GTM Premortem Verdict / `18fcfa32-fc89-425f-81b9-3866bb3b1aef` | Sections 1, 6.2, 7–8: stop list, paid pilot, validation | `b41cbaf6bbc1a24e1fe278252fb91e4b7a13bee6f1e8295a5cf84bc75e769090` |
| September 24 War-Council Final Verdict / `6cb98572-af7e-4a98-8775-71203f4081b0` | Sections 0, 4, 6, 7.2, 8–9: corrected offer, gates, failure criteria | `d41e2eadb0eb00479a2b592a8f262499dd56dd95329a719044ea207234b73598` |
| Final Report (1) / `0c23e0a8-765e-4be8-a176-d7dcc36e69fa` | Sections 1, 5, 6.2, 7–8: receipts integration, pilot and progression | `03302a4f8e42d4cc65effe985a428d9f877c4f68f4cfbb689095b15cc850a7e7` |
| Final Report / `eb50d68a-65b5-405f-bf08-41247f6dae1a` | Full 32-line summary/correction register | `60bc8229ef029d0fd2993f39986de94a45c94a423860d26e96fba1899f64d669` |

Parent subsequently reported the final frozen integrated runtime as `5583c840a94b7e6357f9bbc468ff4815014649e2`. This review does not certify that SHA: no tests were run here, and final serial-gate results must be attached by the parent.

No buyer counts, LOIs, valuation, pilot revenue, human success rates or post-GPT-6 claims can be inferred from this review or test suites.

## 2. Wedge mismatch: choose one purchase, not three

The current headline emphasizes signed document-agent receipts. Actual user-facing value is **owned upload → local extraction → inspect original source → explicitly record a human review with revision conflicts**. Explicit signed export is a **separate offline CLI** for supplied audit/trace JSON; the overlay does not automatically produce that receipt format for every upload/review. Legal-redline output is another separate workflow. Bundling these as a single autonomous end-to-end product would misrepresent implementation. [S4–S7]

Three incompatible launch promises must not coexist:

1. **Desktop automation / legal-redline replacement:** unavailable overlay native writer and read-back. A buyer wanting Word edits or unattended approvals is not qualified for the present pilot.
2. **Regulatory or sovereign execution certification:** no independent execution/network witnesses, no compliance determination. Assessor-led distribution is a discovery hypothesis, not an established channel. [S5, S8]
3. **Evidence-review utility:** presently credible as a supervised engineering preview, provided the buyer actually needs source-linked reviews or portable export integrity and can accept bounded local operation. [S3–S7]

**Proposed initial buyer hypothesis:** a small document-agent builder or internal automation team already spending reviewer time reconstructing extraction mistakes and exchanging JSON traces with a separate reviewer. Operational champion: the engineer/review lead who owns incident triage. Economic buyer: the budget owner for that workflow. An assurance practitioner can be the second verifier/advisor; do not assume they buy first.

**Suggested truthful pitch:** “Axiom-Grid is a local engineering preview for inspecting document extraction evidence and recording explicit human reviews. It also signs supplied trace exports for offline integrity verification against a separately pinned key. It does not certify execution, compliance or desktop edits.”

**Research-thesis mismatch:** the separate surviving research critique’s final 90-day thesis is independently observed desktop outcomes plus scoped network-boundary evidence above gateway receipts. The shipped preview has neither that desktop witness/read-back nor an external network witness. Narrowing to signed observations is therefore a **different, smaller wedge**, not completion of the research’s differentiation thesis. Validate this smaller purchase explicitly; if buyers only value the missing outcome/boundary proof, pause the receipt-led commercial pitch rather than claiming the roadmap is delivered. [S8]

Differentiation is not cryptographic exclusivity. Test whether reproducible evidence, source preservation and explicit disagreements reduce a concrete review burden better than the buyer’s existing logs plus spreadsheet. Free hashing/signing alone is unlikely to justify payment without that demonstrated workflow benefit; this is a hypothesis, not a market finding.

### Original-research directives: implemented versus still missing

The originals are not a single consistent purchase thesis: earlier memos favor legal-redline/compliance bundles, the September 19 memo proposes consumer Pro/Team tiers, September 24 rejects subscriptions without a hosted surface, and the later council elevates OpenBot receipts plus benchmark distribution. Choose a paid workflow before channel stacking. [S10: September 19 §§4,6; September 24 §§0,7.2; Council §§3–4]

| Research requirement | Current evidence / missing work | Executable disposition for this launch |
|---|---|---|
| One name, canonical proof surface, fresh-eye test | Local rebranding/claim repairs exist; remote deployment, redirects, repo metadata and indexing were not checked here | Five consenting fresh readers describe scope, download and verification without hints; owner later verifies hosted links. No claimed public deployment. |
| One-command cold verification under 60 seconds | Real Python CLI and sample exist, not the originally advertised `axiom verify`; cold-host installation/timing and independent usability unverified | Use actual command, time clean supported-host setup versus verification separately, retain tamper transcript. Missing standalone packaging is a gate if buyer needs it. |
| Open receipt spec + OpenBot live demo/every-action hook/PR | Experimental linear-chain spec and offline field adapter exist; live authenticated capture, compose demo, upstream engagement and merge absent | First prove authorized export handoff. Live hook/PR is future consented integration, not a current channel or every-action completeness claim. |
| Receipt-bound human review and legal-redline buyer | CAS review exists, but not automatic reviewer-identity/diff/sign-off receipt bridge. Legal-redline CLI uses separate manifests | Do not promise Article 50 evidence sufficiency or end-to-end review receipts. Buyers requiring a tracked-changes pilot need a separate legal-redline/read-back acceptance plan before quoting that scope. |
| Benchmark launch weapon / every run emits receipts | Retained synthetic workload/failure evidence exists; no universal benchmark receipt emission or external reproduction proven | Publish only exact-SHA, workload-scoped results after owner approval. Benchmark users are distribution evidence, not paying legal buyers or real humans. |
| External verification / timestamp anchoring | Pinned-key/checkpoint verifier exists; independent recipient result and RFC 3161 timestamping not established | Require real recipient transcript; timestamp authority is optional future feature, never replace missing trusted time with signer timestamp. |
| 10 interviews, at least 4 ready to try, signed scope/price/champion/date | No interviews or paid signal demonstrated | Run this kit; capture objections and authorized sample/next-step commitment, not sentiment alone. Review after 10 completed buyer interviews; if fewer than 4 authorize a real trial, revise wedge before broad promotion. |
| $650 bundle vs $10–25k deployment vs $499–999/mo pilots | These are conflicting offers/targets, not customer price evidence | Use a $650 bounded **evaluation** hypothesis without compliance deliverables. Larger deployment fee needs authorized scope, real workload and buyer budget; no subscription before repeat paid use supports it. |
| Regulatory urgency, competitors, grants, capital and model/video claims | Research contains mutually corrected claims; no independent current verification here | No legal deadlines/fines, market funding figures, competitor exclusivity, grant availability or named model-battle caption in pitch without fresh authoritative evidence. Do not submit applications or label credits revenue. |

**Discovery stop rule:** honor the research’s intent to falsify cheaply, not its unsupported conclusion that one sale establishes PMF or no replies alone disproves demand. After 10 completed interviews, require the trial-intent gate above. After a second revised batch (20 completed interviews total), if there is no budget-backed qualified pilot, pause this paid wedge and document whether pain, authority, evidence sufficiency or purchasing friction failed. Fifteen/twenty proposed emails are not delivered interviews; track delivery, permission and objections separately. There was no outreach here. [S10: September 19 §§4,8; September 24 §8]

## 3. Truth-boundary table

| Area | Actually implemented / documented local evidence | Not demonstrated / proposed | Allowed buyer wording / boundary |
|---|---|---|---|
| Owned upload / extraction | Opaque owned reference, bounded app-managed copy, admitted local parse, retained source; real browser workflow declarations | Every format on every OS; worst-case hostile parsing; production install | “Supported local preview on the verified pilot host”; declare exact format/version/limits. Files are not app-encrypted at rest. [S3, S7] |
| Scope and persistence | Full-credential-hash namespaces, SQLite WAL; two workers and process replacement on shared local filesystem | User/role IAM, independently authenticated people, multi-node HA | “Credential-scoped local evidence”; a shared key is not individual reviewer identity. [S3] |
| Human review | CAS rejects stale updates, unknown/wrong scope refused, current revision reload; source observations remain unchanged | Human edits re-grounded, factually correct, model training or universal calibrated confidence | “Records a human-provided review separately”; show original and reviewed values and revision. [S3, S7] |
| Native desktop writes | Unsupported writes fail closed | Live Word/Excel mutation and independent resulting-state read-back | “Read and suggest only”; failed Accept is a boundary, not activation. [S3, S4] |
| Legacy graph/eval | Authenticated legacy aggregates fail closed with 501; legacy image paths 404 | Tenant-safe graph/evaluation product | Hide from pilot scope; never call 501 a working evaluator. [S3] |
| Signed receipts | Ed25519, finite canonical JSON, linear chain, signed count/tail checkpoint, offline CLI | Merkle tree, adopted standard, witness of actual execution, automatic overlay receipt stream | “Integrity of supplied signed observations”; export is explicit and separate. [S5] |
| Freshness / trust | Caller pins public key; independently retained checkpoint can reject an older valid export | Trusted timestamp, complete capture, persistent append-only archive, rotation/revocation protocol | “Valid relative to pinned signer and supplied checkpoint”; list missing evidence. [S5] |
| Adapters | OpenBot export-field adapter; generic Opik/Helicone objects with string `id` | Live SDK hooks, paginated every-action capture, universal version compatibility | “Offline JSON-export adapters”; capture source/version remains buyer supplied. [S5] |
| Privacy / offline | Local preview/export need no provider; receipt excludes raw evidence content | OS-wide zero egress; secret-proof hashes; app-level encryption | Disable optional network services for offline pilot; hashes/labels still need access controls and low-entropy disclosure review. [S4, S5] |
| Gateway | Local fault/budget/circuit tests; newer explicit bounded discovery described in slice | GLM/Kimi/Qwen requested labels available, billed usage accuracy, live quality | Optional and out of initial pilot; live catalog and rotated credentials are separate gates. [S1, S3, S9] |
| Performance | Scoped checkpoint retained short-run, CAS/restart and synthetic load evidence | Final integrated-SHA full-load pass, 24-hour soak, 100x successful capacity | Name exact workload/revision; no human or 100x impact inference. [S2, S3] |
| Human / commercial | Automated browser journeys and synthetic identities; pilot/discovery plan | Recruited humans, customer deployment, LOI, revenue, willingness to pay | “Seeking design evaluators”; all commercial fields blank until evidenced. [S1, S6] |
| Distribution / compliance | Experimental format and local launch drafts | Public deploy, signed supported-platform install, external standard adoption, compliance approval | “Engineering preview”; legal/regulatory/patent research requires fresh professional verification. [S6, S8] |

**Specific copy debt:** README retains historical four-model HTTP-success and green torture descriptions; its warning helps, but they are not current live/model-quality proof. Older `docs/LAUNCH_HANDOFF-2026-09-29.md` still contains “category-defining/proof,” unshipped commands and five $499–999/mo pilots as a target. Archive/mark superseded or remove these from navigation before buyer sharing; never reinterpret that target as booked revenue. The adapter guide’s older preview-cache description must be reconciled with later scoped durable-state/expiry semantics at final SHA. [S2–S6]

## 4. Five-point launch premortem — product consequences

| Failure after launch | Observable leading signal | Prevention / verifiable decision |
|---|---|---|
| **1. Buyer bought desktop automation; received evidence tooling.** Demo slides or procurement notes promise edits/compliance/zero egress; reviewer asks where document changes went | Make buyer repeat the intended paid task in their own words before demo. Reject unsupported automation requirement. Require their acceptance of read-only scope and separate CLI. |
| **2. Verification badge becomes false assurance.** Buyer says valid signature means correct extraction or complete agent action capture; correction appears to overwrite source truth | Teach-back: buyer distinguishes original observation, human opinion and signed commitment. Run tamper, stale-checkpoint and unsigned/missing-capture cases. All must be labeled without “execution verified.” |
| **3. Small pilot collapses under concurrency or abandonment.** Tail latency, legitimate admission rejection or transport failures interrupt actual review; short green tests obscure loaded failures | Pin pilot-specific envelope before enrolling. Full requested release gates remain red until final independent run; never replace the existing zero-all-server-5xx / sub-200ms loaded-error gates with a looser gate silently. A lower-concurrency supervised exception requires written owner approval, not a GA label. |
| **4. Rotation / rollback strands or exposes evidence.** Old deployment key retained so buyer can access scoped records; old binaries reopened against incompatible migrated state; receipt trust key silently changes | Stop intake on compromise, rotate/revoke and audit, preserve protected evidence; test new-key accessibility/migration policy separately. Credential hash defines scope, so rotation may change namespace. Receipt signing rotation has no shipped protocol. Test compatible restore and key handoff before payment. |
| **5. Founder mistakes research and scripts for demand.** “120 users,” hypothetical pilot pricing, assessor urgency or grants appear as traction; humans cannot complete key pinning without founder | Separate funnel evidence from suite counts. Recruit consenting independent humans, benchmark their current review task and secure an explicit budget-backed paid task only after successful scoped evaluation. No grant urgency or model-era narrative substitutes for purchase proof. |

## 5. Minimal verifiable buyer workflow (two lanes; no invented bridge)

### Lane A — source-linked review, implemented path

1. Buyer supplies **one authorized, low-risk document** with a supported format and known relevant fields. Agree expected output/refusals before looking at the result. Record consent, content sensitivity and host/software versions.
2. Connect with a fresh deployment key via the tab-memory flow; upload through the owned-file control. Record opaque reference and retention terms; do not hand the runtime arbitrary filesystem paths.
3. Process the owned document. Inspect a suggested field and its source text. Compare bytes/hash and source anchor to the buyer’s authorized original. An empty/unsupported answer is a recorded outcome, not replaced by a fixture.
4. Reviewer edits a value with reason. A second authorized review session attempts a stale revision: show 409, current-value reload and explicit retry. Preserve original source/extraction separately from review revisions. Shared-key sessions test conflict behavior, not distinct-person IAM.
5. On the same permitted host, restart and re-read the known ID with the same credential; cross-credential request must not disclose it. Native Accept remains refused. Record timestamps, IDs, statuses and redacted artifacts.

### Lane B — signed supplied observations, separate implemented CLI

1. Buyer provides a consented real JSON audit/trace export, identifies its producer/version and missing capture scope. Never substitute synthetic sample data while calling it customer activity.
2. Owner provisions a dedicated Ed25519 key outside repository/chat. Private key permissions are restrictive; recipient receives public-key fingerprint through an independent channel. Deployment key and signing key are different.
3. Export using documented `python scripts/axiom_receipts.py export ... --source openbot|opik|helicone --private-key ... --output ...`; archive source evidence under access control. Signatures commit to its canonical JSON, not raw-file byte formatting.
4. Second person verifies with `python scripts/axiom_receipts.py verify ... --public-key ... --checkpoint ...`, using their independently retained latest checkpoint. The current checkpoint is within the export; retaining/exchanging it independently is an operator procedure, not an automatic CLI sidecar feature.
5. Verify modified-entry rejection, wrong-key rejection, truncation rejection and older-valid-export rejection **with** retained checkpoint. Also show that a well-signed dishonest/incomplete input can pass integrity: this teaches the remaining source-trust gap.

**Proposed, not shipped:** linking every review revision automatically into receipt export, attribution to individually authenticated reviewers, packaged pilot evidence manifest, lifecycle-aware signing rotation and a neutral independent implementation. Do not promise these in the first invoice. If the buyer only wants Lane A, do not force receipts into their activation metric; if they only want Lane B, do not require the overlay. Pilot scope must select the paid lane explicitly.

## 6. Executable buyer-discovery / qualification kit (draft; not sent)

### Recruitment list and funnel discipline

Founder manually identifies 8–12 candidates with an existing document-agent workflow, a named review owner and a separate recipient of evidence. This is a proposed target, not people recruited. Prefer an authorized direct relationship or public opt-in; no scraping/install/outreach was performed here. Split interviews between builders/review operators and 2–3 assurance/evidence recipients to test handoff value, not to imply an established assessor channel.

Track one row per **organization**, deduplicate people from the same team:

`organization | interviewee role | source/consent | last actual incident/date | current workflow/time/cost evidence | format + sensitive-data limits | required lane | reviewer + verifier | host/concurrency | economic buyer | budget/procurement path | next authorized step/date | objections | qualification decision | evidence location`

No estimated revenue, conversion or LOI entry without source artifact. An interview is not a qualified pilot; a quote is not an order; an order is not cash; a research target is none of these.

### Invitation draft

“Could we spend 25 minutes reviewing how your team investigates document-agent extraction mistakes or shares trace evidence? I’m testing a local engineering preview for source inspection, explicit human review and separate signed trace export. It does not edit desktop apps or certify execution/compliance. No sensitive data or purchase is required for the interview; any later evaluation would use your consented low-risk material.”

### 25-minute interview script (ask before demo)

- **0–5 min:** “Tell me about the last real extraction/review failure. What document/task, who found it, what consequence?” Ask to see a redacted artifact if authorized. Do not suggest the pain.
- **5–10 min:** “How did you establish what source the answer came from? What did the reviewer change? Where is disagreement recorded? What tools/logs did you already use?”
- **10–15 min:** “Who needs the evidence afterward? Would checking integrity change any decision? What evidence is missing even if a signature verifies?”
- **15–20 min:** “Which host/formats/data policies apply? What workload/concurrency? Can you supply a redacted sample and separate verifier? Do you require native editing, SSO, HA, regulatory certification or encrypted app storage?”
- **20–25 min:** “Who pays for this task today? What measurable outcome would justify a fixed evaluation fee? Who can approve it, and by when?” Ask permission for a scoped next step; do not count polite interest as buying intent.

### Binary qualification (no arbitrary score hiding a veto)

**Qualify only if every mandatory condition is yes:**

- A recent recurring task and actual current workaround can be described with evidence; buyer chooses Lane A or B and a concrete decision it supports.
- Named operator, evidence recipient and budget owner; authorized route to agreement/payment.
- Consented redacted/public/low-risk dataset and supported pilot host/format; no production dependency or high-stakes automated decisions.
- Accepts read-only scope, separate receipt CLI, no execution/compliance/zero-egress guarantee, and explicit data/key retention limitations.
- Pilot envelope and success/abort measures agreed **before** tests; rollback, deletion/retention and incident contact approved.
- A second person can verify without receiving a private key; founder is not the only evidence interpreter.

**Disqualify/defer** if buyer requires native live writes, 24/7 production SLA, cross-node HA, per-person enterprise IAM, automatic every-action capture, whole-machine air gap proof, legal certification, unsupported conversion paths or vendor model IDs not validated. Also defer if they will not authorize sample use or cannot name who pays. Offer an interview only, not an unsupported paid deployment.

### First paid-pilot offer template (hypothesis)

- **Term:** two weeks; one organization, one agreed host, one selected lane, at most two concurrent reviewer sessions, 20 low-risk documents or one bounded real trace export (within implemented event/export limits), no unattended production use.
- **Fee:** propose a fixed **US$650** evaluation fee only after the buyer confirms budget and scope; this is an experiment, not validated pricing, MRR or booked revenue. Founder can reject/requote based on actual procurement; no discount creates a success result.
- **Buyer provides:** authorization, ground-truth reviewer, source/export with provenance, verifier and approved host/security policy.
- **Founder provides:** supervised setup, scope sheet, evidence inventory, documented rejection/gap cases and final comparison against buyer’s current task. Manual packaging must be labeled manual.
- **Acceptance:** agreed task completion and integrity cases, independent teach-back, no cross-scope disclosure/source mutation, buyer-baseline comparison and disposition of every unresolved case. No guaranteed accuracy/time-saving percentage before baseline.
- **Stop/refund terms:** define in signed agreement before intake; stop on exposure, isolation failure, unapproved network call, unsafe source mutation or repeated envelope violation. Do not claim legal enforceability; founder/legal reviewer approves terms.
- **Exit:** export authorized evidence; verify retention/deletion, revoke pilot access, document what cannot be safely deleted (e.g., backups) and obtain buyer acknowledgement. Customer pays for a scoped evaluation/service, not a production-ready autonomous agent.

### Evidence required before first paid intake

A folder/checklist prepared by owner, with each item linked to an artifact rather than a checked box alone:

1. Signed/approved scope and authorized data use; named buyer/reviewer/verifier; purchase agreement/approved order and secure payment process. Revenue is recorded only when actually received under applicable accounting treatment.
2. Frozen build/version and host dependency/license inventory; independently reproduced minimal workflow on that host with no ignored safety failure; known final-SHA full-suite/load results and skips disclosed.
3. Credential revocation/audit evidence, freshly scoped deployment credentials, private signing-key custody and independent public-key fingerprint/checkpoint receipt.
4. Real authorized source/trace, redacted observed statuses and negative cases, recipient verification result; no synthetic substitution. Any manual step marked manual.
5. Measured baseline task and precommitted success criteria; signed-off operating envelope, incident/rollback rehearsal and retention/deletion test result.

If one is missing, run discovery or a consented low-risk evaluation instead. A smaller paid scope does not convert a failing GA gate into a pass.

## 7. Remaining real-human evaluation (proposed, not results)

**Stage 1:** five consenting participants from at least two candidate organizations: three operational reviewers and two evidence recipients. Separate roles from number of people; avoid counting the same person twice. Record compensation, consent, prior experience, accessibility needs and permission to retain screen/task data. Founder is a moderator, not a counted independent user.

Each performs a baseline task using their current workflow, then the matched Axiom task on held-out authorized material; alternate order to reduce practice bias. Prelabel a small corpus of supported clean inputs, ambiguous/conflicting facts, missing source, unsupported inputs and tampered/stale/wrong-key receipts. Include deliberate BLOCK, abandoned upload, two-session conflict, reload/restart, expiring source link, mobile/keyboard and unsupported Accept. Do not inject fake backend success. The second verifier should receive only authorized artifacts and separately pinned public key/checkpoint, not founder hints/private key.

Log **unassisted completion**, help interventions, elapsed task time, reviewer disagreement, incorrect confidence/claim interpretations, failed source resolution, 409 recovery, retained source hash, verification negative-case decision, serious safety event and willingness to commit a next paid task. Denominators are completed/attempted tasks and unique consenting people, with dropouts shown. Do not summarize tiny samples as representative accuracy or general market conversion.

**Proposed progression gate:** zero observed cross-scope disclosure/source mutation/private-key leak/false “execution verified” declaration; every participant explains at least the signature-versus-truth distinction after onboarding; each lane has an independently completed real task; all serious usability blockers receive a disposition. These are small-study progression criteria, not a universal safety theorem. If failure occurs, checkpoint at no more than five remediation cycles per failing module and re-test affected cases without erasing earlier failures.

**Stage 2:** expand to 12 consenting humans across at least three organizations only after Stage 1 blockers close; include a distinct assistive-technology user and less technical reviewer if appropriate to buyer population. Measure repeat use after one week and explicitly ask for a budget-authorized paid next step. A requested “100+ real-human” completion claim would require actual separately consented recruitment and retained evidence at that scale; neither 120 scripted identities nor 100-way CAS provides it. Do not perform that expansion merely to manufacture a vanity count. [S1–S3]

## 8. Seven launch priorities only (owners, acceptance and blockers)

| Priority | Owner / executable action | Verifiable acceptance | Current blocker / decision |
|---|---|---|---|
| **P0-1 — truthful offer** | Founder: publish one chosen paid lane/scope sheet; mark obsolete launch docs historical and reconcile expiry language | Final-SHA claim sweep links each advertised capability to runnable path/evidence; buyer teach-back rejects execution/compliance/100x/model-era implications | Older proof/unshipped-command/pilot-target language; recovered originals contain conflicting commercial directives. Discovery can proceed with explicit disclosure; public claim reconciliation incomplete. |
| **P0-2 — credential safety** | Owner/security: revoke posted/historical provider and Git credentials, reissue least privilege, audit usage/access copies; separate signing/deployment keys | Redacted revocation identifiers/times, usage review, fresh scoped credentials; verified new-namespace access/retention plan and independent signer fingerprint | Removal/scanner output is not revocation; credential-hash scope may strand old records; signing rotation protocol absent. Blocks remote/live use and paid sensitive intake. |
| **P0-3 — reliable pilot envelope** | Runtime/release owner: freeze final SHA, run independent minimal workflow/full suites and retained strict load on intended host; set controlled preview limits | Report exact status/transport/error maxima/all-server errors, skips, host limits and abort policy; zero safety failures; requested full release gates actually pass before GA | Historical 503/transport/tail gates remain red; parent tests in progress are not results. No 24h soak/platform certificate. Lower-load exception must be explicit and supervised. |
| **P0-4 — evidence handoff trust** | Evidence owner + independent recipient: real consented export, separate key/checkpoint pinning, negative verification cases | Recipient reproduces integrity verification and tamper/wrong-key/truncation/stale rejection; lists capture, replay, timestamp and source-honesty gaps | Synthetic sample only is insufficient; independent implementation/rotation/execution witness not demonstrated. Blocks receipt-based paid value claim until actual handoff. |
| **P0-5 — operable rollback/data lifecycle** | Operator: exercise intake stop, drain/restore on compatible version, protected evidence export, TTL/backup deletion and incident response | Rehearsal records restored IDs/revisions/source hashes, denied other scope, readiness/drain and buyer-approved recovery/retention; no secret restored to enable access | No demonstrated pilot recovery objectives or rotation/migration/deletion rehearsal at final SHA; local shared WAL not HA. Blocks paid intake. |
| **P1-6 — real-human task evidence** | Research owner: run Stage 1 then affected retests with consent and preregistered cases | Task-level attempts/help/failure evidence from actual people and independent recipient, no serious unresolved safety/assurance confusion, no scripted-human substitution | No recruited-human results. Blocks usability/success-rate claims; permits recruitment and clearly labeled moderated learning. |
| **P1-7 — buyer payment proof** | Founder: complete interview sheet, qualify one buyer, agree baseline/task/fee/scope; separate orders from receipts | Named budget owner and approved paid scoped agreement, actual acceptance evidence, payment only recorded after receipt; next-use decision captured | No demonstrated demand, LOI, bookings or revenue; proposed $650 unvalidated. Blocks traction claim and scalable business thesis, not discovery. |

## 9. Launch controls / rollback / secret rotation runbook (proposed procedures)

**Before any intake:** named release owner and incident contact; immutable pilot artifact/revision, supported host and bounded network configuration; protected source/evidence/receipt inventory; separate pilot credentials; owner-approved retention/backup location; no public raw secret scan/log export. Run supported install and source/credential-scope/refusal negative cases, then test restore on a copy before enrolling.

**Start small:** one organization and agreed lane, scheduled supervised session, admitted workload within measured pilot envelope. Optional gateway/telemetry network paths disabled unless separately consented and verified. There is no live-provider requirement for core preview/export. Use per-request correlation and redacted operational records, not source content in public logs. Agree recovery time/point with buyer before contract; do not invent an availability SLA from local short runs.

**Abort triggers:** suspected private/deployment key exposure, cross-scope read, unintended source mutation, false execution/compliance rendering, unapproved network activity, data corruption, persistent 5xx/transport failure or exceeding agreed recovery/latency envelope. Stop new intake, preserve restricted evidence, notify named owner/buyer through approved incident channel; no automated public announcement is proposed.

**Rollback:** stop intake → drain/join work → take consistent protected application-state/owned-file backup (not casual copying of a live SQLite file while ignoring WAL) → preserve immutable receipts/checkpoints and schema/version inventory → deploy only a compatible known-good pilot build against a tested copy/restore → verify readiness, known IDs/CAS revisions/source hashes and cross-scope denial → reopen only with explicit owner/buyer approval. If downgrade schema compatibility is unknown, remain stopped; do not point older code at migrated production state or erase evidence to obtain green health.

**Rotation:** revoke provider/Git exposure at issuer and audit historic/chat/fork copies; do not use posted secrets for testing. Issue replacement least-privilege credentials via private mechanism, not chat or source. Deployment-key rotation changes hash-derived evidence scope: explicitly decide retention/re-export or verified administrative migration; do not reassign old unscoped records or silently weaken authorization. Until migration is implemented/tested, preserve old evidence securely with documented owner recovery procedure, without re-enabling a compromised bearer. Signing key is independent: preserve old public key/checkpoint for historical verification, publish a new fingerprint via independent channel and record validity intervals. Because v0.1 lacks a shipped rotation/revocation protocol, this is manual custody metadata, not automatic verifier-enforced revocation. A mathematically valid old signature is not proof the old key was uncompromised.

**Exit:** confirm authorized evidence transfer, revoke pilot access, exercise TTL/deletion/backup retention, document legal holds and non-erased copies. Snapshot a reviewer-readable results/gaps report. No silent retention promises or unverifiable memory zeroization.

## 10. Catalog decision and parent handoff

No new catalog tool is justified for this read-only product review. Existing pinned browser testing, local trace instrumentation and checksum-verified secret scanning have concrete relevance; their historical retention is documented, not a fresh license/security clearance of the full transitive tree. Before distributing any pilot bundle, owner verifies exact dependency versions/licenses, notices, supported install, update policy and vulnerability exposure. No blind plugin or framework install, trading/offensive tool or parallel orchestration layer helps establish buyer demand or missing desktop witnesses. [S1–S3, S5]

Parent handoff: retain NO-GO for GA; use the seven items as acceptance/blocker ledger. Report final integrated-SHA suite results separately, without adding overlapping totals or reusing earlier benchmark claims. Original research is now recovered and scoped requirements reconciled below; do not treat its market/legal assertions as fresh verification. A paid pilot is a reversible scoped evaluation with a budget-backed buyer, not evidence that the entire repository is production-ready.

### Stable document fingerprints captured during review

```
README.md                                  c0f167c70bc519dea0f728438b1495f8afc61c547f4e2d49e9b5d84a25f356d4
docs/RESEARCH_EXECUTION_LEDGER.md           499e64189bcc10e6514a01001458f9f4900fce40348a44029c0c2184db1800f4
docs/PR_HANDOFF.md                         13859e6381afeb657a9909bc3a3b7a984a94256a279e573e020facbd2b9ca006
docs/SCOPED_HARDENING_CHECKPOINT.md         1fb30ae5010ae5c3e0ac989d1f148ccf5a52261d229e303819cbeb8ca062ad51
docs/RECEIPT_ADAPTERS.md                    4fb0d222996c320fbc0fd4d993900ebc54fcf32b9ae8639a089c048d9a167bc5
specs/OPEN_RECEIPTS_V0_1.md                 818decc21189c8d805e6ec1e6503ba0217d83de1a3deb405ba781a7b1baf7503
research-redteam-source.md                 046c926cc28ea43b9b2202d6fb0a95d4ea3d6b02a534e9114b78c493e20b5616
```

## Parent final integration note

Final runtime b28d58a has 507 strict passes, 1,466 broad passes/four skips and 39 browser checks. Final short 100-client runs have zero observed 5xx/transport failures but miss 200 ms errors; 100 distinct credential workflows pass functional gates, not latency. This updates the advancing-SHA context above without converting the reviewer's untested analysis into certification. The current council checkpoint and delivery manifest control release status.
