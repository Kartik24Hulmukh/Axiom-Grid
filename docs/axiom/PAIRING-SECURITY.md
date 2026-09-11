# IPC pairing security and recovery

## Supported boundary

Unix file pairing uses one implementation in the runtime and native overlay.
Every directory component is opened relative to an already-open descriptor with
`O_NOFOLLOW | O_DIRECTORY`. The final directory must belong to the effective
user and have mode 0700. Existing directories are **never chmodded** by startup.
The token must be a mode-0600, owner-matching, single-link regular file of exactly
64 hexadecimal bytes. Symlinks, hardlinks, FIFOs, malformed and oversized files
fail closed. Readers apply the same checks as creators.

Startup locks the private directory with nonblocking `flock`, with a two-second
retry budget. First-time creation writes a random mode-0600 temporary file,
fsyncs it, renames it atomically and fsyncs the directory. Cooperating processes
cannot observe partial credentials or publish different tokens. The lock is
released automatically on descriptor close or process exit. A crash before
rename can leave a private `.ipc-*.tmp` orphan; it is never treated as a token.
The random temporary name is independent of the credential.

Use a private directory on a local Unix filesystem supporting directory flock
and fsync. Network filesystem semantics have not been qualified. Symlinked home
or configuration paths must be replaced with a direct physical path via
`AXIOM_PAIRING_FILE`; this is intentional fail-closed compatibility behavior.
Untrusted users must not control/rename the selected directory's ancestors.

This is not isolation from malware already running as the same user, root, or a
compromised model daemon. File permissions cannot defend against those actors.
Windows automatic file pairing remains unsupported and now explicitly fails
closed rather than implying Unix permissions protect a Windows file. A separate
valid 64-hex `AXIOM_API_TOKEN` override remains available; secure Windows storage
and native lifecycle validation are still release blockers.

## Intentional behavior change

Permissive or corrupt existing credentials are rejected, not silently tightened
or replaced. A token that was readable by others may already be disclosed;
chmod alone cannot make that credential safe. Automatic replacement also risks
splitting the credentials held by an already-running runtime and overlay.

## Explicit rotation / recovery

1. Stop **all** Axiom runtime and overlay processes. Verify port 7437 is closed.
2. Resolve the actual configured pairing path. Inspect it and its ancestors;
   do not follow a suspicious symlink or recursively change shared permissions.
3. Remove the suspect token entry. Repair or create a dedicated directory owned
   by the current user with mode 0700. For a compromised path, select a new
   private physical directory instead. Remove private orphan temporary files
   only while all consumers are stopped. Investigate any disclosure first.
4. Remove any old `AXIOM_API_TOKEN` override from both processes. Start the runtime
   to create a new token, then the overlay to read the same token. Never print it.
5. Confirm authenticated readiness succeeds; old tokens must return HTTP 401.

No hot rotation API is provided: live rotation needs coordinated revocation and
consumer refresh semantics before it can be safe. Signed deployment, OS keychain
storage and automated rotation UX remain backlog items.

## Runtime shutdown

SIGINT and Unix SIGTERM stop accepting connections and allow at most five seconds
of graceful draining. Remaining connections are closed by process teardown.
This deliberately bounds shutdown even for partial request bodies. A signal is
not a guarantee that an external model daemon immediately stops internal work.
The integration test exercises actual processes and sockets, including a stalled
body; it requires local port 7437 to be available.
