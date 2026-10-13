# Gateway operator preflight — offline / fail closed

This is a **zero-dispatch gate**, not a provider connector or launch approval.
No router/runtime changes. No dependencies. Unknown provider endpoint, ownership,
quota/error billing and hard monetary controls prohibit live operation. The
historical default base URL and model labels are not evidence of provider support.
`repos.md` contains historical live-verification claims; they are **not accepted**
as fresh evidence. GLM-5.3/Kimi K3 labels remain unverified; no model-era facts are
claimed here.

## Run privately

Configure `MELIOUS_BASE_URL`, `MELIOUS_API_KEY`, `MELIOUS_MODELS`,
`MELIOUS_TOKEN_CEILING` and `MELIOUS_PREFLIGHT_ALLOWED_ORIGINS` in the operator's
private environment or secret manager. Never put keys in chat, CLI arguments,
committed files or a shell transcript. Rotate previously exposed credentials
before any later approved provider use. This utility does not validate rotation.

- No default endpoint, models, origin allowlist or token ceiling is assumed.
- Allowed origins are comma-separated exact HTTPS origins, no paths except `/`,
  credentials, query/fragment, wildcard or non-443 port. This is an operator
  intent check, **not** proof of provider ownership.
- Configured IDs are comma-separated exact ASCII identifiers, no whitespace
  trimming, aliases, inference or silent fallback. Up to 16 unique IDs.
- Local token admission must be 1..10000. This is a conservative **preflight
  policy**, not the router's maximum or a provider monetary cap.
- Ambient proxy settings gate review. The existing router's direct `http.client`
  ignores proxies and rejects redirects; no unaudited proxy mode is offered.

```sh
python scripts/gateway_operator_preflight.py
python scripts/gateway_operator_preflight.py --catalog-file /private/catalog.json
python scripts/gateway_operator_preflight.py --live
```

All three return exit **2** and a sanitized JSON `BLOCKED` report. `--live` is an
explicit request, **not** a bypass: it records `live_requested_but_refused`.
The utility contains no HTTP client, resolver calls, provider requests, retries,
fallbacks or completion payloads. Call limit **0**, maximum spend attributable
by this script **0**. This is not a cap on other processes or the running router.
It never prints environment values, URLs, IDs, paths, catalog contents or key
material; invalid arguments use a fixed error. Output includes only gate codes,
booleans, mode and fixed zero bounds. It neither writes nor persists secrets.

An optional local catalog must be regular/non-symlink, <=64 KiB JSON, contain a
nonempty unique `data[].id` list and every exact configured ID. Duplicate object
keys are rejected. A matching saved catalog is **offline evidence only**; it
cannot clear freshness, access, ownership, prices or model-quality gates.
No DNS resolves offline. Syntax screening is deliberately not SSRF certification;
DNS/rebinding and nonprovider identity remain unresolved gates.

## Before a separate live adapter can be approved

1. Independently establish provider ownership and the exact official catalog and
   completion endpoints from authoritative provider documentation. Do not infer
   an endpoint from the repository default or install a second gateway.
2. Approve exact origins/IDs; resolve and reject *all* loopback, private, link-local,
   reserved or mixed-public/private targets. Prevent DNS rebinding between check
   and connect; preserve TLS hostname verification and forbid redirects/proxies.
3. Verify provider-enforced monetary/quota controls, pricing and error/unknown
   usage billing. A local token estimate or operator attestation alone is not an
   invoice bound. No completion plan is approved in this phase.
4. Specify the maximum catalog call count and response bytes and an externally
   enforceable process deadline for DNS/TCP/TLS; redact logs and join/kill workers.
5. Require fresh exact catalog IDs and exact returned completion IDs without
   translating aliases. Catalogue presence is not answer-quality certification.

If any fact is unknown, retain `BLOCKED` and do not send a key. This phase does
not research or guess a Melious endpoint, and provides no switch to make API calls.

## Router limitations independently checked

Connected HTTP trickle/header deadlines and explicit cancellation work in the
existing loopback fixtures; fallback after a shorter per-route timeout stays in
the total connected-call budget. Reasoning exhaustion stops fallbacks, billable
rejected attempts consume admission and bounded Retry-After cooldowns avoid
parking a worker. These are local functional tests, not production wire SLOs.

Additional two-call loopback tests confirm redirects are **not** followed and a
successful response with missing usage commits **0** local tokens. Zero here is
unknown billing, not a free response. Rejected HTTP error bodies likewise supply
no usage to the ledger. Thus local admission cannot guarantee a monetary ceiling.

A bounded injected resolver/connect hold confirms explicit cancellation and the
nominal deadline do **not** interrupt pre-watchdog work. This is deterministic
injection, not an actual stalled DNS/TLS experiment. Connected cancellation must
be explicitly passed by the caller; cancelling a running thread Future does not
stop its request. TLS, intended-host behavior, deployed caller wiring and provider
billing controls are not validated by these fixtures.
