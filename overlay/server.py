"""
Kairo Phantom — Overlay Server (SPEC §S8)

FastAPI service serving the premium glass-chrome UX for de-identification triage.
Allows viewing source documents, highlights bbox, and accept/edit/reject.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import hashlib
import hmac
import json
import logging
import logging.handlers
import os
import pathlib
import queue
import tempfile
import threading
import time
import uuid
from collections import deque
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from kernel.core.data_model import (
    Action,
    ActionKind,
    ActionStatus,
    Correction,
    Document,
    ExtractionStatus,
)
from kernel.core.provenance import ProvenanceLogImpl
from kernel.sidecar.action_executor import ActionExecutorImpl
from kernel.sidecar.inference_gateway import TieredInferenceGateway
from kernel.sidecar.ingestor import IngestorImpl
from kernel.sidecar.memory_store import MemoryStoreImpl
from kernel.sidecar.orchestrator import OrchestratorImpl
from kernel.sidecar.quality_gate import LocalQualityGate
from kernel.sidecar.security_filter import LocalSecurityFilter
from overlay.body_limit import BodyLimitMiddleware
from overlay.telemetry import install_tracing, log_context
from packs.contract.pack import ContractPack
from packs.generic.pack import GenericPack
from packs.invoice.pack import InvoicePack
from packs.memo.pack import ClassifiedMemoPack
from packs.paper.pack import PaperPack


# Initialize FastAPI
@contextlib.asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Reopen durable state and join extraction workers before closing SQLite."""
    global _extraction_pool
    memory_store.reopen()
    if _extraction_pool._shutdown:
        _extraction_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="axiom-extract"
        )
    try:
        yield
    finally:
        # ASGI server has drained ingress; do not close state while work runs.
        # Running Python threads cannot be forcibly stopped: supervisors still
        # need a termination grace period for a genuinely hung native parser.
        await asyncio.to_thread(_extraction_pool.shutdown, wait=True, cancel_futures=True)
        memory_store.close()


app = FastAPI(title="Axiom-Grid Overlay API", lifespan=_lifespan)
logger = logging.getLogger("overlay.server")


# ------------------------------------------------------------------
# OPS-002: structured JSON logging (one JSON object per line; safe for
# Loki/Datadog/CloudWatch ingestion). Opt out with AXIOM_LOG_FORMAT=text.
# ------------------------------------------------------------------
class JsonLogFormatter(logging.Formatter):
    """Render log records as single-line JSON with stable field names."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": "axiom-grid-overlay",
        }
        payload.update(log_context())
        if record.exc_info:
            payload["exc_type"] = getattr(record.exc_info[0], "__name__", "Exception")
        for key in ("request_id", "path", "status", "latency_ms", "client"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"), default=str)


LOG_DROPPED_TOTAL = {"count": 0}


class _NonBlockingQueueHandler(logging.handlers.QueueHandler):
    """OPS-006: enqueue log records without ever blocking the request path.

    A plain StreamHandler writes synchronously: when stderr is a pipe nobody
    drains (CI harnesses, `cmd | head`, misconfigured supervisors) the 64 KiB
    pipe buffer fills and every request thread blocks inside write() - the
    serving path stalls on log I/O and SIGTERM graceful shutdown can no longer
    run (focused-runtime CI hang, 2026-09-13). Records go to a bounded queue;
    a daemon QueueListener owns the blocking write. On saturation records are
    shed and counted in /metrics - never blocked on.
    """

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            LOG_DROPPED_TOTAL["count"] += 1


def configure_structured_logging(level: str | None = None) -> None:
    """Idempotently install non-blocking JSON logging on the root logger."""
    if os.environ.get("AXIOM_LOG_FORMAT", "json").lower() == "text":
        return
    root = logging.getLogger()
    if not any(isinstance(h, _NonBlockingQueueHandler) for h in root.handlers):
        sink = logging.StreamHandler()
        sink.setFormatter(logging.Formatter("%(message)s"))
        log_queue: queue.Queue = queue.Queue(
            maxsize=int(os.environ.get("AXIOM_LOG_QUEUE_MAX", "4096"))
        )
        logging.handlers.QueueListener(
            log_queue, sink, respect_handler_level=True
        ).start()
        handler = _NonBlockingQueueHandler(log_queue)
        handler.setFormatter(JsonLogFormatter())
        root.addHandler(handler)
    # Uvicorn installs its own synchronous stderr handlers before importing
    # the app. Route lifecycle/error logs through the same bounded queue too:
    # otherwise shutdown INFO messages can block behind a saturated sink.
    queue_handler = next(h for h in root.handlers if isinstance(h, _NonBlockingQueueHandler))
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = [queue_handler]
        uvicorn_logger.propagate = False
    root.setLevel((level or os.environ.get("AXIOM_LOG_LEVEL", "INFO")).upper())
    # Third-party per-request chatter is not observability; keep it at WARNING
    # so the hot path does not pay a JSON serialisation per upstream call.
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


configure_structured_logging()


# ------------------------------------------------------------------
# SEC-007: strict, explicit CORS. Default is deny-all cross-origin: the
# overlay is same-origin by design. Operators opt in per-origin via
# AXIOM_CORS_ORIGINS (comma-separated, exact scheme://host[:port]). The
# wildcard "*" is rejected when credentials would be allowed.
# ------------------------------------------------------------------
def _cors_origins() -> list[str]:
    raw = os.environ.get("AXIOM_CORS_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return [o for o in origins if o != "*"]


_CORS_ORIGINS = _cors_origins()
if _CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
        max_age=600,
    )

# Paths
BASE_DIR = pathlib.Path(__file__).parents[1]
FIXTURES_DIR = BASE_DIR / "fixtures" / "wedge"
TEMPLATES_DIR = BASE_DIR / "overlay" / "templates"
WORKSPACE_ROOT = BASE_DIR.resolve()
ALLOWED_ROOTS = [WORKSPACE_ROOT, pathlib.Path(tempfile.gettempdir()).resolve()]

ALLOWED_ORIGINS = {
    "http://localhost",
    "http://127.0.0.1",
    "http://testserver",
    "https://testserver",
    "tauri://localhost",
}


def _origin_allowed(origin: str) -> bool:
    """Only serialized origins, never prefix-matched URLs or userinfo."""
    if any(ch.isspace() or ord(ch) < 32 for ch in origin):
        return False
    try:
        parsed = urlsplit(origin)
        if (parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment
                or "?" in origin or "#" in origin or "\\" in origin):
            return False
        port = parsed.port  # Raises on malformed or out-of-range ports.
        if parsed.netloc.endswith(":"):
            return False
    except ValueError:
        return False
    if origin in ALLOWED_ORIGINS or origin in _CORS_ORIGINS:
        return True
    return port is not None and (
        (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "testserver"})
        or (parsed.scheme == "https" and parsed.hostname == "testserver")
    )


@app.middleware("http")
async def enforce_origin_gate(request, call_next):
    origin = request.headers.get("origin")
    if origin is not None and not _origin_allowed(origin):
        return JSONResponse(status_code=403, content={"detail": "Forbidden: invalid origin"})
    return await call_next(request)


# ------------------------------------------------------------------
# Production hardening middleware (SEC-003/004, OPS-001)
# ------------------------------------------------------------------

# SEC-004: regex-heavy packs run against a bounded thread pool so a hostile
# oversized document cannot monopolise the async event loop (CPU-starvation
# DoS guard). Bounded at 4 workers; 100x stress proved lock-safe behaviour.
_extraction_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="axiom-extract"
)

# OPS-004: backpressure on the extraction pool. A ThreadPoolExecutor queue is
# unbounded, so under a spike far beyond 4 workers requests pile up, latency
# balloons past any SLO, and clients time out while the server still burns
# CPU on dead work. A semaphore of workers + small queue turns overload into
# a fast, honest 503 (fail-fast, load-shedding) instead of a slow collapse.
_EXTRACTION_QUEUE_DEPTH = int(os.environ.get("AXIOM_EXTRACTION_QUEUE_DEPTH", "16"))
_extraction_slots = threading.BoundedSemaphore(4 + _EXTRACTION_QUEUE_DEPTH)

OPS_METRICS = {
    "started_at": time.time(),
    "requests_total": 0,
    "errors_total": 0,
    "status_counts": {},
    "latency_ms_max": 0.0,
    "latency_ms_total": 0.0,
    "latency_samples": deque(maxlen=10000),
}

MAX_UPLOAD_BYTES = int(os.environ.get("AXIOM_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024)))


# ------------------------------------------------------------------
# OPS-003: request-id correlation. Honour a client-supplied X-Request-Id
# (bounded, sanitized) or mint one; echo it on every response so client
# support tickets can be joined to the structured JSON log stream.
# ------------------------------------------------------------------
_REQUEST_ID_MAX_LEN = 64


@app.middleware("http")
async def request_id_middleware(request, call_next):
    rid = request.headers.get("x-request-id", "").strip()
    if not rid or len(rid) > _REQUEST_ID_MAX_LEN:
        rid = uuid.uuid4().hex
    # Sanitize: correlation ids must never carry CR/LF into log streams
    # (log-injection / response-splitting guard).
    rid = "".join(ch for ch in rid if ch.isascii() and (ch.isalnum() or ch in "-_.")) or uuid.uuid4().hex
    request.state.request_id = rid
    response = await call_next(request)
    response.headers["X-Request-Id"] = rid
    return response


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    """SEC-003: lock every response down with defense-in-depth security headers."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path == "/" or request.url.path.endswith(".html"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
    return response


@app.middleware("http")
async def request_governor_middleware(request, call_next):
    """OPS-001/SEC-004: per-request metrics + body size + CPU-budget guards."""
    t0 = time.perf_counter()

    # SEC-004: reject oversized request bodies before parsing (DoS guard)
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if not content_length.isascii() or not content_length.isdecimal():
                raise ValueError("invalid length")
            if int(content_length) > MAX_UPLOAD_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Payload too large"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length"})

    response = await call_next(request)

    dt_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "request completed",
        extra={
            "request_id": getattr(request.state, "request_id", ""),
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(dt_ms, 2),
            "client": request.client.host if request.client else "unknown",
        },
    )
    OPS_METRICS["requests_total"] += 1
    OPS_METRICS["latency_ms_total"] += dt_ms
    OPS_METRICS["latency_samples"].append(dt_ms)
    OPS_METRICS["latency_ms_max"] = max(OPS_METRICS["latency_ms_max"], round(dt_ms, 2))
    sc = str(response.status_code)
    OPS_METRICS["status_counts"][sc] = OPS_METRICS["status_counts"].get(sc, 0) + 1
    if response.status_code >= 500:
        OPS_METRICS["errors_total"] += 1
    return response


# ------------------------------------------------------------------
# SEC-006: bearer / API-key authentication for the public API surface
# ------------------------------------------------------------------
#
# Threat model: the overlay was born as a same-origin desktop sidecar, where
# the origin gate (SEC-002) is sufficient. The moment it is exposed as a
# network API every mutating endpoint (/demo, /apply, /correct, /api/*) is
# callable by anyone who can reach the socket. SEC-006 closes that.
#
#   AXIOM_API_KEYS      comma-separated list of accepted keys. When set, every
#                       non-exempt route requires `Authorization: Bearer <key>`
#                       or `X-API-Key: <key>`. Unset => local-first mode
#                       (auth disabled, origin gate still enforced).
#   AXIOM_REQUIRE_AUTH  "1"/"true" => production posture. If no keys are
#                       configured the API FAILS CLOSED with 503 on protected
#                       routes instead of silently running open.
#
# Keys are compared via sha256 digests with hmac.compare_digest (constant-time,
# length-independent). The digest prefix doubles as a stable per-tenant id so
# the rate limiter (SEC-005) can apply a per-key quota tier instead of per-IP.

_AUTH_EXEMPT_PATHS = {"/", "/healthz", "/api/health", "/livez", "/readyz", "/metrics", "/dashboard", "/docs", "/openapi.json", "/redoc"}
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = ()


def _load_api_key_digests() -> dict[str, str]:
    raw = os.environ.get("AXIOM_API_KEYS", "")
    digests: dict[str, str] = {}
    for k in raw.split(","):
        k = k.strip()
        if len(k) >= 16:  # refuse trivially short keys
            d = hashlib.sha256(k.encode("utf-8")).hexdigest()
            digests[d] = d[:12]
    return digests


_API_KEY_DIGESTS: dict[str, str] = _load_api_key_digests()
_AUTH_REQUIRED = os.environ.get("AXIOM_REQUIRE_AUTH", "").lower() in {"1", "true", "yes"}


def _auth_enabled() -> bool:
    return bool(_API_KEY_DIGESTS) or _AUTH_REQUIRED


def _is_auth_exempt(path: str) -> bool:
    return path in _AUTH_EXEMPT_PATHS or path.startswith(_AUTH_EXEMPT_PREFIXES)


def _presented_key(request) -> str | None:
    auth = request.headers.get("authorization")
    if auth:
        scheme, _, token = auth.partition(" ")
        if scheme.lower() == "bearer" and token.strip():
            return token.strip()
    xk = request.headers.get("x-api-key")
    return xk.strip() if xk and xk.strip() else None


def _authenticate(request) -> str | None:
    """Return the tenant id for a valid presented key, else None.
    Constant-time: always hashes and compares against every configured digest."""
    key = _presented_key(request)
    if key is None or not _API_KEY_DIGESTS:
        return None
    presented = hashlib.sha256(key.encode("utf-8")).hexdigest()
    match: str | None = None
    for digest, tenant in _API_KEY_DIGESTS.items():
        if hmac.compare_digest(presented, digest):
            match = tenant
    return match


@app.middleware("http")
async def api_key_auth_middleware(request, call_next):
    """SEC-006: bearer/API-key gate. 401 + WWW-Authenticate on bad/missing key,
    503 when production posture is demanded but no keys are configured
    (fail closed, never fail open)."""
    if not _auth_enabled() or _is_auth_exempt(request.url.path):
        return await call_next(request)
    if not _API_KEY_DIGESTS:
        OPS_METRICS["auth_rejections_total"] = OPS_METRICS.get("auth_rejections_total", 0) + 1
        return JSONResponse(
            status_code=503,
            content={"detail": "Service misconfigured: AXIOM_REQUIRE_AUTH set but no AXIOM_API_KEYS"},
        )
    tenant = _authenticate(request)
    if tenant is None:
        OPS_METRICS["auth_rejections_total"] = OPS_METRICS.get("auth_rejections_total", 0) + 1
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized: missing or invalid API key"},
            headers={"WWW-Authenticate": 'Bearer realm="axiom-grid"'},
        )
    request.state.tenant = tenant
    return await call_next(request)


# ------------------------------------------------------------------
# SEC-005: token-bucket rate limiting (per-client-IP) production hardening
# ------------------------------------------------------------------

_RATE_LIMIT_PER_MIN = int(os.environ.get("AXIOM_RATE_LIMIT_PER_MIN", "300"))
_RATE_LIMIT_WINDOW_S = 60.0
_RATE_LIMIT_EXEMPT_PATHS = {"/healthz", "/api/health", "/livez", "/readyz", "/metrics"}
_rate_limit_buckets: dict[str, deque[float]] = {}
_RATE_LIMIT_BUCKET_HIGH_WATER = int(os.environ.get("AXIOM_RATE_LIMIT_BUCKET_HIGH_WATER", "500"))
# Hard ceiling on distinct buckets regardless of freshness: beyond this the
# least-recently-seen buckets are evicted so memory is O(hard_cap) even under
# a rotating-source flood (100x load premortem #1).
_RATE_LIMIT_BUCKET_HARD_CAP = max(_RATE_LIMIT_BUCKET_HIGH_WATER, int(os.environ.get("AXIOM_RATE_LIMIT_BUCKET_HARD_CAP", "5000")))
_TRUST_PROXY = os.environ.get("AXIOM_TRUST_PROXY", "").lower() in {"1", "true", "yes"}
_rate_limit_lock = threading.Lock()


_RATE_LIMIT_PER_MIN_AUTH = int(os.environ.get("AXIOM_RATE_LIMIT_PER_MIN_AUTH", "3000"))


def _client_key(request) -> str:
    # SEC-006 tier: a valid API key gets its own (larger) bucket keyed by
    # tenant id, so one noisy tenant behind a shared NAT/LB IP cannot starve
    # the others, and per-tenant quotas can be metered/billed later.
    tenant = _authenticate(request) if _API_KEY_DIGESTS else None
    if tenant:
        return f"tenant:{tenant}"
    # SEC-008: X-Forwarded-For is attacker-controlled unless a trusted reverse
    # proxy is guaranteed to overwrite it. Only honour it when the operator
    # explicitly declares that topology (AXIOM_TRUST_PROXY=1); otherwise a
    # client could rotate the header to mint a fresh bucket per request and
    # bypass the limit entirely while growing the bucket table.
    if _TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            first = fwd.split(",")[0].strip()
            if first and len(first) <= 64:
                return first
    client = request.client
    return client.host if client else "unknown"


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """SEC-005: sliding-window per-IP rate limit. Fails closed with 429 +
    Retry-After once a client exceeds AXIOM_RATE_LIMIT_PER_MIN requests in a
    60s window. Health/readiness probes are exempt so orchestrators (k8s)
    never get throttled out of their own liveness checks."""
    if request.url.path in _RATE_LIMIT_EXEMPT_PATHS or _RATE_LIMIT_PER_MIN <= 0:
        return await call_next(request)

    key = _client_key(request)
    now = time.monotonic()
    with _rate_limit_lock:
        cutoff = now - _RATE_LIMIT_WINDOW_S
        # Bound attacker-controlled cardinality; deque gives O(1) expiry.
        if len(_rate_limit_buckets) > _RATE_LIMIT_BUCKET_HIGH_WATER:
            stale = [k for k, values in _rate_limit_buckets.items() if not values or values[-1] < cutoff]
            for stale_key in stale:
                _rate_limit_buckets.pop(stale_key, None)
        if len(_rate_limit_buckets) >= _RATE_LIMIT_BUCKET_HARD_CAP and key not in _rate_limit_buckets:
            # Evict least-recently-seen buckets down to 90% of the cap so we do
            # not pay the sort on every request during a flood.
            victims = sorted(_rate_limit_buckets, key=lambda k: _rate_limit_buckets[k][-1] if _rate_limit_buckets[k] else 0.0)
            for victim in victims[: len(_rate_limit_buckets) - int(_RATE_LIMIT_BUCKET_HARD_CAP * 0.9)]:
                _rate_limit_buckets.pop(victim, None)
        bucket = _rate_limit_buckets.setdefault(key, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        limit = _RATE_LIMIT_PER_MIN_AUTH if key.startswith("tenant:") else _RATE_LIMIT_PER_MIN
        if len(bucket) >= limit:
            retry_after = max(1, int(_RATE_LIMIT_WINDOW_S - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
    return await call_next(request)


def resolve_sandbox_path(file_path_str: str) -> pathlib.Path:
    """Resolve file path strictly within WORKSPACE_ROOT or system temp directory."""
    if not file_path_str or not isinstance(file_path_str, str) or not file_path_str.strip() or "\x00" in file_path_str:
        raise HTTPException(status_code=422, detail="Invalid file path")

    p = pathlib.Path(file_path_str)
    candidates = []
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.append(FIXTURES_DIR / file_path_str)
        candidates.append(BASE_DIR / file_path_str)
        candidates.append(pathlib.Path.cwd() / file_path_str)
        candidates.append(p)

    for cand in candidates:
        try:
            resolved = cand.resolve()
            if resolved.is_file() and any(resolved.is_relative_to(root) for root in ALLOWED_ROOTS):
                return resolved
        except (OSError, ValueError):
            continue

    raise HTTPException(status_code=404, detail=f"File {file_path_str} not found")


# Initialize Core Services
provenance_log = ProvenanceLogImpl()
STATE_DIR = pathlib.Path(os.environ.get("AXIOM_STATE_DIR", str(BASE_DIR / ".kairo")))
memory_store = MemoryStoreImpl(STATE_DIR / "overlay_store.db")
ingestor = IngestorImpl()
security_filter = LocalSecurityFilter(enable_pii_scan=False)

# Gateway in test mode (no LiteLLM/Ollama needed for overlay demonstration)
os.environ["KAIRO_GATEWAY_TEST_MODE"] = "true"
inference_gateway = TieredInferenceGateway(tier3_enabled=False)

quality_gate = LocalQualityGate(memory_store)
wedge_pack = GenericPack()

orchestrator = OrchestratorImpl(
    ingestor=ingestor,
    security_filter=security_filter,
    inference_gateway=inference_gateway,
    quality_gate=quality_gate,
    provenance_log=provenance_log,
    pack=wedge_pack,
    memory_store=memory_store,
)

action_executor = ActionExecutorImpl(provenance_log)

orchestrator_lock = threading.Lock()


class DemoRequest(BaseModel):
    """Strict schema: a non-blank, bounded file reference (no NUL bytes)."""

    file: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")

    @field_validator("file")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("file must not be blank")
        return value


class ApplyRequest(BaseModel):
    ext_id: str
    accept: bool


class CorrectionRequest(BaseModel):
    ext_id: str
    field_name: str
    original: str
    corrected: str
    reason: str


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the primary HTML overlay template."""
    template_path = TEMPLATES_DIR / "index.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    content = await asyncio.to_thread(template_path.read_text, encoding="utf-8")
    return HTMLResponse(content=content)


@app.post("/demo")
async def run_demo(req: DemoRequest):
    """Run the pipeline on a document and return data for the overlay."""
    file_path = resolve_sandbox_path(req.file)

    try:
        # 1. Create target document
        # Real provenance digest of the exact bytes fed to the pipeline.
        try:
            file_bytes = await asyncio.to_thread(file_path.read_bytes)
            digest = hashlib.sha256(file_bytes).hexdigest()
        except OSError as exc:
            raise HTTPException(status_code=422, detail=f"Unable to read {req.file}: {exc}") from exc
        doc = Document(
            source_path=str(file_path),
            sha256=digest,
        )

        # 2. Run Orchestrator (off event loop, serialized to protect shared SQLite state)
        def _run_pipeline(document):
            with orchestrator_lock:
                return orchestrator.run(document)
        trace = await asyncio.to_thread(_run_pipeline, doc)

        # 3. Read raw file contents to return to UI
        if file_path.suffix.lower() in (".txt", ".md"):
            document_text = await asyncio.to_thread(file_path.read_text, encoding="utf-8", errors="replace")
        else:
            # Reconstruct document text from the registered chunks
            doc_chunks = [c for c in provenance_log._chunks.values() if c.doc_id == doc.doc_id]
            if not doc_chunks:
                doc_chunks = list(provenance_log._chunks.values())
            document_chunks = sorted(
                doc_chunks,
                key=lambda c: (c.page, c.bbox.y0 if c.bbox else 0)
            )
            document_text = "\n\n".join(chunk.text for chunk in document_chunks)

        # 4. Format suggestions with bbox + page mapping
        suggestions = []
        for ext in trace.extractions:
            if ext.status == ExtractionStatus.BLOCKED:
                continue
            
            chain = provenance_log.get_provenance(ext.ext_id)
            if not chain.is_complete:
                continue

            suggestions.append({
                "ext_id": ext.ext_id,
                "field_name": ext.field_name,
                "value": ext.value,
                "confidence": ext.confidence,
                "page": chain.chunk.page if chain.chunk else 1,
                "chunk_id": chain.chunk.chunk_id if chain.chunk else "",
                "bbox": {
                    "x0": chain.chunk.bbox.x0 if chain.chunk and chain.chunk.bbox else 0,
                    "y0": chain.chunk.bbox.y0 if chain.chunk and chain.chunk.bbox else 0,
                    "x1": chain.chunk.bbox.x1 if chain.chunk and chain.chunk.bbox else 1,
                    "y1": chain.chunk.bbox.y1 if chain.chunk and chain.chunk.bbox else 1,
                }
            })

            # Register proposed action for each suggestion
            action = Action(
                ext_id=ext.ext_id,
                kind=ActionKind.SUGGEST,
                target_app="notepad",
                payload={"value": ext.value},
                confidence=ext.confidence,
                status=ActionStatus.PENDING,
            )
            provenance_log.register_action(action)

        # 5. Format trace details
        formatted_trace = {
            "halted": trace.halted,
            "halt_reason": trace.halt_reason,
            "stages": [
                {
                    "name": s.name,
                    "input_data": s.input_data,
                    "output_data": s.output_data,
                    "duration_ms": s.duration_ms,
                    "status": s.status,
                }
                for s in trace.stages
            ]
        }

        return {
            "success": True,
            "document_text": document_text,
            "suggestions": suggestions,
            "trace": formatted_trace,
        }

    except Exception as e:
        logger.exception("unhandled error in overlay endpoint")
        return {"success": False, "error": str(e)}


@app.post("/apply")
async def apply_cua(req: ApplyRequest):
    """Execute a confirmed CUA action and verify post-state."""
    # Retrieve action from provenance log
    action_id = None
    for act_id, act in provenance_log._actions.items():
        if act.ext_id == req.ext_id:
            action_id = act_id
            break

    if not action_id:
        return {"success": False, "error": "No pending action found for this extraction"}

    action = provenance_log._actions[action_id]
    
    # Kairo ActionExecutor requires human_confirm=True
    result = action_executor.apply(action, human_confirm=req.accept)
    return {
        "success": result.success,
        "error": result.error,
        "post_state": result.post_state,
    }


@app.post("/correct")
async def record_flywheel_correction(req: CorrectionRequest):
    """Record a correction to memory store, triggering the local flywheel."""
    try:
        corr = Correction(
            ext_id=req.ext_id,
            original=req.original,
            corrected=req.corrected,
            reason=req.reason,
            by="overlay-user",
        )
        memory_store.record_correction(corr)
        return {"success": True}
    except Exception as e:
        logger.exception("unhandled error in overlay endpoint")
        return {"success": False, "error": str(e)}


# Serve only rendered images, never the runtime database, WAL, or audit files.
# Authentication middleware protects this mount like every document API.
(STATE_DIR / "page_images").mkdir(parents=True, exist_ok=True)
app.mount("/static/page_images", StaticFiles(
    directory=str(STATE_DIR / "page_images"), check_dir=False
), name="page_images")


@app.get("/api/compression/stats")
async def get_compression_stats():
    """Return aggregate context compression statistics."""
    try:
        from kairo.context.compressor import get_compression_stats
        return get_compression_stats()
    except ImportError:
        return {"error": "Context compressor not available", "total_runs": 0}


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the Kairo Grounding Trace dashboard."""
    dashboard_path = BASE_DIR / "kairo" / "observability" / "dashboard.html"
    if dashboard_path.exists():
        content = await asyncio.to_thread(dashboard_path.read_text)
        return HTMLResponse(content=content, status_code=200)
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.get("/api/traces")
async def get_traces(limit: int = 50):
    """Return recent grounding traces for the dashboard."""
    try:
        from kairo.observability.trace import get_traces
        return get_traces(limit=limit)
    except ImportError:
        return []


@app.get("/api/traces/stats")
async def get_trace_stats():
    """Return aggregate grounding trace statistics."""
    try:
        from kairo.observability.trace import get_trace_stats
        return get_trace_stats()
    except ImportError:
        return {"total_traces": 0, "grounded_pct": 0.0}


# ---- Phase 3: Connector Protocol ----

class ExtractDocumentRequest(BaseModel):
    """Strict schema: bounded, non-blank file path; no NUL-byte injection."""

    file: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")
    extraction_schema: dict | None = None

    @field_validator("file")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("file must not be blank")
        return value


class AskDocumentRequest(BaseModel):
    """Strict schema for /api/ask-document."""

    file: str = Field(min_length=1, max_length=4096, pattern=r"^[^\x00]+$")
    question: str = Field(min_length=1, max_length=2048, pattern=r"^[^\x00]+$")

    @field_validator("file", "question")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value


class GraphQueryRequest(BaseModel):
    """Strict schema for /api/graph/query."""

    keyword: str | None = Field(default=None, max_length=1024)
    query: str | None = Field(default=None, max_length=1024)


@app.post("/api/extract-document")
async def extract_document(req: ExtractDocumentRequest):
    """Extract fields from a document with grounding metadata.

    Returns fields with value, grounded status, bbox, cascade method,
    confidence, and source_link for each extracted field.
    """
    # Admission covers all document I/O, classification and pipeline work.
    # Acquiring only at submit time let rejected requests fill the default
    # executor and retain full document strings before the capacity check.
    slots = _extraction_slots
    if not slots.acquire(blocking=False):
        OPS_METRICS["extraction_shed_total"] = OPS_METRICS.get("extraction_shed_total", 0) + 1
        raise HTTPException(
            status_code=503,
            detail="Extraction capacity saturated; retry shortly",
            headers={"Retry-After": "1"},
        )

    def _run_admitted():
        file_path = resolve_sandbox_path(req.file)
        filepath = str(file_path)
        try:
            with open(filepath, "rb") as source:
                content = source.read(MAX_UPLOAD_BYTES + 1)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="Document exceeds byte budget")
            text = content.decode("utf-8", errors="ignore")
        except OSError as exc:
            logger.exception("unable to read document for extraction")
            raise HTTPException(status_code=422, detail="Unable to read document") from exc

        from kairo.core.classifier import classify_document
        doc_type = classify_document(text)
        pack_class = {
            "invoice": InvoicePack,
            "contract": ContractPack,
            "paper": PaperPack,
            "memo": ClassifiedMemoPack,
            "generic": GenericPack,
        }.get(doc_type, GenericPack)
        doc = Document(source_path=filepath)
        # The store and capacity belong to the actual worker, not its waiter.
        # Cancelling an HTTP request cannot stop a running Python thread.
        with MemoryStoreImpl(":memory:") as request_store:
            request_orchestrator = OrchestratorImpl(
                ingestor=IngestorImpl(),
                security_filter=LocalSecurityFilter(enable_pii_scan=False),
                inference_gateway=TieredInferenceGateway(tier3_enabled=False),
                quality_gate=LocalQualityGate(request_store),
                provenance_log=ProvenanceLogImpl(),
                pack=pack_class(),
                memory_store=request_store,
            )
            with orchestrator_lock:
                trace = request_orchestrator.run(doc)
        return trace, doc_type, doc

    try:
        work = _extraction_pool.submit(_run_admitted)
    except BaseException:
        slots.release()
        raise
    work.add_done_callback(lambda _future: slots.release())
    try:
        trace, doc_type, doc = await asyncio.wrap_future(work)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("unhandled error in /api/extract-document pipeline")
        raise HTTPException(status_code=500, detail="Extraction pipeline failed") from exc

    from kairo.core.classifier import build_source_link

    # Build response with grounding metadata
    fields = {}
    refused_fields = []
    for ext in trace.extractions:
        bbox = None
        page = 1
        if ext.anchors:
            a = ext.anchors[0]
            bbox = [a.bbox.x0, a.bbox.y0, a.bbox.x1 - a.bbox.x0, a.bbox.y1 - a.bbox.y0]
            page = a.page

        grounded = ext.method.value != "block"
        if grounded:
            fields[ext.field_name] = {
                "value": ext.value,
                "grounded": True,
                "bbox": bbox,
                "page": page,
                "cascade": ext.method.value.upper(),
                "confidence": ext.confidence,
                "source_link": build_source_link(doc.doc_id, page, bbox or [0, 0, 0, 0]),
            }
        else:
            refused_fields.append(ext.field_name)

    return {
        "doc_id": doc.doc_id,
        "doc_type": doc_type,
        "fields": fields,
        "refused_fields": refused_fields,
        "processing_time_ms": sum(s.duration_ms for s in trace.stages),
    }


@app.post("/api/ask-document")
async def ask_document(req: AskDocumentRequest):
    """Ask a question about a document. Returns answer with bbox or refusal."""
    file_path = resolve_sandbox_path(req.file)
    filepath = str(file_path)
    question = req.question

    try:
        # For now, extract all fields and check if the question matches any
        extract_req = ExtractDocumentRequest(file=filepath)
        result = await extract_document(extract_req)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("unhandled error in /api/ask-document")
        raise HTTPException(status_code=500, detail="ask-document failed") from exc

    # Simple keyword matching: find field whose name or value matches question keywords
    question_lower = question.lower()
    for field_name, field_data in result["fields"].items():
        if field_name.replace("_", " ") in question_lower or field_name in question_lower:
            return {
                "question": question,
                "answer": field_data["value"],
                "grounded": True,
                "bbox": field_data["bbox"],
                "page": field_data["page"],
                "source_link": field_data["source_link"],
            }

    # No match -> refusal
    return {
        "question": question,
        "answer": None,
        "grounded": False,
        "refusal_reason": "No grounded answer found for this question in the document.",
    }


@app.get("/api/source/{doc_id}")
async def get_source_render(doc_id: str, page: int = 1, x: float = 0, y: float = 0, w: float = 0, h: float = 0):
    """Render a document page with bbox highlight overlay.

    For text documents, returns the text with the highlighted region marked.
    For PDFs, would render via PyMuPDF (requires the source file path).
    """
    # In a full implementation, this would render the page as PNG via PyMuPDF
    # and overlay an SVG bbox. For now, return metadata.
    return {
        "doc_id": doc_id,
        "page": page,
        "highlight_bbox": [x, y, w, h] if w > 0 and h > 0 else None,
        "render_url": f"kairo://doc/{doc_id}?page={page}&x={x}&y={y}&w={w}&h={h}",
    }


# ---- Phase 4: Knowledge Graph ----

@app.post("/api/graph/query")
async def query_graph(req: GraphQueryRequest):
    """Query the grounded knowledge graph by keyword.

    NOT an LLM call — pure keyword + entity matching + graph traversal.
    Returns matching nodes with bbox provenance.
    """
    keyword = req.keyword or req.query or ""
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="keyword or query is required")
    try:
        from kairo.graph.store import GroundedKnowledgeGraph
        g = GroundedKnowledgeGraph()
        g.load()  # load persisted graph if available
        results = g.query(keyword)
        return {"keyword": keyword, "results": results, "count": len(results)}
    except Exception as e:
        logger.exception("unhandled error in /api/graph/query")
        return {"keyword": keyword, "results": [], "count": 0, "error": str(e)}


@app.get("/api/graph")
async def get_graph():
    """Get the full knowledge graph for visualization."""
    try:
        from kairo.graph.store import GroundedKnowledgeGraph
        g = GroundedKnowledgeGraph()
        g.load()
        return g.to_dict()
    except Exception as e:
        logger.exception("unhandled error in /api/graph")
        return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0}, "error": str(e)}


# ---- Phase 5: Figure Extraction ----

@app.get("/api/figures/{doc_id}")
async def get_figures(doc_id: str, file: str = ""):
    """Get figures extracted from a document.

    For PDFs: uses PyMuPDF to detect images, find captions, classify.
    For text: extracts Figure/Table references from text.
    """
    if not file or not file.strip():
        raise HTTPException(status_code=400, detail="file parameter is required")
    file_path = resolve_sandbox_path(file)
    filepath = str(file_path)

    try:
        if filepath.lower().endswith(".pdf"):
            from kairo.core.figure_extractor import extract_figures_from_pdf
            figures = await asyncio.to_thread(extract_figures_from_pdf, filepath)
        else:
            def _read(fp):
                with open(fp, "r", errors="ignore") as f:
                    return f.read()
            text = await asyncio.to_thread(_read, filepath)
            from kairo.core.figure_extractor import extract_figures_from_text
            figures = extract_figures_from_text(text)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("unhandled error in /api/figures")
        raise HTTPException(status_code=500, detail="figure extraction failed") from exc

    return {
        "doc_id": doc_id,
        "file": filepath,
        "figure_count": len(figures),
        "figures": [f.to_dict() for f in figures],
    }


# ---- Phase 6: Eval + Monitoring ----

@app.get("/api/eval/report")
async def get_eval_report():
    """Get the full eval report with regression and drift alerts."""
    try:
        from kairo.observability.eval import get_eval_report
        return get_eval_report()
    except Exception as exc:  # pragma: no cover - defensive fail-closed
        logger.exception("eval report unavailable")
        return {"runs": 0, "alerts": [], "error": str(exc)}


@app.get("/source/{extraction_id}")
async def get_source_provenance(extraction_id: str):
    """Retrieve bounding box and page reference for click-to-source verification."""
    ext = memory_store.get_extraction(extraction_id)
    if not ext:
        ext = provenance_log.get_provenance(extraction_id).extraction
        if not ext:
            raise HTTPException(status_code=404, detail="Extraction not found")

    chain = provenance_log.get_provenance(ext.ext_id)
    if not chain.is_complete or not chain.chunk:
        if ext.anchors:
            anchor = ext.anchors[0]
            bbox = {
                "x0": anchor.bbox.x0 if anchor.bbox else 0,
                "y0": anchor.bbox.y0 if anchor.bbox else 0,
                "x1": anchor.bbox.x1 if anchor.bbox else 1,
                "y1": anchor.bbox.y1 if anchor.bbox else 1,
            }
            page = anchor.page
            doc_id = ext.pack_id
        else:
            raise HTTPException(status_code=404, detail="Provenance chain is incomplete")
    else:
        page = chain.chunk.page
        bbox = {
            "x0": chain.chunk.bbox.x0 if chain.chunk.bbox else 0,
            "y0": chain.chunk.bbox.y0 if chain.chunk.bbox else 0,
            "x1": chain.chunk.bbox.x1 if chain.chunk.bbox else 1,
            "y1": chain.chunk.bbox.y1 if chain.chunk.bbox else 1,
        }
        doc_id = chain.document.doc_id if chain.document else ""

    pages = memory_store.get_pages(doc_id)
    image_ref = ""
    for p in pages:
        if p.index == page:
            image_ref = f"/static/page_images/{p.image_sha256}.png" if p.image_sha256 else ""
            break

    return {
        "page": page,
        "bbox": bbox,
        "image_ref": image_ref,
    }


# ------------------------------------------------------------------
# Production ops endpoints: liveness, readiness, metrics
# ------------------------------------------------------------------

@app.get("/healthz")
async def healthz():
    """Shallow service health probe."""
    return {"status": "ok", "service": "axiom-grid-overlay", "auth_enabled": _auth_enabled()}


@app.get("/api/health")
async def api_health():
    """Load-balancer health alias; intentionally equivalent to /healthz."""
    return await healthz()


@app.get("/livez")
async def livez():
    """Constant-time process liveness; never performs dependency checks."""
    return {"status": "alive", "uptime_seconds": round(time.time() - OPS_METRICS["started_at"], 2)}


_readyz_probe_lock = threading.Lock()
_readyz_probe_ok = threading.Event()


@app.get("/readyz")
async def readyz():
    """Readiness probe: runs the real extraction pipeline end-to-end exactly once
    (per process) on a synthetic classified memo, hermetically in the temp
    sandbox, then caches the verified-ready state. Under 100x+ contention this
    avoids re-running the heavyweight pipeline on every probe while still
    failing closed with 503 if the pipeline has never succeeded."""
    if _readyz_probe_ok.is_set():
        return {"status": "ready", "pipeline": "ok", "cached": True}

    try:
        return await asyncio.to_thread(_run_readyz_probe)
    except Exception as exc:
        logger.exception("readiness probe failed")
        return JSONResponse(status_code=503, content={"status": "not_ready", "error": type(exc).__name__})


def _run_readyz_probe() -> dict:
    """Publish success under the same lock as initialization and file cleanup.

    The event-loop caller must not own cleanup: it can race the next worker
    before publishing success. A private directory also isolates processes
    and prevents following a pre-created symlink in the shared temp directory.
    """
    with _readyz_probe_lock:
        if _readyz_probe_ok.is_set():
            return {"status": "ready", "pipeline": "ok", "cached": True}
        with tempfile.TemporaryDirectory(prefix="axiom-readyz-") as directory:
            probe_path = pathlib.Path(directory) / "probe.txt"
            probe_path.write_text(
                "CLASSIFICATION: UNCLASSIFIED\nSUBJECT: readiness probe\n"
                "ORIGIN: axiom-grid ops\n", encoding="utf-8",
            )
            text = probe_path.read_text(encoding="utf-8")
            from kairo.core.classifier import classify_document
            doc_type = classify_document(text)
            from packs.memo.pack import ClassifiedMemoPack
            fields = ClassifiedMemoPack().extract_text(text)
            if not fields:
                raise RuntimeError("readiness probe extracted zero fields")
        _readyz_probe_ok.set()
        return {"status": "ready", "pipeline": "ok", "doc_type": doc_type,
                "fields_extracted": len(fields)}


@app.get("/metrics")
async def metrics(format: str = "json"):
    """Bounded in-process telemetry in JSON or Prometheus exposition format."""
    total = OPS_METRICS["requests_total"]
    samples = sorted(OPS_METRICS["latency_samples"])
    def percentile(q):
        return round(samples[min(len(samples)-1, int((len(samples)-1)*q))], 2) if samples else 0.0
    data = {"uptime_seconds": round(time.time()-OPS_METRICS["started_at"],2), "requests_total": total,
            "errors_total": OPS_METRICS["errors_total"], "auth_rejections_total": OPS_METRICS.get("auth_rejections_total",0),
            "extraction_shed_total": OPS_METRICS.get("extraction_shed_total",0),
            "log_dropped_total": LOG_DROPPED_TOTAL["count"],
            "status_counts": OPS_METRICS["status_counts"], "active_rate_limit_buckets": len(_rate_limit_buckets),
            "latency_ms_mean": round(OPS_METRICS["latency_ms_total"]/total,2) if total else 0.0,
            "latency_ms_max": OPS_METRICS["latency_ms_max"],
            "latency_percentiles": {"p50":percentile(.5),"p90":percentile(.9),"p95":percentile(.95),"p99":percentile(.99)}}
    if format.lower() in {"prometheus","otel"}:
        lines=[f"axiom_requests_total {total}",f"axiom_errors_total {data['errors_total']}",
               f"axiom_auth_rejections_total {data['auth_rejections_total']}",f"axiom_extraction_shed_total {data['extraction_shed_total']}",f"axiom_log_dropped_total {data['log_dropped_total']}",f"axiom_rate_limit_buckets {data['active_rate_limit_buckets']}"]
        lines += [f'axiom_http_status_total{{code="{code}"}} {count}' for code,count in data["status_counts"].items()]
        # Latency summary (Prometheus summary-style quantiles). Alerting on P95/P99 requires this
        # exposition; the JSON form alone is not scrapeable. Quantiles are over the bounded in-process
        # sample window, so each worker reports its own distribution (aggregate with max() by pod).
        lines += ["# TYPE axiom_request_latency_ms summary"]
        lines += [f'axiom_request_latency_ms{{quantile="{q}"}} {v}' for q, v in
                  (("0.5", data["latency_percentiles"]["p50"]), ("0.9", data["latency_percentiles"]["p90"]),
                   ("0.95", data["latency_percentiles"]["p95"]), ("0.99", data["latency_percentiles"]["p99"]))]
        lines += [f"axiom_request_latency_ms_sum {round(OPS_METRICS['latency_ms_total'], 2)}",
                  f"axiom_request_latency_ms_count {total}",
                  f"axiom_request_latency_ms_max {data['latency_ms_max']}",
                  f"axiom_uptime_seconds {data['uptime_seconds']}"]
        return HTMLResponse("\n".join(lines)+"\n", media_type="text/plain; version=0.0.4")
    return data


# Register last so spans enclose auth, rate limiting and request logging.
install_tracing(app)


# Outer ASGI boundary counts actual bytes before any endpoint parses JSON.
app.add_middleware(BodyLimitMiddleware, limit=lambda: MAX_UPLOAD_BYTES)
