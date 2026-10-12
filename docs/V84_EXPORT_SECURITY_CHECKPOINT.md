# Axiom-Grid V8.4 — exported-HTML security hardening, launch NO-GO

## Scope and decision

Continuation from local9a6ce8b / published406e0c0, complete shared treef405540d. Parent used the exporter source's one remaining revision (4→5), after an independent read-only sink review and actual baseline. The old child implementation lane remains2/2 frozen. Server, diagnostics, strict gate, PDF engine and installer ceilings remain frozen; no cap exception was inferred from broad delegation.

Only KPX exporter and its already-enforced contract test change in the runtime candidate. No dependency, engine, parser, model, provider, auth, admission, threshold, workload producer or workflow changed. Documentation is a separate follow-up. The existing draft PR33 is the only publication target; main must remain unchanged while required load bounds fail.

## Actual vulnerability and correction

Real PromptShield accepted the harmless script-marker inputs. Actual KPX HTML files were rendered by an isolated local Chromium context with all network requests aborted, fresh pages and no user/profile/provider state. Seven cases executed a marker before the fix: metadata-title breakout, paragraph, heading, list, quote, fenced code and inline code. This establishes local scripting-enabled artifact rendering behavior, not credential theft, origin reach or every real file-opening environment.

The identical eight-case browser replay (seven hostile plus benign control) after context-specific encoding produced **zero executed markers and zero script elements**. Benign Unicode/title/heading/quote/code/bold output remains. The metadata title is escaped in its title text context; seven converter user-text emission sites are escaped AFTER original line-prefix recognition and BEFORE fixed inline-format wrappers. Raw HTML now intentionally displays as literal text rather than executable markup. This is not a complete CommonMark/parser rewrite or universal sanitizer guarantee.

The separate EPUB chapter-heading h1 is explicitly escaped in the same source revision. This expression/shared-converter protection has **source/structural evidence only**: real successful EPUB generation, EbookLib navigation/metadata handling and legal distribution remain unverified/unavailable in the default profile. The actual missing-EbookLib failure/no-fake-EPUB tests stay intact.

Malformed scanner results no longer infer safety through missing-field defaults/truthiness. A pure validator requires dictionary, built-in Boolean decision, list of string patterns and no contradictory safe=True/nonempty pattern list; invalid schema raises a fixed RuntimeError without logging arbitrary response content. Valid real scanner behavior is preserved, including actual detected-injection denial. The adapter applies this validator to the actual PromptShield result.

## Evidence qualifications

- Baseline regression:2 failed/3 passed. HTML failure is an actual artifact vulnerability. The second failure is absence of the newly proposed validator, NOT a real scanner emitting malformed data.
- Candidate narrow scope:8 passed, fatal resource/unraisable warnings; original real four-format positives, missing-security and missing-EPUB boundaries retained.
- New HTML contract executes10 actual hostile exports with real PromptShield plus benign structure/text assertions.
-17 malformed/inconsistent response cases are **pure negative schema fixtures**, not engine/scanner substitutions or observed real scanner emissions. Adapter AST wiring and real scanner empty/benign/injection controls separately pass. No end-to-end malformed-scanner export_all claim.
- Independent read-only review found no scoped blocking source issue; exact reviewed source/test checksums retained. It did not rerun parent tests/browser and is not deployment certification.
- Strict unchanged gate:670 pytest passes,44 subtests, plus3 genuine absent-engine PDF-profile checks; lint/compile passed. One Starlette deprecation warning retained. Counts overlap other suites.
- Initial browser package-location failure retained; reused already-installed pinned Playwright/Chromium after correcting the external harness. No downloads, package upgrades or third-party modifications.

## Remaining launch gates — unchanged

This is an exporter security correction, **not a latency fix**. V8.3 unchanged full producers each executed100 clients/120 scripted identities/4,500 timed requests: HTTPX worst persona error4098.083ms, Node354.499ms, both violating<200ms. Those are historical V8.3 observations, NOT rerun measurements on V8.4. Original two pooled header-read losses remain causally unresolved. Previous remote V8.3 load job failed both producer steps, despite8 other successful jobs.

No retry-until-green, relaxed gate, speculative server change, auto-merge, main rewrite, deployment or live-provider call. Exposed historical/main/chat credentials still require owner revocation/audit; no secret values used/tested. Required training assets, rotated live gateway endpoint/model/quotas, signed clean-host/platform builds, legal/transitive distribution profiles, broader IAM/key custody/retention/backup/rollback, deployment/soak and consented real-human/customer evidence remain open. Scripted personas are not recruited humans; no traction or100x improvement claim.

Changed-source scanner0findings. Full tracked scan retains13 identical previous reviewed rule/path/line findings, exit1; no allowlist/suppression/clean-scan claim. This does not prove historical credential revocation.

## Final validation/publication

Runtime candidate commit `e6e3193d4ea29c3616ca33c26e269669d5a0c52a`. Expanded identical offline scope: **1,891 passed,2 unchanged skips,44 subtests**, under fatal resource/unraisable warnings; retained Starlette deprecation warning. Missing training asset/cross-platform workflow skips remain, and this is not clean-host/platform evidence. Generated benchmark/release outputs were preserved and deliberately excluded. Initial cleanup restored three strict-generated paths, then its scope assertion exposed additional expanded-suite generated outputs; that housekeeping failure is retained. All25 additional tracked generated reports and one new generated history report were then preserved and restored/removed by explicit path. No benchmark improvement is committed. Independent reviewed checksums match the committed source/test. Final remote snapshot/CI remain pending publication; keep draft/main unchanged until unchanged release criteria pass.
