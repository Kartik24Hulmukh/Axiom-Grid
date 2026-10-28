# Target-device information and qualification

## Opt-in profile report — not a doctor pass

The next release decision needs the **actual intended authorized device and task**. The stdlib-only collector provides a small, inspectable report; it does not start Axiom, contact a backend, run a model, enumerate applications/processes, inspect GPU drivers, download anything, or decide whether a machine is suitable.

Run from the Axiom source checkout on that device with Python 3:

```bash
python3 -B scripts/collect_device_profile.py
```

On Windows, use the available Python 3 launcher/interpreter, for example:

```powershell
py -3 -B scripts/collect_device_profile.py
```

Default output is JSON on stdout. To create a private report intentionally in an existing directory:

```bash
python3 -B scripts/collect_device_profile.py --output device-profile.json
```

A private same-parent temporary file is written and closed before exclusive hard-link publication. Existing destinations and final-component symlinks are refused; parent directories are not created. This requires hard-link support and a trusted, stable parent directory; unsupported filesystems fail closed. There is no crash-durability guarantee. Write/close/link failures do not publish a partial final report. A cleanup failure can leave a private temporary file, or a complete destination if linking already succeeded; a nonzero exit is still a failure, not approval based on file existence. POSIX creation requests mode `0600`; this is not a claim about Windows ACLs, trusted parent directories, or safe storage in a shared/synchronized directory. Use a private directory you control. No upload occurs. Inspect the JSON before voluntarily sharing it; OS/build/CPU/memory metadata can still be identifying in combination. Shell redirection has the shell's overwrite/permission behavior, not the collector's exclusive-create protection.

Optional fields are just your claims, not probes or independently approved configuration. Model names require 1–256 ASCII graphic characters with no whitespace; backend versions require bounded trimmed printable text. Argument admission is capped before parsing (16 tokens, 1,024 UTF-8 bytes per token, 4,096 total):

```bash
python3 -B scripts/collect_device_profile.py \
  --model-name 'your-exact-model-tag' \
  --backend-version 'your-exact-backend-version'
```

Do not put tokens, passwords, private paths or API keys in those arguments. The tool does not choose an approved model or validate a digest. Independently qualify the exact backend and weights under [MODEL_IDENTITY_POLICY.md](MODEL_IDENTITY_POLICY.md); copying a reported inventory digest is not approval.

## Reported and unknown fields

- Basic OS family plus release/machine when available through the bounded supported API path. No hostname/user/IP/path/environment dump is included.
- Logical CPU count, not affinity/quota-adjusted usable capacity.
- Linux host-visible physical memory from a bounded `/proc/meminfo` read, with validated `sysconf` fallback. Other platforms can report this as unknown; no external command is invoked to fill it.
- Cgroup memory limits deliberately remain **unknown / not_resolved**. Container memory entitlement, ancestor limits and available RAM are not established.
- Optional operator-reported model name/backend version explicitly labeled **not verified**.

Every report retains `scope: device-profile-only`, `production_qualified: false`, and `readiness`, `real_model`, `native`, `offline` checks as `not_tested`. Unknown measurements are not passing values. There is no hardware minimum, capacity score, GPU/model-compatibility verdict, authenticity claim or production status. The report does not contain an Axiom build/revision attestation or independently observed model identity.

## What to supply next

After inspecting the report, provide the target OS, CPU/RAM, relevant GPU/VRAM details if known, exact independently approved model/backend versions, and one representative permitted task. State whether this is a personal or IT-managed device. Do not send private device identifiers or credentials. No collector extension that enumerates hardware, calls commands or contacts services is authorized by this document.

## Separate acceptance work — still pending

1. Build/install the approved artifact on the named target profile; observe actual window behavior, authentication/pairing, explicit input, Unicode, manual copy and failure states.
2. Provision independently approved assets and private credentials; verify build/model/dependency rights and reported-identity enforcement.
3. Test cold disconnected start, missing files/models, backend failures, long output, cancel, quit and resource release. A cancel response does not prove backend compute stopped.
4. Observe network behavior with a controlled boundary; qualify the backend as well as the client. Loopback/report consistency is not offline proof or weight attestation.
5. Inspect retention/logs/session separation and platform upgrade, rollback and uninstall. Keep bundling disabled until installer gates pass.
6. Run consent-based task trials including correction and recovery cost. Neither this metadata report nor a green CI run establishes customer value or production readiness.

See [AUTHORIZED_PREVIEW.md](AUTHORIZED_PREVIEW.md), [RELEASE_QUALIFICATION.md](RELEASE_QUALIFICATION.md) and [INTEGRATION_DECISIONS.md](INTEGRATION_DECISIONS.md).
