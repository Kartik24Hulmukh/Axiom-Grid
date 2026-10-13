# Open Agent Receipt Specification — implementation pointer

The earlier draft at this path was aspirational: its Merkle-chain, every-action,
citation and sealed-proof claims were not an implemented portable format.

Use [Open Receipt Specification v0.1](OPEN_RECEIPTS_V0_1.md) for the actual
experimental schema and verification algorithm. It signs observations using a
linear SHA-256 hash chain and Ed25519 signatures with a signed checkpoint.
Signatures do not certify execution truth, source completeness or zero egress.

Runnable CLI: `python scripts/axiom_receipts.py verify ...`. See
[adapter instructions](../docs/RECEIPT_ADAPTERS.md). Live OpenBot instrumentation,
external ecosystem adoption and independently witnessed execution remain pending.
