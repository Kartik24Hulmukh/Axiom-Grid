# Service failure checkpoints are diagnostics, not qualification

Main run 41338931756 at merge b4b68a3 identified
`overlay.tests.test_surrogate_encode_zero_day::test_surrogate_burst_100_workers_zero_5xx_and_recovery_slo`
as the sole failed service case (574 tests, 1 failure). Its assertion and root
cause remain unknown without the preserved full-service-results report. Do not
infer a latency failure from the test name or equate this with the earlier
unidentified incident in issue #48.

## Future reports only

The existing test records one owned `axiom_surrogate_burst_phase` property before
each checkpoint: `workload`, `no_5xx`, `health`, `quantiles`, `p50`, and finally
`complete` only after the original assertions finish. Unrelated properties are
preserved. No finally/teardown path overwrites the checkpoint. The 100 workers,
600 requests, timing boundaries, assertions and strict P50 <200 ms threshold are
unchanged. Failure propagation remains authoritative; there are no retries or
new skips. Recording a checkpoint is not a benchmark or reliability pass.

The bounded JUnit reader exposes an optional checkpoint only for the exact raw,
unparameterized module/function identity above, with a direct failure/error
outcome, as a direct testcase child with suite-only ancestry. Duplicate testcase identities, duplicate containers/properties, malformed
structures and values outside the fixed enum omit the optional observation. An
omission is not success. All other property values, assertion messages, payloads,
request bodies, timings, tracebacks and captured output remain excluded.

Counts and safe identities retain their existing bounds. At most one checkpoint
is rendered, with at most 20 combined identity/checkpoint entries and a 16 KiB
rendered-summary cap. The renderer revalidates optional data independently; forged
optional fields are omitted, not echoed. Existing XML byte/testcase limits,
UTF-8/DTD/entity rejection and nonblocking no-follow descriptor reads remain.
These are trusted-repository diagnostic identifiers, not authenticated evidence
or a general secret scanner. Stable trusted parent directories remain required.

## Interpretation and next action

“Last recorded burst phase” means a diagnostic checkpoint, **not the failing
assertion or root-cause verdict**. A later exception or teardown may follow any
checkpoint, including `complete`. A future success cannot explain the historical
failure, and future metadata cannot retroactively annotate an old report.

The original pytest exit, full-service-results artifact and thresholds remain
the gate. For incident closure, inspect the authorized service.xml/service.log,
identify the actual assertion/traceback, establish a targeted reproducer when
possible, and validate a justified correction. Do not repeatedly rerun until green
or weaken the threshold. No production/reliability, native editor, installer,
model-quality, offline or traction approval follows from these diagnostics.
