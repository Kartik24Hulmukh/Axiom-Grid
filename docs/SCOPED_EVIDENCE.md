# Credential-scoped evidence and human review

Engineering preview, not a multi-account SaaS or distributed-store certification.

## Actual workflow

1. Configure **rotated** deployment keys through `AXIOM_API_KEYS` and set `AXIOM_REQUIRE_AUTH=1`. Use HTTPS outside localhost. A key is a credential namespace, not a person/team identity; people sharing a key share its records. Keys are held in browser tab memory only.
2. Upload `.txt`, `.md`, `.pdf`, `.docx` or `.pptx` through the actual upload control or `POST /api/documents?filename=...` with a binary body. File support still depends on installed parser dependencies. The API creates an app-managed copy, not a write into the original desktop file. A filename selects a supported extension; it cannot select a filesystem path.
3. Pass the opaque `uploaded:<uuid>` reference to `/demo`, `/api/extract-document` or `/api/ask-document`. Authenticated credentials may otherwise read only curated public fixtures. Private repository/temp/state paths and another credential's uploads are denied.
4. Source links resolve to complete immutable retained document/chunk/extraction graphs. SQLite WAL supports multiple local worker processes sharing **one local volume** and process restart. Independent nodes, network filesystems, storage replication and host failure are not certified.
5. `/correct` validates the owned extraction and field, original/current value and optional `expected_revision`. Unknown or expired IDs return 404; stale/wrong-field updates return 409. `/api/reviews/{ext_id}` reloads current value/revision for explicit human retry. A correction never changes the original source or extraction observation, and is **not automatically re-grounded**.
6. Exact-original-value reviews from the same credential can calibrate future quality-gate confidence, with at most five matching reviews. This is conservative confidence feedback, not fine-tuning or model execution proof.

## Bounds and lifecycle

- Streaming body ceiling: 2 MiB by default. Binary containers are separately subject to parser resource guards; use `AXIOM_EXTRACTION_ISOLATION=process` for killable parsing where supported.
- Admission: bounded native worker slots plus at most 192 pending waiters / 96 per credential **per event loop**. Round-robin tenant waiting does not bypass already queued callers. An actual receive-side disconnect removes waiting work; a running native worker retains its permit until completion. Bounded saturation still returns 503; a deadline returns 504. No operational guarantee is obtained by changing these error codes.
- Complete snapshots: at most 128 retained graphs per credential, 16 MiB per graph and 64 MiB serialized graph budget. Source API availability is at most one hour; graph-count/byte eviction may make a link unavailable earlier. Closed unresolved refusals are retained without invented source edges and are never rendered as facts. Publication atomically installs the graph and entity index, then evicts completed snapshots only.
- Upload copies: at most 128 and 64 MiB per credential. API access expires after one hour. Physical expired-copy cleanup is deferred to the next upload; inactive credentials require operator cleanup. Startup, serialized with publishers, removes orphaned UUID upload copies left without committed metadata. Database/WAL overhead is **not** included in serialized quotas.
- Review payloads: 8 MiB logical UTF-8 byte quota per credential, including corrected values, reasons and copied original values. Over-budget mutation fails atomically with 413. Review state is latest-value CAS, **not an append-only audit log**.
- Local database files and uploaded copies use mode 0600 on tested Linux; owned directories use 0700. At-rest encryption is not installed. Operators must secure the volume and backups. Key rotation creates a different namespace; no silent reassignment of old/unscoped data occurs.
- Shutdown joins workers before closing all durable stores. Readiness checks durable connections in addition to parser/state/capacity checks. No long-soak, zero-leak theorem or arbitrary native-thread kill claim is made.

## Explicitly unavailable in authenticated mode

Legacy global knowledge-graph, figure, evaluation and compression aggregates return 501 instead of exposing shared state. Legacy rendered-image paths return 404. Per-credential completed trace snapshots are available; they are not fabricated full OpenTelemetry spans. A native desktop writer and independent read-back adapter remain unavailable: applying proposals fails closed.

These gaps, loaded wire latency, independent CI/deployment, rotated credentials, model quality/catalog checks, production collector receipt, supported-platform releases and consented real-human trials keep GA and auto-merge gated.
