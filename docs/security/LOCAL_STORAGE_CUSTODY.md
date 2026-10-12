# Local storage custody and retention — operator gate

This checkpoint hardens local `EvidenceStore` and `DocumentStore` filesystem and
schema boundaries. It is **not** application encryption, individual-user IAM,
distributed storage, immutable audit storage, or certified data erasure. Sensitive
paid intake and GA remain NO-GO until the separate operator/security gates close.

## Supported custody boundary

- POSIX, one local filesystem, one dedicated service UID. Every containing path
  must be a real directory owned by the service UID or root. Non-sticky ancestors
  writable by other users are refused; a sticky system temporary ancestor is
  allowed, but the actual state root cannot be shared/writable by other users.
- Store roots/namespaces become mode `0700`; existing roots must already be owned
  by the service UID and not group/other writable. Symlinked path components are
  refused, not silently canonicalized. Do not configure a symlinked state root.
- Database, WAL, SHM and rollback-journal files are checked before adoption and
  at startup/readiness: regular files, service owner, one hard link, no group/other
  write permission, mode `0600`. New DB/upload files are private at creation,
  without a process-global umask change. Upload targets are rechecked before
  resolve, quota accounting, recovery and purge; namespace symlinks are refused.
- Other host processes running as the **same UID**, root, ACL overrides, malicious
  mounts, network filesystems, filesystem corruption and compromised runtime code
  are not an isolation boundary. SQLite opens paths internally; these checks do
  not constitute a race-proof vault against a hostile same-UID process. Returned
  upload paths still require a trusted host until parsing completes.
- Fix custody offline with intake stopped and owner approval. Do not automatically
  chmod a symlink victim, adopt a hardlinked database, or reinterpret an untrusted
  state directory to make readiness pass.

## Schema, source and tenant integrity

Startup/readiness validate required columns/types, composite primary keys,
foreign-key cascade declarations, SQLite quick-check and foreign-key integrity.
Unknown/incomplete schemas are refused. The existing two optional review columns
are still migrated additively, under the same `BEGIN IMMEDIATE` transaction as
schema inspection and creation. Errors are surfaced, never converted into empty
success responses. Successful schema validation is not cryptographic provenance.

Evidence reads validate payload byte count, expected graph shape, dataclass/enum
reconstruction, requested document ID and source/entity edges. Upload reads and
same-tenant quota accounting validate IDs, allowed suffixes, positive bounded
byte counts, finite creation time and actual copy size; missing live copies fail
closed. There is no persisted upload content hash/authenticated MAC, so equal-size
host-side tampering is not detected by these checks. No automatic repair/import
of unscoped data is added.

Tenant predicates remain in SQL and reviews remain a separate mutable table:
`BEGIN IMMEDIATE` serializes revision CAS across independent local processes.
A deployment-credential hash is a namespace, **not an independently authenticated
person**. Sharing a deployment key shares its records. Keep the original
observation separate from the human-provided review. Rotation changes namespace;
verified administrative migration and identity/role management remain unshipped.

## TTL: API denial versus deletion versus erasure

1. Reads deny expired records using the configured TTL (default one hour).
2. `purge_expired()` removes expired evidence graphs with entity/review cascade,
   and unlinks expired upload copies plus metadata for **all tenants**, including
   inactive tenants. Reopen, readiness healthchecks and successful publications/
   saves also perform all-tenant expiry cleanup. Purge shares the SQLite writer
   lock with concurrent publishers; reopening still recovers uncommitted upload
   orphans without deleting committed copies.
3. **No background timer is added.** A completely idle/stopped process will not
   purge itself. Before intake the operator must schedule and monitor both stores'
   maintenance/readiness activity, agree a maximum cleanup delay and demonstrate
   expiry across inactive tenants on the intended host. No wall-clock eventual
   deletion guarantee is shipped merely by exposing a purge function.
4. SQLite deletion/unlink is **not forensic erasure**. Plaintext may remain in DB
   free pages, WAL/journal, snapshots, backups, open descriptors, filesystem/media
   history and exported evidence. Checkpoint/vacuum alone is not a universal erase
   proof. Source retention and graph retention are separate inventories; losing an
   upload does not imply all observations/receipts were erased.
5. Upload unlink and metadata commit are not one filesystem transaction. A crash
   can leave stale metadata; expired missing files are reconciled by later purge.
   Failed quota/publication transactions can roll back metadata cleanup after an
   unlink, with expired references still inaccessible. Corrupt metadata refuses
   purge rather than trusting arbitrary deletion paths; escalate, preserve protected
   evidence, and repair only on a consistent copy under operator approval.

## Required before sensitive/paid intake

- Owner-approved dedicated UID, mount/ACL policy, root ownership/mode inventory and
  compatible-version backup/restore rehearsal that includes SQLite WAL consistency.
- Encryption requirements decided explicitly. There is **no app-level encryption**
  here, no key lifecycle/KMS integration and no WAL encryption. If encrypted host
  storage is required, operator must independently verify volume/backup/export
  coverage, key custody/rotation/recovery and threat assumptions; do not label this
  patch an encrypted vault.
- Individually authenticated reviewer/role/IAM requirements accepted as unavailable
  or implemented and separately tested; deployment credentials never stand in for
  distinct humans. Credential revocation and namespace recovery plans approved.
- Monitored TTL maintenance, legal holds, consistent backups, backup/export
  retention, purge-failure alerting and buyer acknowledgement of non-erased copies.
- Evaluate readiness integrity scans and all-tenant maintenance under the approved
  bounded workload before launch. These focused tests establish no performance
  SLO, multi-node HA, production data-erasure proof, or regulatory compliance.

No new dependency, catalog integration, live credential, provider request,
cryptographic spend, production deployment or human/customer trial is required
or asserted by this checkpoint. `repos.md` was reviewed; none of its candidate
catalog tools closes the filesystem attacks better than existing POSIX/SQLite
primitives and pinned local pytest/ruff. Do not install a crypto abstraction merely
to rename an unresolved encryption/key-management gate.
