"""
Tests for X6 — Scope Discipline + CONTRIBUTING

Asserts that CONTRIBUTING.md, CODEOWNERS, and PUBLIC_ROADMAP.md exist
and contain the required sections.
"""

import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


# ---------------------------------------------------------------------------
# Test 1: Required files exist
# ---------------------------------------------------------------------------
class TestRequiredFilesExist:
    """The scope discipline files must all exist."""

    def test_contributing_md_exists(self):
        """CONTRIBUTING.md must exist."""
        path = os.path.join(REPO_ROOT, "CONTRIBUTING.md")
        assert os.path.exists(path), "CONTRIBUTING.md must exist"

    def test_codeowners_exists(self):
        """CODEOWNERS must exist."""
        path = os.path.join(REPO_ROOT, "CODEOWNERS")
        assert os.path.exists(path), "CODEOWNERS must exist"

    def test_public_roadmap_exists(self):
        """docs/PUBLIC_ROADMAP.md must exist."""
        path = os.path.join(REPO_ROOT, "docs", "PUBLIC_ROADMAP.md")
        assert os.path.exists(path), "docs/PUBLIC_ROADMAP.md must exist"

    def test_readme_exists(self):
        """README.md must exist."""
        path = os.path.join(REPO_ROOT, "README.md")
        assert os.path.exists(path), "README.md must exist"

    def test_compliance_brief_exists(self):
        """docs/COMPLIANCE_BRIEF.md must exist."""
        path = os.path.join(REPO_ROOT, "docs", "COMPLIANCE_BRIEF.md")
        assert os.path.exists(path), "docs/COMPLIANCE_BRIEF.md must exist"

    def test_verifier_crate_release_exists(self):
        """docs/VERIFIER_CRATE_RELEASE.md must exist."""
        path = os.path.join(REPO_ROOT, "docs", "VERIFIER_CRATE_RELEASE.md")
        assert os.path.exists(path), "docs/VERIFIER_CRATE_RELEASE.md must exist"


# ---------------------------------------------------------------------------
# Test 2: CONTRIBUTING.md has required sections
# ---------------------------------------------------------------------------
class TestContributingContent:
    """CONTRIBUTING.md must contain the required scope and contribution sections."""

    @pytest.fixture
    def contributing(self):
        with open(os.path.join(REPO_ROOT, "CONTRIBUTING.md")) as f:
            return f.read()

    def test_has_scope_boundaries(self, contributing):
        """CONTRIBUTING.md must have a scope boundaries section."""
        assert "Scope Boundaries" in contributing or "scope boundaries" in contributing.lower(), \
            "CONTRIBUTING.md must have a 'Scope Boundaries' section"

    def test_has_kairo_does(self, contributing):
        """CONTRIBUTING.md must state what Kairo DOES."""
        assert "DOES" in contributing, "CONTRIBUTING.md must have a 'Kairo DOES' section"

    def test_has_kairo_does_not(self, contributing):
        """CONTRIBUTING.md must state what Kairo Does NOT do."""
        assert "Does NOT" in contributing or "does not" in contributing.lower(), \
            "CONTRIBUTING.md must have a 'Kairo Does NOT' section"

    def test_has_help_wanted(self, contributing):
        """CONTRIBUTING.md must have a 'help wanted' section."""
        assert "help wanted" in contributing.lower(), \
            "CONTRIBUTING.md must have a 'help wanted' section"

    def test_has_read_suggest_only(self, contributing):
        """CONTRIBUTING.md must mention READ + SUGGEST ONLY scope."""
        assert "READ" in contributing and "SUGGEST" in contributing, \
            "CONTRIBUTING.md must mention READ + SUGGEST ONLY"

    def test_has_no_autonomous_writes(self, contributing):
        """CONTRIBUTING.md must mention no autonomous writes."""
        assert "autonomous" in contributing.lower() or "auto-apply" in contributing.lower(), \
            "CONTRIBUTING.md must mention no autonomous writes"

    def test_has_four_packs(self, contributing):
        """CONTRIBUTING.md must mention the four launch Packs."""
        for pack in ["generic", "invoice", "paper", "contract"]:
            assert pack in contributing.lower(), \
                f"CONTRIBUTING.md must mention the '{pack}' Pack"

    def test_has_red_team_reference(self, contributing):
        """CONTRIBUTING.md must reference the red-team submission flow."""
        assert "red-team" in contributing.lower() or "red team" in contributing.lower(), \
            "CONTRIBUTING.md must reference the red-team flow"

    def test_has_audit_log_reference(self, contributing):
        """CONTRIBUTING.md must reference the audit log."""
        assert "audit" in contributing.lower(), \
            "CONTRIBUTING.md must reference the audit log"

    def test_has_verifier_reference(self, contributing):
        """CONTRIBUTING.md must reference the verifier."""
        assert "verifier" in contributing.lower(), \
            "CONTRIBUTING.md must reference the verifier"


# ---------------------------------------------------------------------------
# Test 3: CODEOWNERS has required ownership rules
# ---------------------------------------------------------------------------
class TestCodeownersContent:
    """CODEOWNERS must have appropriate ownership rules."""

    @pytest.fixture
    def codeowners(self):
        with open(os.path.join(REPO_ROOT, "CODEOWNERS")) as f:
            return f.read()

    def test_has_kernel_core_ownership(self, codeowners):
        """CODEOWNERS must have ownership for kernel/core/."""
        assert "kernel/core/" in codeowners, \
            "CODEOWNERS must define ownership for kernel/core/"

    def test_has_grounding_ownership(self, codeowners):
        """CODEOWNERS must have ownership for grounding.py."""
        assert "grounding.py" in codeowners, \
            "CODEOWNERS must define ownership for grounding.py"

    def test_has_audit_log_ownership(self, codeowners):
        """CODEOWNERS must have ownership for audit_log.py."""
        assert "audit_log.py" in codeowners, \
            "CODEOWNERS must define ownership for audit_log.py"

    def test_has_tests_ownership(self, codeowners):
        """CODEOWNERS must have ownership for tests/."""
        assert "/tests/" in codeowners, \
            "CODEOWNERS must define ownership for tests/"

    def test_has_red_team_ownership(self, codeowners):
        """CODEOWNERS must have ownership for red-team/."""
        assert "red-team" in codeowners, \
            "CODEOWNERS must define ownership for red-team/"

    def test_has_docs_ownership(self, codeowners):
        """CODEOWNERS must have ownership for docs."""
        assert "docs/" in codeowners or "CONTRIBUTING" in codeowners, \
            "CODEOWNERS must define ownership for docs"

    def test_has_default_owner(self, codeowners):
        """CODEOWNERS must have a default fallthrough owner."""
        assert "*" in codeowners, \
            "CODEOWNERS must have a default (*) fallthrough owner"

    def test_has_security_ownership(self, codeowners):
        """CODEOWNERS must have ownership for security files."""
        assert "SECURITY" in codeowners, \
            "CODEOWNERS must define ownership for security files"


# ---------------------------------------------------------------------------
# Test 4: PUBLIC_ROADMAP.md has required sections
# ---------------------------------------------------------------------------
class TestPublicRoadmapContent:
    """PUBLIC_ROADMAP.md must contain the required sections."""

    @pytest.fixture
    def roadmap(self):
        with open(os.path.join(REPO_ROOT, "docs", "PUBLIC_ROADMAP.md")) as f:
            return f.read()

    def test_has_scope_boundaries(self, roadmap):
        """PUBLIC_ROADMAP.md must have scope boundaries."""
        assert "Scope" in roadmap, \
            "PUBLIC_ROADMAP.md must have a scope section"

    def test_has_kairo_does(self, roadmap):
        """PUBLIC_ROADMAP.md must state what Kairo DOES."""
        assert "DOES" in roadmap, \
            "PUBLIC_ROADMAP.md must have a 'Kairo DOES' section"

    def test_has_kairo_does_not(self, roadmap):
        """PUBLIC_ROADMAP.md must state what Kairo Does NOT do."""
        assert "Does NOT" in roadmap or "does not" in roadmap.lower(), \
            "PUBLIC_ROADMAP.md must have a 'Kairo Does NOT' section"

    def test_has_help_wanted(self, roadmap):
        """PUBLIC_ROADMAP.md must have a 'help wanted' section."""
        assert "help wanted" in roadmap.lower(), \
            "PUBLIC_ROADMAP.md must have a 'help wanted' section"

    def test_has_roadmap_items(self, roadmap):
        """PUBLIC_ROADMAP.md must have roadmap items with checkboxes."""
        assert "- [ ]" in roadmap or "- [x]" in roadmap, \
            "PUBLIC_ROADMAP.md must have roadmap items"

    def test_has_current_state(self, roadmap):
        """PUBLIC_ROADMAP.md must have a current state section."""
        assert "Current State" in roadmap or "current state" in roadmap.lower(), \
            "PUBLIC_ROADMAP.md must have a current state section"

    def test_has_contribution_link(self, roadmap):
        """PUBLIC_ROADMAP.md must link to CONTRIBUTING.md."""
        assert "CONTRIBUTING" in roadmap, \
            "PUBLIC_ROADMAP.md must link to CONTRIBUTING.md"


# ---------------------------------------------------------------------------
# Test 5: README.md has scope section
# ---------------------------------------------------------------------------
class TestReadmeScopeSection:
    """README.md must have a scope boundaries section (appended, not overwritten)."""

    @pytest.fixture
    def readme(self):
        with open(os.path.join(REPO_ROOT, "README.md")) as f:
            return f.read()

    def test_has_scope_boundaries(self, readme):
        """README.md must have a scope boundaries section."""
        assert "Scope Boundaries" in readme or "scope boundaries" in readme.lower(), \
            "README.md must have a scope boundaries section"

    def test_has_kairo_does(self, readme):
        """README.md must state what Kairo DOES."""
        assert "DOES" in readme, \
            "README.md must have a 'Kairo DOES' section"

    def test_has_kairo_does_not(self, readme):
        """README.md must state what Kairo Does NOT do."""
        assert "Does NOT" in readme or "does not" in readme.lower(), \
            "README.md must have a 'Kairo Does NOT' section"

    def test_has_read_suggest_only(self, readme):
        """README.md must mention READ + SUGGEST ONLY."""
        assert "READ" in readme and "SUGGEST" in readme, \
            "README.md must mention READ + SUGGEST ONLY"

    def test_has_no_source_no_answer(self, readme):
        """README.md must contain the core promise."""
        assert "No source" in readme, \
            "README.md must contain the 'No source → no answer' promise"

    def test_original_content_preserved(self, readme):
        """README.md must still contain original content (not overwritten)."""
        # The canonical product identity replaces the legacy Kairo branding.
        assert "# Axiom-Grid" in readme and "## Quickstart" in readme, \
            "README.md must preserve product identity and install guidance"


# ---------------------------------------------------------------------------
# Test 6: Scope consistency across files
# ---------------------------------------------------------------------------
class TestScopeConsistency:
    """Scope boundaries must be consistent across CONTRIBUTING, README, and ROADMAP."""

    def test_read_suggest_consistent(self):
        """All files must consistently state READ + SUGGEST ONLY."""
        files_to_check = [
            os.path.join(REPO_ROOT, "CONTRIBUTING.md"),
            os.path.join(REPO_ROOT, "README.md"),
            os.path.join(REPO_ROOT, "docs", "PUBLIC_ROADMAP.md"),
        ]
        for fpath in files_to_check:
            with open(fpath) as f:
                content = f.read()
            assert "READ" in content and "SUGGEST" in content, \
                f"{os.path.basename(fpath)} must mention READ + SUGGEST ONLY"

    def test_four_packs_consistent(self):
        """All files must mention the four launch Packs."""
        files_to_check = [
            os.path.join(REPO_ROOT, "CONTRIBUTING.md"),
            os.path.join(REPO_ROOT, "docs", "PUBLIC_ROADMAP.md"),
        ]
        for fpath in files_to_check:
            with open(fpath) as f:
                content = f.read().lower()
            for pack in ["generic", "invoice", "paper", "contract"]:
                assert pack in content, \
                    f"{os.path.basename(fpath)} must mention the '{pack}' Pack"