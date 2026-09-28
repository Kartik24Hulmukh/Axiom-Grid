# Single-agent council premortem (not independent agents or humans)
1. Product: false launch confidence from broken harness, repeated ten styles, absent valid fixtures. Gate every request and report limitations.
2. Architect: worker starvation and unbounded queue under 100 clients. Exercise real TCP app, saturation and recovery separately; 100 clients is not a demonstrated 100x production baseline.
3. Chaos: malformed JSON/surrogates/abandonment cause exceptions. Keep server stderr, count all errors, require graceful exit.
4. Architect: memory/socket/coroutine growth concealed by endpoint snapshots. Sample RSS/FD/thread counts, warm resources first, never infer no leak from one delta.
5. Founder + security: frontier aliases, fleet spend, credential exposure and red CI. Verify catalog with bounded calls; retain circuit tests; block merge on incomplete suite.

repos.md absent from attached ZIP and recursive repository tree. No catalog-derived integration claimed. Existing telemetry and PDF dependencies used instead. Baseline recorded before source edits: 9 failed/345 passed before PDF dependencies; 360 passed after; original attachment IndexError; full collection 28 errors; Wave11 lint two errors.
