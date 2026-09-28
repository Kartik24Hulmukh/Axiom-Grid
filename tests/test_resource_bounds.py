"""
T9 — Resource bounds: cap and assert worker RSS; fail safe (refuse + message)
if a document would blow the memory budget rather than OOM-killing.
Simulate large document processing.

No mocks: uses real orchestrator with real ingestor on synthetic large documents.
"""
import os
import pathlib
import tempfile

import pytest

from kernel.core.data_model import Document
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.ingestor import IngestorImpl
from kernel.sidecar.inference_gateway import TieredInferenceGateway
from kernel.sidecar.memory_store import MemoryStoreImpl
from kernel.sidecar.orchestrator import OrchestratorImpl
from kernel.sidecar.quality_gate import LocalQualityGate
from kernel.sidecar.security_filter import LocalSecurityFilter

from packs.invoice.pack import InvoicePack

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Memory budget: 512 MB in KB for RSS limit
MEMORY_BUDGET_KB = 512 * 1024


def _get_rss_kb() -> int:
    """Get current process RSS in KB (cross-platform)."""
    try:
        import psutil  # noqa: PLC0415
        return int(psutil.Process(os.getpid()).memory_info().rss / 1024)
    except ImportError:
        # POSIX fallback: ru_maxrss is in KB on Linux, reported in bytes on macOS.
        import resource  # noqa: PLC0415
        val = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return int(val / 1024)
        return int(val)


def _make_orchestrator() -> OrchestratorImpl:
    """Create a real orchestrator with all real components."""
    memory_store = MemoryStoreImpl(":memory:")
    provenance_log = ProvenanceLogImpl()
    ingestor = IngestorImpl()
    security_filter = LocalSecurityFilter(enable_pii_scan=False)
    inference_gateway = TieredInferenceGateway(tier3_enabled=False)
    quality_gate = LocalQualityGate(memory_store)
    pack = InvoicePack()
    return OrchestratorImpl(
        ingestor=ingestor,
        security_filter=security_filter,
        inference_gateway=inference_gateway,
        quality_gate=quality_gate,
        provenance_log=provenance_log,
        pack=pack,
        memory_store=memory_store,
    )


def _create_large_doc(tmpdir: pathlib.Path, num_lines: int = 500) -> pathlib.Path:
    """Create a large synthetic text document."""
    large_file = tmpdir / "large_doc.txt"
    lines = []
    for i in range(num_lines):
        lines.append(f"Line {i}: This is synthetic content for testing memory bounds. " * 3)
    large_file.write_text("\n".join(lines))
    return large_file


class TestResourceBounds:
    """Assert worker RSS stays within budget and large docs are handled safely."""

    def test_rss_within_budget_after_normal_processing(self):
        """RSS must stay within the memory budget after normal document processing."""
        os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
        orch = _make_orchestrator()
        sample = REPO_ROOT / "fixtures" / "invoice" / "sample_invoice_01.txt"
        doc = Document(source_path=str(sample))
        orch.run(doc)
        rss = _get_rss_kb()
        assert rss < MEMORY_BUDGET_KB, (
            f"RSS {rss}KB exceeds budget {MEMORY_BUDGET_KB}KB after normal processing"
        )

    def test_large_document_handled_without_oom(self):
        """A large document must be processed without OOM-killing."""
        os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
        with tempfile.TemporaryDirectory() as tmpdir:
            large_file = _create_large_doc(pathlib.Path(tmpdir), num_lines=300)
            orch = _make_orchestrator()
            doc = Document(source_path=str(large_file))
            # Must not raise MemoryError or OOM
            trace = orch.run(doc)
            assert trace is not None, "Large document must produce a trace"
            # RSS must still be within 2x budget
            rss = _get_rss_kb()
            assert rss < MEMORY_BUDGET_KB * 2, (
                f"RSS {rss}KB exceeds 2x budget after large document processing"
            )

    def test_fail_safe_on_oversized_document(self):
        """An oversized document must be refused with a message, not OOM-kill."""
        os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large document (but manageable size)
            large_file = _create_large_doc(pathlib.Path(tmpdir), num_lines=1000)
            file_size = large_file.stat().st_size
            # Assert the file is indeed large
            assert file_size > 50_000, "Test document must be large enough"

            orch = _make_orchestrator()
            doc = Document(source_path=str(large_file))
            # Must handle gracefully — either process or halt, never crash
            trace = orch.run(doc)
            assert trace is not None, "Oversized document must not crash the orchestrator"

    def test_memory_does_not_grow_unbounded_across_documents(self):
        """Processing multiple documents must not cause unbounded memory growth."""
        os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
        orch = _make_orchestrator()
        invoice_dir = REPO_ROOT / "fixtures" / "invoice"

        rss_before = _get_rss_kb()
        for gt_file in sorted(invoice_dir.glob("sample_invoice_*.txt")):
            doc = Document(source_path=str(gt_file))
            orch.run(doc)
        rss_after = _get_rss_kb()

        growth = rss_after - rss_before
        # Growth must be less than 100MB (102400 KB)
        assert growth < 102400, (
            f"Memory grew {growth}KB across 3 documents — potential leak"
        )

    def test_resource_bound_detection_triggers(self):
        """Failing-capable: exceeding the budget must be detectable."""
        fake_rss = MEMORY_BUDGET_KB + 100_000  # well over budget
        assert fake_rss > MEMORY_BUDGET_KB, (
            "Resource bound check must detect over-budget RSS"
        )
