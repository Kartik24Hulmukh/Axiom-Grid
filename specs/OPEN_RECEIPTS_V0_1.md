# Open Receipt Specification v0.1 — engineering preview

**Purpose:** portable, offline-verifiable signed observations of agent actions and trace exports. Reference implementation: `kernel/core/agent_receipts.py`. This is an experimental Axiom-Grid format, not an adopted ecosystem standard.

## Event and canonical bytes

Each entry has exactly `payload`, `entry_hash`, `signature`. Payload has exactly:

| Field | Meaning |
|---|---|
| `version` | `axiom.receipts/0.1` |
| `session_id` | One non-empty identifier for the export |
| `sequence` | Integer, contiguous from zero (booleans forbidden) |
| `event_id` | Unique within the session |
| `observed_at` | Signer's UTC ISO-8601 observation timestamp, not an independent trusted timestamp |
| `source`, `source_event_id` | Upstream source and event/trace identifier |
| `action`, `outcome` | Observed action type and outcome; exports must not imply execution verification |
| `evidence_sha256` | SHA-256 of the canonical source JSON; source content is not exported |
| `prev_hash` | Previous entry hash; empty for genesis |

Canonical bytes are Python-compatible JSON: sorted object keys, no whitespace, ASCII escapes (`ensure_ascii=True`), no NaN/infinity. v0.1 does not promise RFC 8785/JCS interoperability; cross-language implementations must reproduce these bytes exactly. The entry hash is SHA-256 of canonical payload bytes. The Ed25519 signature (128 lowercase hex characters from the writer) covers those same bytes. This is a **linear hash chain, not a Merkle tree**.

## Export and verification

An export has exactly `entries`, `checkpoint`, `checkpoint_signature`. Checkpoint has exactly `version`, `session_id`, `entry_count`, `tail_hash`. Sign checkpoint canonical bytes with the same key. Verify its signature, exact schema, count, session, sequence, unique event IDs, each hash/signature/link, and tail. Enforce 64 KiB source-event JSON, 16 MiB export, 10,000-entry session limits. CLI rejects duplicate JSON keys, oversized files, unavailable/wrong keys, and malformed exports with nonzero exit.

Public key trust is **out of band**: the verifier requires a caller-supplied pinned Ed25519 public key and never trusts an embedded replacement. A signed checkpoint detects truncation relative to that export. Detecting replay of an older valid export requires retaining the latest checkpoint independently and passing `--checkpoint`. v0.1 has no external witness, timestamp authority, append-only persistent store, or key-rotation protocol. An empty signed session is valid but proves no activity.

## Privacy and assurance boundary

Raw prompts, tool arguments, credentials, document text and results are not copied into receipts; they are committed to by their hash. Low-entropy sensitive content can still be guessed against a public hash: protect receipts with access controls and consider a future keyed/redacted commitment protocol. Caller-selected identifiers and action labels must not contain secrets. A valid signature proves the pinned key signed the observation; it does **not** prove the agent actually did it, that the source exporter was honest, that all actions were captured, citation correctness, legal compliance, or absence of network egress. Evidence corroboration and external execution witnesses are separate gates.
