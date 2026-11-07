# Exploratory local preview evidence

These are fixed task specifications, outputs and case results from the 2026-11-07 continuation. They are **not** a held-out benchmark or proof of product readiness. Outputs are stored as text to discourage accidental execution. Inspect the complete output before considering execution; the manual scorer described in `scripts/preview-evaluation` executes code and is not a sandbox.

- Linux sandbox, 2 vCPUs, 4.2 GiB RAM, no GPU; Ollama 0.40.13; Qwen2.5-Coder 1.5B Q4_K_M. Reported model manifest SHA-256: `d7372fd828518a4d38b1eb196c673c31a85f2ed302b3d1e406c4c2d1b64a0668`. This is reported identity consistency, not byte attestation.
- Client/runtime comparison: both system prompts passed 15/15 IPv4 and 15/15 HTTP method checks. The IPv4 outputs were identical. The model was cold for the first baseline request and warm afterwards, so elapsed times are not comparable.
- VS Code 1.145.2, freshly installed unsigned development VSIX 0.1.3 SHA-256 `9f99ed6f9d15fa024097607262ff9e76e55c06ba7aa07ddd0e59767a2675744e`, experimental runtime prompt, warm model: 12/12 byte-format cases passed after review. UI results show no edit before Tab, then insertion; preview time 12.2 s. The basic-password-store disposable profile is not credential-security qualification.
- Tasks were selected after prior failed tests. Fixed cases were not sent to the model. No blanket claim follows from one run per task and variant; regression and customer validation remain open.
