"""Legacy inventory helpers, NOT a supply-chain or production qualification gate.

The heuristic inventory is incomplete and unpinned. Signing is disabled until an
approved persistent signer and independent verification contract are implemented.
"""
import os
import sys
import json
import logging

log = logging.getLogger("kairo.sbom_gate")


def scan_for_secrets(root_dir: str) -> bool:
    """Scan the repository for hardcoded secrets (mock Gitleaks)."""
    log.info("[SBOM Gate] Running secrets scanning...")
    # Patterns to look for
    secret_keywords = ["AWS_SECRET_ACCESS_KEY", "DATABASE_PASSWORD", "PRIVATE_KEY_PEM"]
    found_secrets = False
    
    for root, dirs, files in os.walk(root_dir):
        # Skip build dirs, caches, git, and test folders
        dirs[:] = [d for d in dirs if d not in [".git", "target", ".venv", "__pycache__", "node_modules", "tests", "test", "testing"]]
        for file in files:
            if "test_" in file or file == "sbom_gate.py":
                continue
            if file.endswith((".py", ".rs", ".toml", ".yaml", ".json")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            for keyword in secret_keywords:
                                if keyword in line and "mock" not in line.lower() and "test" not in line.lower():
                                    log.error(f"[FAIL] Secret keyword '{keyword}' found in {file_path}:{line_num}")
                                    found_secrets = True
                except Exception as e:
                    log.debug(f"Could not read {file_path}: {e}")
                    
    return not found_secrets


def generate_sbom(root_dir: str) -> dict:
    """Return a legacy heuristic inventory; not a complete or verified SBOM."""
    log.info("[SBOM Gate] Scanning dependencies and generating CycloneDX SBOM...")
    
    # Base CycloneDX structure
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "urn:uuid:3e0753f2-a7d6-444c-9f66-239634e073d8",
        "version": 1,
        "metadata": {
            "component": {
                "name": "kairo-phantom",
                "version": "3.9.0",
                "type": "application"
            }
        },
        "components": []
    }
    
    # Scan Cargo.toml dependencies (if exists)
    cargo_path = os.path.join(root_dir, "Cargo.toml")
    if os.path.exists(cargo_path):
        try:
            with open(cargo_path, "r") as f:
                content = f.read()
            # Simple regex/parser to extract dependencies
            for line in content.splitlines():
                if "=" in line and not line.strip().startswith("["):
                    parts = line.split("=")
                    dep_name = parts[0].strip()
                    if dep_name not in ["name", "version", "edition", "authors", "workspace", "members"]:
                        sbom["components"].append({
                            "name": dep_name,
                            "type": "library",
                            "bom-ref": f"pkg:cargo/{dep_name}",
                            "purl": f"pkg:cargo/{dep_name}"
                        })
        except Exception as e:
            log.warning(f"Failed to parse Cargo.toml: {e}")
            
    # Add Python sidecar dependencies
    sbom["components"].extend([
        {"name": "fastapi", "type": "library", "bom-ref": "pkg:pypi/fastapi", "purl": "pkg:pypi/fastapi"},
        {"name": "cryptography", "type": "library", "bom-ref": "pkg:pypi/cryptography", "purl": "pkg:pypi/cryptography"},
        {"name": "openpyxl", "type": "library", "bom-ref": "pkg:pypi/openpyxl", "purl": "pkg:pypi/openpyxl"},
        {"name": "python-docx", "type": "library", "bom-ref": "pkg:pypi/python-docx", "purl": "pkg:pypi/python-docx"},
        {"name": "python-pptx", "type": "library", "bom-ref": "pkg:pypi/python-pptx", "purl": "pkg:pypi/python-pptx"},
    ])
    
    return sbom


def sign_sbom(sbom_path: str, sig_path: str) -> bool:
    """Refuse legacy ephemeral signing; no approved verification identity exists.

    Kept for callers that require a boolean gate. Never creates or trusts a
    signature, even if cryptography is installed or an old signature exists.
    """
    log.error("SBOM signing unavailable: approved signer/verification policy required")
    return False


def run_cargo_audit(root_dir: str) -> bool:
    """
    Run cargo-audit to check Rust dependencies for known CVEs.
    Returns True only when cargo-audit executes successfully.
    Missing tooling, missing manifest, errors and vulnerabilities fail closed.
    """
    import subprocess
    log.info("[SBOM Gate] Running cargo-audit for CVE checks...")
    cargo_toml = os.path.join(root_dir, "Cargo.toml")
    if not os.path.exists(cargo_toml):
        log.error("[SBOM Gate] No Cargo.toml found; audit not performed")
        return False

    try:
        result = subprocess.run(
            ["cargo", "audit", "--json"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            log.info("[SBOM Gate] [OK] cargo-audit: No vulnerabilities found")
            return True
        else:
            # Parse JSON output for vulnerability count
            try:
                audit_data = json.loads(result.stdout)
                vuln_count = len(audit_data.get("vulnerabilities", {}).get("list", []))
                log.error(f"[SBOM Gate] [FAIL] cargo-audit: {vuln_count} vulnerability(ies) found")
            except Exception:
                log.error(f"[SBOM Gate] [FAIL] cargo-audit failed with code {result.returncode}")
            return False
    except FileNotFoundError:
        log.error("[SBOM Gate] cargo-audit unavailable; audit not performed")
        return False
    except subprocess.TimeoutExpired:
        log.error("[SBOM Gate] cargo-audit timed out after 120s")
        return False
    except Exception as e:
        log.warning(f"[SBOM Gate] cargo-audit check error: {e}")
        return False


def main() -> int:
    """Refuse the retired all-in-one gate before scans, files or subprocesses."""
    print("BLOCKED: legacy SBOM gate is not a release qualification mechanism. "
          "Approved dependency inventory, advisory scan and verifiable signer "
          "evidence are required; production_qualified=false.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
