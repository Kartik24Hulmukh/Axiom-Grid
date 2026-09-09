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

Packaging infrastructure exists:

| Platform | Script | Output |
|---|---|---|
| Linux | `scripts/package-linux.sh` | `.AppImage` + `.deb` |
| macOS/Linux | `install.sh` | `~/.kairo-phantom/` |
| Windows | `install.ps1` | PowerShell installer |
| Cross-platform | `phantom-core/src-tauri/tauri.conf.json` | Tauri bundle (`.dmg`, `.deb`, `.msi`) |

### Build commands

```bash
# Linux .AppImage + .deb
./scripts/package-linux.sh

# Tauri bundle (all platforms)
cd phantom-core && cargo tauri build

# Python install
python install.py
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

**What's ready:** The build scripts and Tauri config are in place. Once signing certificates are provided, the build produces signed installers with no code changes needed.

**What ships unsigned:** The `.AppImage` (Linux) and unsigned `.dmg`/`.msi` can be built now. Users on Linux can install without signing. macOS/Windows users will see a "unidentified developer" warning until signed builds are available.

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
| Installer build scripts | ✅ Ready (install.sh, package-linux.sh, Tauri) |
| Signed installers | INFRA-PENDING (5 missing secrets listed) |
| Tauri bundle config | ✅ Ready |