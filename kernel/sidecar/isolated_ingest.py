"""Killable binary-document ingestion in a spawned child process.

A ThreadPoolExecutor worker running a native PDF/DOCX parser cannot be
cancelled: a hung or adversarial document (zip bomb, malformed xref loop)
holds a service thread and the GIL forever. When
``AXIOM_EXTRACTION_ISOLATION=process``, binary parsing happens in a spawned
child whose address space and CPU are limited BEFORE any parser work, and
whose whole process tree is killed and reaped on deadline. The parent keeps
zero stuck parser state. Default stays ``thread`` for back-compat; production
deployments serving untrusted documents MUST set ``process``.
"""
from __future__ import annotations

import multiprocessing as _mp
import os


class IsolatedIngestDeadline(TimeoutError):
    """The child exceeded its deadline and was killed. Map to HTTP 504."""


class IsolatedIngestResourceError(RuntimeError):
    """The child hit an rlimit (address space / CPU). Map to HTTP 422."""


def _set_limits() -> None:
    try:
        import resource
    except ImportError:  # non-POSIX: deadline isolation still applies
        return
    cpu = int(os.environ.get("AXIOM_INGEST_CPU_SECONDS", "120"))
    as_bytes = int(os.environ.get("AXIOM_INGEST_RSS_BYTES", str(2 * 1024**3)))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (as_bytes, as_bytes))


def _child_entry(filepath: str, queue) -> None:
    _set_limits()
    try:
        from kernel.sidecar.ingestor import IngestorImpl
        queue.put(("ok", IngestorImpl().ingest(filepath)))
    except (ValueError, RuntimeError) as exc:
        queue.put(("reject", f"{type(exc).__name__}: {exc}"))
    except MemoryError:
        queue.put(("resource", "address-space limit exceeded"))
    except BaseException as exc:  # noqa: BLE001 -- contain arbitrary parser failures inside the child
        queue.put(("reject", f"{type(exc).__name__}: {exc}"))


def ingest_isolated_document(filepath: str, timeout: float):
    """Parse once in a spawned child; return chunks, document and pages.

    Raises IsolatedIngestDeadline (504) if the deadline passes, ValueError
    (422) for unsupported/invalid documents, IsolatedIngestResourceError
    (422) when an rlimit fired.
    """
    ctx = _mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_child_entry, args=(str(filepath), queue), daemon=True)
    try:
        proc.start()
    except BaseException:
        queue.close()
        queue.join_thread()
        proc.close()
        raise
    # Drain BEFORE joining: a child's Queue feeder cannot flush a multi-MiB
    # result into an undrained pipe, so join-before-get deadlocks valid inputs.
    import queue as queue_module
    import time
    deadline = time.monotonic() + timeout
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise IsolatedIngestDeadline(f"isolated ingest exceeded {timeout:.1f}s deadline")
            try:
                status, payload = queue.get(timeout=min(.05, remaining))
                break
            except queue_module.Empty as exc:
                if not proc.is_alive():
                    raise IsolatedIngestResourceError(
                        f"isolated ingest child died without a result (exitcode={proc.exitcode})") from exc
        proc.join(max(0, deadline - time.monotonic()))
        if proc.is_alive():
            raise IsolatedIngestDeadline(f"isolated ingest exceeded {timeout:.1f}s deadline")
    except queue_module.Empty as exc:
        if not proc.is_alive():
            raise IsolatedIngestResourceError(
                f"isolated ingest child died without a result (exitcode={proc.exitcode})") from exc
        raise IsolatedIngestDeadline(f"isolated ingest exceeded {timeout:.1f}s deadline") from exc
    except IsolatedIngestDeadline:
        raise
    except IsolatedIngestResourceError:
        raise
    except Exception as exc:
        raise IsolatedIngestResourceError(
            f"isolated ingest child died without a result (exitcode={proc.exitcode})") from exc
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join()
        queue.close()
        queue.join_thread()
        proc.close()
    if status == "ok":
        return payload
    if status == "resource":
        raise IsolatedIngestResourceError(payload)
    raise ValueError(payload)


def ingest_isolated(filepath: str, timeout: float):
    """Compatibility text-only projection of a complete isolated parse."""
    chunks, _, _ = ingest_isolated_document(filepath, timeout)
    return [chunk.text for chunk in chunks]


class ParsedDocumentIngestor:
    """Pass the already isolated parse to the pipeline without reparsing."""
    def __init__(self, filepath, parsed):
        self.filepath = str(filepath)
        self.parsed = parsed

    def ingest(self, filepath):
        if str(filepath) != self.filepath:
            raise ValueError("Parsed document belongs to a different source path")
        return self.parsed


def isolation_enabled() -> bool:
    return os.environ.get("AXIOM_EXTRACTION_ISOLATION", "thread").strip().lower() == "process"
