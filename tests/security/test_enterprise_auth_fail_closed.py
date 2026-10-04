"""Incomplete enterprise authorization surfaces must fail closed."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_rbac_unknown_principals_default_deny_and_local_identity_is_explicit():
    source = (ROOT / "phantom-core/src/identity.rs").read_text()
    assert "None => false" in source
    assert 'matches!(agent_id, "auto" | "content" | "reasoning")' not in source
    assert 'rbac.allow(&identity.agent_id, vec!["*".to_string()])' in source


def test_mock_enterprise_auth_and_cloud_sync_are_quarantined():
    identity = (ROOT / "phantom-core/src/identity.rs").read_text()
    mcp = (ROOT / "phantom-core/src/mcp_auth.rs").read_text()
    assert "OIDC verification is unavailable; denying token" in identity
    assert "Cloud sync is disabled until authenticated encrypted transport" in identity
    assert "MCP OAuth authorization is unavailable" in mcp
    assert "true\n    }" not in mcp


def test_jit_validity_verifies_ed25519_signature_and_time_bounds():
    source = (ROOT / "phantom-core/src/identity.rs").read_text()
    start = source.index("impl JitToken")
    end = source.index("// ─── RBAC Table", start)
    implementation = source[start:end]
    assert "VerifyingKey::from_bytes" in implementation
    assert "verify_strict" in implementation
    assert "self.issued_at > now" in implementation
    assert "now >= self.expires_at" in implementation


def test_disabled_directory_mapping_never_grants_admin():
    source = (ROOT / "phantom-core/src/identity.rs").read_text()
    assert "if !self.enabled {\n            return PermissionRing::Admin;" not in source