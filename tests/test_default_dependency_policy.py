"""Offline direct-manifest policy guards, not an SBOM or legal clearance.

No dependency imports, installers, PDF mocks, network, or product runtime. These
also run with stdlib unittest, independent of legacy dependency-heavy collection.
"""
from pathlib import Path
import re
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LEGACY_EPUB = "requirements-legacy-epub.txt"
EXCLUDED_DEFAULT_NAMES = {
    "pymupdf", "pymupdfb", "fitz", "pymupdf4llm", "pdfmux", "ebooklib",
}
_INCLUDE = re.compile(r"(?:-r\s*|--requirement(?:\s+|=)|-c\s*|--constraint(?:\s+|=))(.+)")
_REQUIREMENT = re.compile(
    r"([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]+\])?\s*"
    r"(?:(?:===|==|~=|!=|<=|>=|<|>).+|@\s*\S+.*|;.*)?"
)


def manifest_names(path, root, active=()):
    """Read local requirement/constraint closure, failing closed on unknown syntax.

    Named PEP 508 URLs are checked by declared distribution name only. URL
    contents and transitive metadata are deliberately not resolved or downloaded.
    """
    root = root.resolve()
    path = path.resolve()
    if not path.is_relative_to(root):
        raise AssertionError(f"Manifest escapes root: {path}")
    if path in active:
        raise AssertionError(f"Manifest include cycle: {path}")
    names = set()
    pending = ""
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0].rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        line = pending + line
        pending = ""
        include = _INCLUDE.fullmatch(line)
        if include:
            target = include.group(1).strip().strip("\"'")
            if not target or re.search(r"\s|://", target):
                raise AssertionError(f"Unsupported manifest include: {path}:{number}: {line}")
            names |= manifest_names(path.parent / target, root, (*active, path))
            continue
        requirement = _REQUIREMENT.fullmatch(line)
        if not requirement:
            raise AssertionError(f"Unsupported requirement: {path}:{number}: {line}")
        names.add(re.sub(r"[-_.]+", "-", requirement.group(1)).lower())
    if pending:
        raise AssertionError(f"Unterminated requirement continuation: {path}")
    return names


def assert_default_manifest(path, root):
    names = manifest_names(path, root)
    excluded = sorted(names & EXCLUDED_DEFAULT_NAMES)
    if excluded:
        raise AssertionError(f"Excluded default dependencies in {path}: {excluded}")
    return names


def default_manifests():
    # install.sh/PowerShell sidecar + root manifests; overlay image + telemetry;
    # domain/MCP manifests remain subject to this same direct-dependency guard.
    return sorted({
        *(p for p in ROOT.glob("requirements*.txt") if p.name != LEGACY_EPUB),
        ROOT / "requirements.lock",
        ROOT / "kairo-sidecar/requirements.txt",
        ROOT / "docker/requirements-runtime.txt",
        *(ROOT / "kairo").rglob("requirements*.txt"),
        *(ROOT / "mcp-servers").rglob("requirements*.txt"),
    })


class TestDefaultDependencyPolicy(unittest.TestCase):
    def test_default_manifests_exclude_banned_and_review_only_packages(self):
        for path in default_manifests():
            with self.subTest(manifest=str(path.relative_to(ROOT))):
                self.assertTrue(path.is_file())
                assert_default_manifest(path, ROOT)

    def test_supported_real_pdf_dependencies_remain_declared(self):
        runtime = manifest_names(ROOT / "docker/requirements-runtime.txt", ROOT)
        tests = manifest_names(ROOT / "requirements-test.txt", ROOT)
        domain = manifest_names(ROOT / "kairo/domains/pdf/requirements.txt", ROOT)
        self.assertIn("pdfplumber", runtime)
        for names in (tests, domain):
            self.assertTrue({"pdfplumber", "pikepdf", "pypdfium2", "pypdf"} <= names)

    def test_legacy_epub_is_separate_and_not_default_included(self):
        self.assertEqual(manifest_names(ROOT / LEGACY_EPUB, ROOT), {"ebooklib"})
        text = (ROOT / LEGACY_EPUB).read_text(encoding="utf-8")
        self.assertIn("LGPL", text)
        self.assertIn("review", text)
        self.assertNotIn(ROOT / LEGACY_EPUB, default_manifests())
        for path in default_manifests():
            self.assertNotIn("ebooklib", manifest_names(path, ROOT))

    def test_guard_rejects_case_extras_markers_urls_and_wrappers(self):
        cases = (
            "PyMuPDF>=1.23.0", "pYmUpDf==1.26 # optional/lazy is NOT an exception",
            "PyMuPDF[pdf]>=1.23; platform_system == 'Windows'",
            "PyMuPDF @ https://example.invalid/engine.whl",
            "PyMuPDFb>=1.0", "fitz", "pymupdf4llm>=0.1", "pdfmux>=0.1",
            "EbookLib>=0.18; python_version < '3.99'",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "requirements.txt"
            for case in cases:
                with self.subTest(requirement=case):
                    path.write_text(case + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(AssertionError, "Excluded default"):
                        assert_default_manifest(path, root)

    def test_guard_follows_local_includes_and_constraints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "requirements.txt"
            nested = root / "nested"
            nested.mkdir()
            (nested / "engine.txt").write_text("PyMuPDF>=1.23\n", encoding="utf-8")
            (nested / "base.txt").write_text("-r engine.txt\n", encoding="utf-8")
            for directive in ("-r nested/base.txt", "-rnested/base.txt",
                              "--requirement=nested/base.txt", "--requirement nested/base.txt",
                              "-c nested/base.txt", "-cnested/base.txt",
                              "--constraint=nested/base.txt", "--constraint nested/base.txt"):
                with self.subTest(directive=directive):
                    entry.write_text(directive + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(AssertionError, "Excluded default"):
                        assert_default_manifest(entry, root)

    def test_guard_does_not_treat_comment_as_installed_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "requirements.txt"
            entry.write_text("# PyMuPDF is banned\npdfplumber>=0.11 # oracle\n"
                             "pikepdf>=9\nPyPDF>=4\n", encoding="utf-8")
            self.assertEqual(assert_default_manifest(entry, root),
                             {"pdfplumber", "pikepdf", "pypdf"})

    def test_distribution_names_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "requirements.txt"
            entry.write_text("python_docx>=1\npython.docx>=1\n", encoding="utf-8")
            self.assertEqual(manifest_names(entry, root), {"python-docx"})

    def test_guard_handles_continued_requirement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "requirements.txt"
            entry.write_text("PyMuPDF \\\n >=1.23\n", encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "Excluded default"):
                assert_default_manifest(entry, root)

    def test_guard_fails_closed_on_cycles_missing_and_opaque_inputs(self):
        cases = ("-r requirements.txt", "-r missing.txt", "-r ../outside.txt",
                 "--requirement https://example.invalid/requirements.txt",
                 "https://example.invalid/engine.whl", "-e git+https://example.invalid/repo",
                 "--index-url https://example.invalid/simple", "pdfplumber \\")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "requirements.txt"
            for case in cases:
                with self.subTest(line=case):
                    entry.write_text(case + "\n", encoding="utf-8")
                    with self.assertRaises((AssertionError, FileNotFoundError)):
                        assert_default_manifest(entry, root)


if __name__ == "__main__":
    unittest.main()
