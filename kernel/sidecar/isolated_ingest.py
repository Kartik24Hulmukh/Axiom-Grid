"""Killable document parsing with bounded, validated JSON results.

This is a resource/deadline boundary, NOT an OS sandbox: the parser retains the
worker user's filesystem and network privileges. Spawned children parse only a
private snapshot of captured bytes. No child-controlled pickle is deserialized.
POSIX process groups are killed on completion/timeout (descendants can escape by
creating a new session); non-POSIX platforms fail closed. The opt-in ``thread``
development mode has the same validation but cannot interrupt a hung parser.
"""
from __future__ import annotations

import hashlib
import json
import math
import multiprocessing as _mp
import os
from pathlib import Path
import signal
import stat
import tempfile
import time
from dataclasses import asdict, replace
from datetime import datetime

from kernel.core.data_model import BBox, Chunk, Document, Page

# Hard ceilings also bound operator-configurable limits.
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
MAX_CHUNKS = 20000
MAX_PAGES = 10000
MAX_TEXT_CHARS = 4 * 1024 * 1024
MAX_EMBEDDING_VALUES = 4096


class IsolatedIngestDeadline(TimeoutError):
    """The deadline expired; the parser process was killed and reaped."""


class IsolatedIngestResourceError(RuntimeError):
    """Resource setup failed or the parser exited without a valid result."""


def isolation_enabled() -> bool:
    """Process by default. Invalid settings fail closed, never imply thread."""
    mode = os.environ.get("AXIOM_EXTRACTION_ISOLATION", "process")
    if mode not in {"process", "thread"}:
        raise ValueError("AXIOM_EXTRACTION_ISOLATION must be process or thread")
    return mode == "process"


def _positive_setting(name: str, default: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    if not raw.isascii() or not raw.isdecimal() or not 0 < int(raw) <= maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return int(raw)


def _configuration() -> dict[str, int]:
    return {
        "input": _positive_setting("AXIOM_INGEST_MAX_INPUT_BYTES", MAX_INPUT_BYTES, MAX_INPUT_BYTES),
        "output": _positive_setting("AXIOM_INGEST_MAX_OUTPUT_BYTES", MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES),
        "chunks": _positive_setting("AXIOM_INGEST_MAX_CHUNKS", MAX_CHUNKS, MAX_CHUNKS),
        "pages": _positive_setting("AXIOM_INGEST_MAX_PAGES", MAX_PAGES, MAX_PAGES),
        "text": _positive_setting("AXIOM_MAX_EXTRACTED_CHARS", MAX_TEXT_CHARS, MAX_TEXT_CHARS),
        "cpu": _positive_setting("AXIOM_INGEST_CPU_SECONDS", 120, 86400),
        "as": _positive_setting("AXIOM_INGEST_RSS_BYTES", 2 * 1024**3, 16 * 1024**3),
    }


def _set_limits(limits: dict[str, int]) -> None:
    # Invalid or unavailable limits must not silently disable containment.
    import resource
    resource.setrlimit(resource.RLIMIT_CPU, (limits["cpu"], limits["cpu"]))
    resource.setrlimit(resource.RLIMIT_AS, (limits["as"], limits["as"]))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits["output"], limits["output"]))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _keys(value, names: set[str]) -> dict:
    if type(value) is not dict or set(value) != names:
        raise ValueError("Invalid isolated ingest object schema")
    return value


def _string(value, maximum: int, *, nonempty: bool = False) -> str:
    if type(value) is not str or len(value) > maximum or (nonempty and not value):
        raise ValueError("Invalid isolated ingest string")
    # Reject surrogate code points which cannot round-trip as UTF-8.
    value.encode("utf-8", errors="strict")
    return value


def _identifier(value) -> str:
    value = _string(value, 256, nonempty=True)
    # IDs become route/query components downstream. Forbid controls, Unicode,
    # separators and reserved punctuation instead of relying on URL escaping.
    if not value.isascii() or any(not (c.isalnum() or c in "_-") for c in value):
        raise ValueError("Invalid isolated ingest route identifier")
    return value


def _integer(value, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid isolated ingest integer")
    return value


def _number(value) -> float:
    if type(value) not in (int, float):
        raise ValueError("Invalid isolated ingest finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("Invalid isolated ingest finite number")
    return float(value)


def _hash(value, *, empty: bool = False) -> str:
    value = _string(value, 64)
    if (empty and value == "") or (len(value) == 64 and all(c in "0123456789abcdef" for c in value)):
        return value
    raise ValueError("Invalid isolated ingest digest")


def _validate(payload, snapshot: str, digest: str, limits: dict[str, int]):
    """Validate all fields before constructing trusted graph objects."""
    _keys(payload, {"version", "status", "document", "chunks", "pages"})
    if type(payload["version"]) is not int or payload["version"] != 1 or payload["status"] != "ok":
        raise ValueError("Invalid isolated ingest protocol")
    d = _keys(payload["document"], {"doc_id", "source_path", "sha256", "page_count", "ingested_at"})
    doc_id = _identifier(d["doc_id"])
    if _string(d["source_path"], 4096) != snapshot or _hash(d["sha256"]) != digest:
        raise ValueError("Isolated ingest source/digest mismatch")
    count = _integer(d["page_count"], 1, limits["pages"])
    try:
        ingested_at = datetime.fromisoformat(_string(d["ingested_at"], 128, nonempty=True))
        if ingested_at.utcoffset() is None:
            raise ValueError("Ingest timestamp must be timezone aware")
    except (ValueError, OverflowError) as exc:
        raise ValueError("Invalid isolated ingest timestamp") from exc
    raw_pages, raw_chunks = payload["pages"], payload["chunks"]
    if type(raw_pages) is not list or len(raw_pages) != count:
        raise ValueError("Isolated ingest page count mismatch")
    if type(raw_chunks) is not list or len(raw_chunks) > limits["chunks"]:
        raise ValueError("Isolated ingest chunk count exceeded")
    pages, seen_pages = [], set()
    for p in raw_pages:
        _keys(p, {"doc_id", "index", "width_px", "height_px", "image_sha256"})
        if p["doc_id"] != doc_id:
            raise ValueError("Isolated ingest page document reference mismatch")
        index = _integer(p["index"], 1, count)
        if index in seen_pages:
            raise ValueError("Duplicate isolated ingest page")
        seen_pages.add(index)
        pages.append(Page(doc_id=doc_id, index=index,
                          width_px=_integer(p["width_px"], 1, 1000000),
                          height_px=_integer(p["height_px"], 1, 1000000),
                          image_sha256=_hash(p["image_sha256"], empty=True)))
    chunks, seen_chunks, text_count = [], set(), 0
    for c in raw_chunks:
        _keys(c, {"chunk_id", "doc_id", "page", "bbox", "text", "source_type", "embedding"})
        chunk_id = _identifier(c["chunk_id"])
        if chunk_id in seen_chunks or c["doc_id"] != doc_id:
            raise ValueError("Duplicate chunk ID or document reference mismatch")
        seen_chunks.add(chunk_id)
        page = _integer(c["page"], 1, count)
        if page not in seen_pages:
            raise ValueError("Invalid isolated ingest page reference")
        b = _keys(c["bbox"], {"x0", "y0", "x1", "y1"})
        coords = {k: _number(v) for k, v in b.items()}
        if any(not 0 <= v <= 1 for v in coords.values()):
            raise ValueError("Isolated ingest bbox outside normalized page")
        bbox = BBox(**coords)
        text = _string(c["text"], limits["text"])
        text_count += len(text)
        if text_count > limits["text"]:
            raise ValueError("Isolated ingest total text exceeded")
        embedding = c["embedding"]
        if type(embedding) is not list or len(embedding) > MAX_EMBEDDING_VALUES:
            raise ValueError("Invalid isolated ingest embedding")
        chunks.append(Chunk(chunk_id=chunk_id, doc_id=doc_id, page=page, bbox=bbox,
                            text=text, source_type=_string(c["source_type"], 128, nonempty=True),
                            embedding=[_number(n) for n in embedding]))
    return chunks, Document(doc_id=doc_id, source_path=snapshot, sha256=digest,
                            page_count=count, ingested_at=ingested_at), pages


def _write_result(result: str, payload: dict, maximum: int) -> None:
    """Stream to a capped private file, then atomically publish; no pipe feeder."""
    temporary = result + ".partial"
    encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    with open(temporary, "xb") as output:
        total = 0
        for part in encoder.iterencode(payload):
            data = part.encode("ascii")
            total += len(data)
            if total > maximum:
                raise ValueError("Isolated ingest output byte cap exceeded")
            output.write(data)
    os.replace(temporary, result)


def _child_entry(snapshot: str, result: str, limits: dict[str, int]) -> None:
    try:
        os.setsid()
        _set_limits(limits)
    except BaseException:
        # No parser may run after failed resource setup.
        return
    try:
        from kernel.sidecar.ingestor import IngestorImpl
        chunks, doc, pages = IngestorImpl().ingest(snapshot)
        document = asdict(doc)
        document["ingested_at"] = doc.ingested_at.isoformat()
        payload = {"version": 1, "status": "ok", "document": document,
                   "chunks": [asdict(c) for c in chunks], "pages": [asdict(p) for p in pages]}
        _write_result(result, payload, limits["output"])
    except BaseException:
        # Never expose arbitrary parser exception text or serialize exceptions.
        try:
            _write_result(result, {"version": 1, "status": "reject"}, limits["output"])
        except BaseException:
            pass


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate isolated ingest JSON key")
        result[key] = value
    return result


def _json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite isolated ingest JSON number")
    return number


def _read_result(result: str, maximum: int):
    # Child can replace its result with a FIFO/symlink/device: never follow it
    # or block opening it. Size is checked both before and during the read.
    try:
        fd = os.open(result, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > maximum or info.st_nlink != 1:
                raise ValueError("Invalid isolated ingest result file")
            data = source.read(maximum + 1)
        if len(data) > maximum:
            raise ValueError("Isolated ingest result byte cap exceeded")
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicates,
                             parse_float=_json_float,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    except FileNotFoundError as exc:
        raise IsolatedIngestResourceError("Isolated ingest child produced no result") from exc
    except (OSError, UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed isolated ingest result") from exc
    if payload == {"version": 1, "status": "reject"}:
        raise ValueError("Document parser rejected input")
    return payload


def _stop_group(proc) -> None:
    # setsid happens before parsing. killpg cannot target the parent's group.
    # If timeout preceded setsid, kill() below still handles the direct child.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join()


def ingest_document_isolated(
    filepath: str, timeout: float, *, content: bytes | None = None,
) -> tuple[list[Chunk], Document, list[Page]]:
    """Return the complete validated graph from one parser invocation.

    ``content`` is the parent's already bounded immutable capture; when supplied
    the original path is NEVER opened. Otherwise read at most the input cap + 1.
    The deadline covers capture, spawn, child execution and result validation;
    filesystem I/O/process creation themselves are not interruptible by Python.
    Thread mode is explicitly for trusted development and is not killable.
    """
    try:
        valid_timeout = type(timeout) in (int, float) and math.isfinite(timeout) and timeout > 0
    except OverflowError:
        valid_timeout = False
    if not valid_timeout:
        raise ValueError("Ingest timeout must be finite and positive")
    deadline = time.monotonic() + timeout
    if type(filepath) is not str or not filepath or len(filepath) > 4096 or "\x00" in filepath:
        raise ValueError("Invalid ingest filepath")
    process = isolation_enabled()
    limits = _configuration()
    if os.name != "posix" or not all(hasattr(os, name) for name in
                                    ("O_NOFOLLOW", "O_NONBLOCK", "setsid", "killpg")):
        raise IsolatedIngestResourceError("Isolated ingestion requires POSIX resource limits and safe file opens")
    try:
        import resource
        for name in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_FSIZE", "RLIMIT_CORE"):
            getattr(resource, name)
    except (ImportError, AttributeError) as exc:
        raise IsolatedIngestResourceError("Required POSIX resource limits unavailable") from exc
    suffix = Path(filepath).suffix.lower()
    if suffix not in {".txt", ".md", ".pdf", ".docx"}:
        raise ValueError(f"Unsupported file type: {suffix}")
    if content is None:
        fd = os.open(filepath, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError("Input must be a regular file")
            content = source.read(limits["input"] + 1)
    if type(content) is not bytes or len(content) > limits["input"]:
        raise ValueError("Ingest input must be bounded immutable bytes")
    digest = hashlib.sha256(content).hexdigest()

    def check_deadline():
        if time.monotonic() >= deadline:
            raise IsolatedIngestDeadline("Isolated ingest deadline exceeded")

    with tempfile.TemporaryDirectory(prefix="axiom-ingest-") as private:
        snapshot = str(Path(private) / ("source" + suffix))
        result = str(Path(private) / "result.json")
        with open(snapshot, "xb") as target:
            os.chmod(snapshot, 0o600)
            target.write(content)
        check_deadline()
        if process:
            proc = _mp.get_context("spawn").Process(target=_child_entry, args=(snapshot, result, limits))
            try:
                proc.start()
                while proc.is_alive():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise IsolatedIngestDeadline("Isolated ingest deadline exceeded")
                    proc.join(min(remaining, 86400))
                if proc.exitcode != 0:
                    raise IsolatedIngestResourceError("Isolated ingest child exited abnormally")
            finally:
                if proc.pid is not None:
                    _stop_group(proc)
                proc.close()
        else:
            # Do not apply process-global rlimits/setsid in a service thread.
            from kernel.sidecar.ingestor import IngestorImpl
            chunks, doc, pages = IngestorImpl().ingest(snapshot)
            document = asdict(doc)
            document["ingested_at"] = doc.ingested_at.isoformat()
            _write_result(result, {"version": 1, "status": "ok", "document": document,
                                   "chunks": [asdict(c) for c in chunks],
                                   "pages": [asdict(p) for p in pages]}, limits["output"])
        check_deadline()
        graph = _validate(_read_result(result, limits["output"]), snapshot, digest, limits)
        check_deadline()
        chunks, doc, pages = graph
        return chunks, replace(doc, source_path=filepath), pages


def ingest_isolated(filepath: str, timeout: float) -> list[str]:
    """Compatibility API returning only text; use the full API for provenance."""
    chunks, _, _ = ingest_document_isolated(filepath, timeout)
    return [chunk.text for chunk in chunks]
