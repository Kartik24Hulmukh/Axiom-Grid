# Launch decision — NO-GO for a production ghost-typing release

Target dates from the requested September 9, 2026 planning context: Wednesday September 16 or Thursday September 17. Dates are a planning target, not a reason to waive safety gates.

| Gate | Current evidence | Required before claiming production |
|---|---|---|
| Focused runtime compiles and passes tests | Session 012: 25 Rust tests, Clippy, release build; focused CI was green at 25f0caf | Clean-machine CI and platform matrix |
| Preview UI logic | Session 012: 17 Node tests pass; native Linux build/readiness/generation/cancel/recovery smoke passed | Native Tauri build and real keyboard/manual-copy UX |
| Real local model | Session 012: actual Ollama 0.34.0 + qwen2.5:0.5b, 20 synthetic prompts, auth/cancel/recovery; evidence JSON in docs/axiom/evidence | Installed-model end-to-end run on minimum hardware, p50/p95 latency and RAM measurements |
| Safe insertion | Intentionally disabled | Target handle + element identity + selection revision, explicit approval, pre-insertion revalidation, abort on focus change, native undo validation |
| Model onboarding | Explicit configured model, no silent pull | Inventory UI, errors/progress, approved download and license/disk checks |
| Privacy | Fixed loopback client, no proxy/redirect/fallback | OS/network observation on clean machine, audit all model/runtime egress; no cryptographic zero-egress claim |
| Authentication | Unix pairing file 0700/0600 implemented; Windows random generation unsupported; lifecycle/security review still needed | Native-platform pairing, symlink/concurrent-creation hardening, lifecycle/rotation tests |
| Distribution | Bundling disabled | Signed/notarized installer, checksum/SBOM, upgrade/uninstall/rollback tests |
| Extraction | Independent runtime excludes legacy launch surface | Remove unused source and simplify Tauri workspace after native build validates dependencies |
| Market | Hypothesis only | 5–10 target users, observed repeat use, measured time saved and willingness-to-pay interviews |

Launch a limited, clearly labeled design-partner preview only after real-model + native-UI gates pass. Do not promise Word/PPT/Canva/Figma automation until per-app tests demonstrate it. Prefer one OS and two ordinary text editors for the first insertion release. Do not position the product for covert exam assistance.

## Session 012 qualification

Previous session conclusions that there was “no code backlog” were too broad. This
session reproduced and fixed readiness UI races, unconfirmed cancellation messaging,
and acceptance of HTTP redirects containing otherwise-valid model JSON. Inventory
responses are now bounded like generation responses. These are real corrections,
not proof that all other defects have been eliminated.

The real-model smoke suite checks transport, nonempty output and Unicode counts,
not usefulness. The small CPU model made translation/punctuation mistakes. It is a
validation fixture installed explicitly, not an approved production model. Model
license text/digest and raw results are recorded; target-hardware qualification,
human ratings, privacy/network auditing, signed distribution, and partner research
remain open. Automatic insertion remains disabled. Do not merge or label a release
production-ready solely because focused tests pass.
