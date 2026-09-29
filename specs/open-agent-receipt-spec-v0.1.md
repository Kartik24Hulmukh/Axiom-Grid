# Open Agent Receipt Specification (Draft v0.1)

> **One format for proving what an agent did.** Axiom-Grid's reference implementation — the specification is the category-defining artifact for verifiable agent actions.

**Status:** Draft v0.1 · **License:** MIT · **Date:** 2026-09-29

## Why this exists

Grok Bot, OpenBot, and the agent-computer wave give every agent a computer — but **none of them can prove what the agent did**. Audit logs are tamperable. Vendor claims are unverifiable. The Open Agent Receipt is a cryptographic, cite-grounded, verifiable record of an agent action.

## The receipt chain

```
agent action
  └─ canonical event (JSON)
       ├─ sha256 hash
       ├─ Ed25519 sign (agent key)
       ├─ Merkle chain link (prev hash + nonce)
       └─ citation index (page/line refs into source docs)
            → verify: hash ✓  signature ✓  chain ✓  citations ✓
```

## Event schema (v0.1)

| Field | Type | Required | Meaning |
|---|---|---|---|
| `version` | int | ✓ | spec version (1) |
| `ts` | RFC3339 | ✓ | action time |
| `agent_id` | string | ✓ | caller identity |
| `action` | string | ✓ | `read`, `suggest`, `verify`, `export` |
| `doc_sha256` | string | ✓ | input document hash |
| `citations` | [{page, line}] | ✓ | grounded refs into the doc |
| `prev_hash` | string | ✓ | Merkle chain predecessor |
| `nonce` | string | ✓ | chain uniqueness |
| `sig` | base64(Ed25519) | ✓ | signature over canonical bytes |
| `sealed` | bool | ✓ | no network egress during action |

## Verification algorithm

1. Recompute `sha256` over the canonical event bytes.
2. Verify `sig` with the agent's public key (Ed25519).
3. Walk the Merkle chain (`prev_hash` links) to a trusted anchor.
4. Check `sealed=false` → confirm network policy log shows zero egress.
5. If all four hold → `axiom verify` prints `OK <chain-depth> <anchor>`.

## Reference implementation

- `axiom verify <session>` — CLI verifier (this repo)
- `axiom receipts export` — export a session's receipt chain as JSON
- Receipt files: `receipts.jsonl` alongside every pipeline output

## Integration surface (proposed)

- **OpenBot**: bot actions emit receipts via a sidecar adapter
- **browser-use / Skyvern**: verifier adapter for computer-use agents
- **Comet Opik / Helicone**: trace → receipt export bridge
- **OTel**: "signed agent-action spans" semantic convention proposal

## Conformance

A receipt is conformant if a third-party verifier (any implementation) can validate
hash, signature, chain, and citations against the public anchor without vendor
cooperation. Axiom-Grid's `axiom verify` is the reference verifier.

---
*Open an issue to propose changes. AI-generated code and docs are permitted and encouraged under MIT.*
