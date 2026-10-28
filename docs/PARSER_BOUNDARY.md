# Single-parse document extraction boundary

**Profile:** `/api/extract-document`, with `/api/ask-document` delegating to it.
**Not:** the whole Python service, an OS sandbox, real-model E2E or production certification.

## Data flow

1. Existing request admission acquires capacity before path resolution/read/parse.
2. Resolve an allowed source, open the final component with POSIX no-follow and
   nonblocking protections, fstat a regular file, and capture bounded bytes once.
   This does not prevent every ancestor-directory race or same-account compromise.
3. Pass that immutable capture to `ingest_document_isolated(filepath, timeout,
   content=...)`. The function creates a private snapshot preserving the suffix;
   the child hashes and parses that snapshot, not the mutable original path.
4. One spawned child applies resource limits before parser work and publishes a
   bounded JSON result. There is no child-controlled pickle/Queue receive or
   join-before-drain pipe-feeder deadlock. Parent checks child exit, then opens a
   bounded no-follow/nonblocking regular result file and validates its JSON graph.
5. The original source path is restored as metadata. Validated IDs, hash, pages,
   geometry, text, timestamps and embeddings are retained. Classification and the
   orchestrator read the SAME captured graph through a copying in-memory adapter;
   neither invokes the parent parser in process mode.
6. The actual ingested document ID is used in response/source-link construction.
   Request-local memory/provenance remain request-local. A consistent ID is NOT
   proof that a future source endpoint can retrieve the original document/evidence.

Public full-result API:

```python
from kernel.sidecar.isolated_ingest import ingest_document_isolated

chunks, document, pages = ingest_document_isolated(
    original_path, timeout=10.0, content=already_bounded_bytes
)
```

The compatibility `ingest_isolated(path, timeout)` returns only chunk text. Do not
use that lossy wrapper and then reopen/reparse the document to recover provenance.
Without `content`, the full API performs its own bounded regular-file capture.

## Modes, supported inputs and failure behavior

- `AXIOM_EXTRACTION_ISOLATION=process` is the default. Exactly `thread` explicitly
  selects trusted-development mode; other values fail. Both modes snapshot once
  and validate the same result contract. Thread mode has no killable CPU/memory
  boundary and can hold its worker indefinitely; never market it as containment.
- Supported suffixes remain `.txt`, `.md`, `.pdf`, `.docx`; no new format claims.
- Process prerequisites are POSIX safe-open primitives, process groups and resource
  limits. Unsupported platforms/settings fail closed, not to parent/thread parsing.
  This is NOT new Windows support. Address-space limits are `RLIMIT_AS`, not
  measured resident-memory guarantees. Native parser/library coverage is separate.
- HTTP admission saturation is 503, original-byte excess 413, missing source 404,
  parser/config/format/resource rejection 422 and parsing deadline 504. Existing
  pipeline/gate behavior is otherwise retained; not every empty/blocked document
  is promised a successful useful extraction.
- Queue wait subtracts from the child budget. The HTTP waiter can still finish
  before actual work ends; capacity belongs to the worker and is released only
  when work really completes. Post-parse classification/pack work is not newly
  killable. Filesystem/process creation and kernel-uninterruptible I/O cannot be
  given a universal Python deadline guarantee.

## Hard ceilings and configurable lower budgets

| Setting | Default / maximum |
| --- | --- |
| `AXIOM_INGEST_MAX_INPUT_BYTES` | 32 MiB; server's default 2 MiB upload budget is tighter |
| `AXIOM_INGEST_MAX_OUTPUT_BYTES` | 32 MiB exact serialized JSON budget |
| `AXIOM_INGEST_MAX_CHUNKS` | 20,000 |
| `AXIOM_INGEST_MAX_PAGES` | 10,000; parser-specific PDF default is separately 200 |
| `AXIOM_MAX_EXTRACTED_CHARS` | 4 Mi characters total; output-byte cap applies as well |
| `AXIOM_INGEST_CPU_SECONDS` | 120 default, 86,400 hard ceiling |
| `AXIOM_INGEST_RSS_BYTES` (legacy name) | 2 GiB address-space default, 16 GiB hard ceiling |

Budgets must be positive ASCII decimal integers within hard ceilings; malformed
operator configuration does not silently disable limits. Per-chunk embeddings
are bounded to 4,096 finite numeric values. Accepted graph IDs are bounded ASCII
letters/digits/underscore/hyphen; URL query/fragment/control characters are rejected.
Graph validation rejects duplicate/unknown JSON keys, nonfinite/overflow numbers,
wrong primitive types, foreign document references, duplicate IDs/pages, invalid
page counts/dimensions, malformed hashes/timestamps, nonnormalized/reversed geometry,
excess text and mismatched snapshot identity/digest. No arbitrary class construction
or exception deserialization is used. A parser-controlled graph is still a claim
about source content, not independent proof of semantic correctness.

## Threat boundary and residual risks

The child runs as the service user with that user's filesystem/network privileges.
A compromised parser is NOT contained by a seccomp/container/VM policy in this
patch; it could use those privileges. The parent has not independently reproduced
semantic parsing. Private temp files are not secure erasure or malicious same-user
protection. Process-group cleanup handles ordinary child-group descendants, but a
malicious descendant can create a new session; no all-descendant/no-egress guarantee
is made. Operating-system credential/filesystem/network isolation is still needed
before hostile/sensitive-document intake qualification.

Legacy demo/figure/document services and source retrieval are separate surfaces.
Do not infer all endpoints or all transitive code use this boundary. Authentication,
tenant/storage policy, retention, durable evidence retrieval, independent security
review and production workload measurements remain release gates.

## Premortem and countermeasures

| Failure | Implemented countermeasure | Remaining validation |
| --- | --- | --- |
| Parent reparses malicious original after child returns | One capture/one child parse, in-memory graph reuse; parent-parser-forbidden tests | Audit every other ingestion route |
| Path swapped to FIFO/symlink after resolution | Nonblocking/no-follow open, fstat, race regressions | Anchored path/OS sandbox design and local adversary review |
| Large child response deadlocks an IPC feeder | Bounded atomic JSON result file; real 1 MiB result test | Host disk exhaustion and malicious-code privilege policy |
| Malformed graph corrupts provenance or source links | Strict graph/ID/type/hash/reference validation | Durable source retrieval and independent effect semantics |
| Hung parser or invalid limit configuration consumes capacity | Resource setup before parse, process cleanup, actual hung-child and failure tests | Native pathological corpus/OS load and descendant-escape review |
| Cancellation frees capacity for still-running work | Worker-owned slot; running/queued-cancel and submit-failure regressions | Post-parse worst-case CPU and production SLO qualification |
| Probe passes malformed model/cancel output and overclaims locality | Strict HTTP body/identity consistency, explicit unverified-locality fields | Real approved model/native/network/termination evidence |

Run `python scripts/run_assurance_checks.py --document-service` in the pinned test
environment. See CONTINUATION_VERDICT.md for actual results, including failed broad
checks; test source and a configured CI job are not proof of a deployed system.
