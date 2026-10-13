# T6 — Packaging Status

## Migration Test: ✅ PASS

The migration test verifies that the blind corpus is content-addressed and immutable across versions:

```
Checksum verification: 241 passed, 0 failed
Exit code: 0
```

This proves upgrading Kairo does not change the corpus or its checksums — the blind number means the same thing across versions.

Receipt: `receipts/packaging.txt`

---

## Installer Build Path

**Historical packaging notes, not current installer attestation.** The root scripts now use the [reviewed local developer workflow](../LOCAL_INSTALL.md). Linux Python setup needs an existing reviewed wheelhouse and a fresh destination; local Rust installation needs an existing cached toolchain. Windows/macOS automated installation is blocked. No signed artifacts or clean-host verification are established here.

Inherited packaging infrastructure:

| Platform | Script | Output |
|---|---|---|
| Linux | `scripts/package-linux.sh` | `.AppImage` + `.deb` |
| Linux developer only | `install.sh` | Explicit fresh private Python environment |
| Windows (unverified) | `install.ps1` | Nonzero refusal; no installation |
| Cross-platform | `phantom-core/src-tauri/tauri.conf.json` | Tauri bundle (`.dmg`, `.deb`, `.msi`) |

### Build commands

```bash
# Linux .AppImage + .deb
./scripts/package-linux.sh

# Tauri bundle (all platforms)
cd phantom-core && cargo tauri build

# Root installer commands: see ../LOCAL_INSTALL.md for prerequisites/flags.
# install.py without an explicit local mode and destination fails closed.
```

---

## Signing: INFRA-PENDING

**Status: INFRA-PENDING**

Signed installers require code-signing certificates that are not available in this build environment:

| Platform | Missing Secret | Purpose |
|---|---|---|
| macOS | Apple Developer ID Application certificate + notarization credentials | `.dmg` signing + notarization |
| Windows | Authenticode code-signing certificate (EV or OV) | `.msi` signing |
| Linux | GPG signing key (optional) | `.deb` / `.AppImage` signature |

**Exact missing secrets:**
1. `APPLE_DEVELOPER_ID_CERT` — Apple Developer ID Application certificate (P12 format)
2. `APPLE_NOTARIZATION_APPLE_ID` — Apple ID for notarization
3. `APPLE_NOTARIZATION_PASSWORD` — App-specific password for notarization
4. `WINDOWS_AUTHENTICODE_CERT` — Authenticode code-signing certificate (PFX format)
5. `WINDOWS_AUTHENTICODE_PASSWORD` — Certificate password

**Historical infrastructure only:** Build scripts and Tauri configuration do not demonstrate signing, notarization or clean-host installation. Certificates alone do not prove a working signed release; actual packaging and verification gates remain open.

**No release attestation:** This review did not build or test `.AppImage`, `.dmg` or `.msi` artifacts. Do not infer that unsigned binaries are safe, installable or supported from these notes.

---

## Tauri Configuration

```json
{
  "package": {
    "productName": "Kairo Phantom",
    "version": "1.0.0"
  },
  "tauri": {
    "bundle": {
      "active": true,
      "category": "DeveloperTool",
      "targets": ["appimage", "deb", "dmg", "msi"]
    }
  }
}
```

The overlay is a thin Tauri renderer — the CLI is the real product. The overlay provides click-to-source navigation and visual bbox display.

---

## Summary

| Item | Status |
|---|---|
| Migration test (checksums) | ✅ PASS (241/241) |
| Root installers | Reviewed offline Linux developer path only; clean-host gates open |
| Signed installers | INFRA-PENDING (5 missing secrets listed) |
| Tauri bundle config | ✅ Ready |