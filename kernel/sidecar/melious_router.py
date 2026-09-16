"""Resilient Melious multi-model router. Credentials are read at call time only."""
from __future__ import annotations

import contextlib
import json
import math
import os
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib import error, request


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: float = 15.0
    failures: int = 0
    opened_at: float | None = None
    probing: bool = False
    generation: int = 0
    def allow(self, now: float) -> bool:
        """CLOSED -> True. OPEN -> False. HALF_OPEN -> exactly one caller is
        admitted as the probe; concurrent callers keep failing fast so a
        recovering upstream is not stampeded (100x-load premortem #4)."""
        if self.opened_at is None: return True
        if now - self.opened_at < self.recovery_seconds or self.probing: return False
        self.probing = True; return True
    def success(self, generation: int | None = None) -> None:
        # Only responses admitted in this circuit epoch may change its state.
        # In particular, pre-outage successes cannot close OPEN/HALF_OPEN.
        if generation is not None and generation != self.generation:
            return
        if self.opened_at is not None:
            self.generation += 1
        self.failures, self.opened_at, self.probing = 0, None, False

    def failure(self, now: float, generation: int | None = None) -> None:
        if generation is not None and generation != self.generation:
            return
        self.failures += 1
        self.probing = False
        if self.failures >= self.failure_threshold:
            self.opened_at = now
            self.generation += 1
    @property
    def state(self) -> str:
        if self.opened_at is None: return "CLOSED"
        return "HALF_OPEN" if time.monotonic()-self.opened_at >= self.recovery_seconds else "OPEN"

class RouterError(RuntimeError): pass

class BudgetExhaustedError(RouterError):
    """The completion budget was consumed (finish_reason=length) before any
    visible text was produced -- on reasoning models the hidden reasoning
    tokens eat a small max_tokens. This is a caller budget problem, not an
    upstream fault: it must not trip breakers or cascade through the
    fallback chain (which would multiply spend and still return nothing)."""

class SpendCeilingError(RouterError):
    """Admitting this request would push aggregate provider token spend past
    the configured local admission ceiling. This is not a provider-side billing cap."""

class SpendGovernor:
    """Thread-safe aggregate token ledger: reserve-before-dispatch,
    settle-to-actual, release-on-failure.

    Per-call ``max_tokens`` bounds one response; it does not bound the fleet.
    Concurrent callers reserve an estimate before routing. Admission rejects
    estimates that exceed ``ceiling``; actual usage can exceed the estimate.
    This ledger is process-local, not durable or shared between replicas.
    ``None`` keeps accounting without enforcing an admission limit.
    """
    def __init__(self, ceiling: int | None = None):
        if ceiling is not None and (type(ceiling) is not int or ceiling < 1):
            raise RouterError("spend ceiling must be a positive integer or None")
        self.ceiling = ceiling
        self._lock = threading.Lock()
        self.reserved = 0; self.committed = 0; self.refused = 0
    def reserve(self, tokens: int) -> int:
        if type(tokens) is not int or tokens < 0:
            raise RouterError("reservation must be a non-negative integer")
        with self._lock:
            if self.ceiling is not None and self.committed + self.reserved + tokens > self.ceiling:
                self.refused += 1
                raise SpendCeilingError(
                    f"spend ceiling {self.ceiling} would be exceeded: committed={self.committed} reserved={self.reserved} requested={tokens}")
            self.reserved += tokens
            return tokens
    def settle(self, reservation: int, actual: int) -> None:
        """Convert a reservation into committed spend. ``actual`` may exceed
        the reservation (upstream overshoot is still real money) and is never
        clamped; it may be 0 when the request produced no billable usage."""
        with self._lock:
            self.reserved = max(0, self.reserved - reservation)
            self.committed += max(0, int(actual))
    def release(self, reservation: int) -> None:
        self.settle(reservation, 0)
    def snapshot(self) -> dict:
        with self._lock:
            return {"spend_ceiling": self.ceiling if self.ceiling is not None else 0,
                    "spend_reserved": self.reserved, "spend_committed": self.committed,
                    "spend_refused": self.refused}

class DurableSpendLedger(SpendGovernor):
    """AG-08: shared, durable, idempotent spend ledger backed by SQLite.

    Every replica that mounts the same ledger file (or a shared volume) admits
    against ONE aggregate: ``committed + reserved`` is computed inside a
    ``BEGIN IMMEDIATE`` transaction, so concurrent replicas cannot each admit
    against stale local state. Each attempt is a durable row keyed by a
    unique ``attempt_id``; a crash between dispatch and settle leaves the
    reservation visible (conservative: still counted) and ``reconcile()``
    expires stale reservations only after ``stale_after_seconds`` so restarts
    never double-admit. Settle is idempotent: replaying the same attempt does
    not double-count. This is still NOT a provider-side billing cap -- pair
    it with the provider's hard budget and periodic reconciliation.
    """
    def __init__(self, path: str, ceiling: int | None = None, stale_after_seconds: float = 900.0):
        super().__init__(ceiling)
        import sqlite3
        self._sqlite = sqlite3
        self.path = str(path)
        self.stale_after_seconds = float(stale_after_seconds)
        with contextlib.closing(self._connect()) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""CREATE TABLE IF NOT EXISTS spend_attempts (
                attempt_id TEXT PRIMARY KEY, reserved INTEGER NOT NULL,
                actual INTEGER, state TEXT NOT NULL, created_at REAL NOT NULL, settled_at REAL)""")
            conn.execute("CREATE INDEX IF NOT EXISTS spend_state_idx ON spend_attempts(state)")
    def _connect(self):
        conn = self._sqlite.connect(self.path, timeout=5.0, isolation_level=None)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn
    def _totals(self, conn):
        row = conn.execute("SELECT COALESCE(SUM(CASE WHEN state='reserved' THEN reserved ELSE 0 END),0),"
                           " COALESCE(SUM(CASE WHEN state='settled' THEN actual ELSE 0 END),0) FROM spend_attempts").fetchone()
        return int(row[0]), int(row[1])
    def reserve(self, tokens: int, attempt_id: str | None = None) -> str:  # type: ignore[override]
        if type(tokens) is not int or tokens < 0:
            raise RouterError("reservation must be a non-negative integer")
        import uuid
        attempt_id = attempt_id or uuid.uuid4().hex
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                existing = conn.execute("SELECT reserved FROM spend_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
                if existing is not None:  # idempotent replay of the same attempt
                    conn.execute("COMMIT"); return attempt_id
                reserved, committed = self._totals(conn)
                if self.ceiling is not None and committed + reserved + tokens > self.ceiling:
                    conn.execute("COMMIT"); self.refused += 1
                    raise SpendCeilingError(
                        f"spend ceiling {self.ceiling} would be exceeded: committed={committed} reserved={reserved} requested={tokens}")
                conn.execute("INSERT INTO spend_attempts VALUES (?,?,NULL,'reserved',?,NULL)", (attempt_id, tokens, time.time()))
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction: conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
        return attempt_id
    def settle(self, reservation, actual: int) -> None:  # type: ignore[override]
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE spend_attempts SET actual=?, state='settled', settled_at=? WHERE attempt_id=? AND state='reserved'",
                             (max(0, int(actual)), time.time(), str(reservation)))
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction: conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
    def reconcile(self, now: float | None = None) -> int:
        """Expire reservations older than ``stale_after_seconds`` (crashed replicas).
        Returns the number expired. Conservative: stale rows settle at their
        full reservation, never at zero, so a lost attempt is charged, not forgiven."""
        now = time.time() if now is None else now
        with self._lock, contextlib.closing(self._connect()) as conn:
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute("UPDATE spend_attempts SET actual=reserved, state='settled', settled_at=? "
                               "WHERE state='reserved' AND created_at < ?", (now, now - self.stale_after_seconds))
            conn.execute("COMMIT")
            return cur.rowcount
    def snapshot(self) -> dict:
        with self._lock, contextlib.closing(self._connect()) as conn:
            reserved, committed = self._totals(conn)
        return {"spend_ceiling": self.ceiling if self.ceiling is not None else 0,
                "spend_reserved": reserved, "spend_committed": committed,
                "spend_refused": self.refused, "spend_ledger": self.path}

class MeliousModelRouter:
    """Bounded-time fallback router with independent, thread-safe breakers."""
    DEFAULT_MODELS = ("glm-5.3", "glm-5.3-flash", "kimi-k3", "qwen3.8-27b")
    # Fallback chain is operator-tunable without a redeploy: MELIOUS_MODELS="a,b,c".
    # Every id in DEFAULT_MODELS was verified against the live gateway catalog
    # (GET /v1/models) — a dead id silently shortens the fallback chain (404).
    def __init__(self, models=None, base_url=None, timeout=10.0, max_retries=1,
                 acquire_timeout=5.0, probe_timeout=None,
                 transport: Callable | None=None, sleep: Callable=time.sleep,
                 max_inflight=32, total_timeout=30.0, spend_ceiling=None,
                 spend: SpendGovernor | None=None):
        env_models=tuple(m.strip() for m in os.getenv("MELIOUS_MODELS","").split(",") if m.strip())
        self.models=tuple(models or env_models or self.DEFAULT_MODELS)
        if not self.models: raise RouterError("no models configured")
        self.base_url=(base_url or os.getenv("MELIOUS_BASE_URL","https://api.melious.ai/v1")).rstrip("/")
        self.timeout=float(timeout); self.max_retries=max(0,int(max_retries))
        # Latency-budget guards (100x-load premortem): cap total time spent
        # queueing for the router lock, and give the single half-open probe a
        # shorter deadline so a hung-recovering upstream cannot stretch tail
        # latency for the whole recovery window.
        self.acquire_timeout=float(acquire_timeout)
        self.probe_timeout=float(probe_timeout) if probe_timeout is not None else max(1.0, self.timeout/2)
        if type(max_inflight) is not int or max_inflight < 1:
            raise RouterError("max_inflight must be a positive integer")
        self.total_timeout = float(total_timeout)
        for value in (self.timeout, self.acquire_timeout, self.probe_timeout, self.total_timeout):
            if not math.isfinite(value) or value <= 0:
                raise RouterError("timeouts must be finite and positive")
        # Per-model timeout overrides: MELIOUS_MODEL_TIMEOUTS="a=0.8,b=2.0".
        # Order fallbacks so historically slow routes run last, then cap each
        # model's deadline below the fleet default so a slow route cannot
        # consume the whole total budget. Unknown models and non-finite or
        # non-positive values fail closed at startup, never at request time.
        self.model_timeouts = {}
        env_timeouts = os.getenv("MELIOUS_MODEL_TIMEOUTS", "").strip()
        if env_timeouts:
            for pair in env_timeouts.split(","):
                pair = pair.strip()
                if not pair:
                    continue
                if "=" not in pair:
                    raise RouterError(f"MELIOUS_MODEL_TIMEOUTS entry must be model=seconds: {pair!r}")
                name, _, raw = pair.partition("=")
                name = name.strip()
                if name not in self.models:
                    raise RouterError(f"MELIOUS_MODEL_TIMEOUTS names unknown model {name!r}")
                try:
                    value = float(raw)
                except ValueError:
                    raise RouterError(f"MELIOUS_MODEL_TIMEOUTS value for {name!r} must be a number") from None
                if not math.isfinite(value) or value <= 0:
                    raise RouterError(f"MELIOUS_MODEL_TIMEOUTS value for {name!r} must be finite and positive")
                self.model_timeouts[name] = value
        self._slots = threading.BoundedSemaphore(max_inflight)
        # Process-local admission envelope. MELIOUS_TOKEN_CEILING enables it
        # at construction; explicitly shared governors span routers in this
        # process only. Multi-process/fleet limits need an external ledger.
        if spend is None:
            if spend_ceiling is None:
                env_ceiling = os.getenv("MELIOUS_TOKEN_CEILING", "").strip()
                if env_ceiling:
                    if not env_ceiling.isdigit(): raise RouterError("MELIOUS_TOKEN_CEILING must be a positive integer")
                    spend_ceiling = int(env_ceiling)
            ledger_path = os.getenv("MELIOUS_SPEND_LEDGER", "").strip()
            spend = DurableSpendLedger(ledger_path, spend_ceiling) if ledger_path else SpendGovernor(spend_ceiling)
        self.spend = spend
        self._transport=transport or self._http_transport; self._sleep=sleep
        self._lock=threading.RLock(); self.breakers={m:CircuitBreaker() for m in self.models}
        self._cooldown_until = {m: 0.0 for m in self.models}
        self.metrics={"requests":0,"successes":0,"failures":0,"fallbacks":0,"prompt_tokens":0,"completion_tokens":0,"reasoning_tokens":0,"total_tokens":0,"budget_exhausted":0}
    def _http_transport(self, model, payload, timeout):
        key=os.getenv("MELIOUS_API_KEY")
        if not key: raise RouterError("MELIOUS_API_KEY is not configured")
        body=json.dumps({**payload,"model":model}).encode()
        req=request.Request(self.base_url+"/chat/completions",body,{"Authorization":"Bearer "+key,"Content-Type":"application/json"})
        try:
            with request.urlopen(req,timeout=timeout) as r:
                body = r.read(self.MAX_RESPONSE_BYTES + 1)
                if len(body) > self.MAX_RESPONSE_BYTES:
                    raise RouterError("upstream response exceeds byte budget")
                return json.loads(body)
        except error.HTTPError as exc:
            retry=exc.headers.get("Retry-After") if exc.headers else None
            e=RouterError(f"upstream HTTP {exc.code}")
            e.retry_after = self._retry_after(retry)
            e.status=exc.code
            exc.close()
            raise e from None
    @staticmethod
    def _retry_after(value):
        if value is None:
            return 0.0
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            try:
                seconds = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                return 0.0
        return max(0.0, seconds) if math.isfinite(seconds) else 0.0

    @staticmethod
    def _usage_counts(data):
        """Validate all upstream counts before changing any local state."""
        usage = data.get("usage", {})
        if not isinstance(usage, dict):
            raise RouterError("malformed upstream usage")
        details = usage.get("completion_tokens_details", {})
        if details is None:
            details = {}
        if not isinstance(details, dict):
            raise RouterError("malformed upstream token details")
        counts = {k: usage.get(k, 0) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        counts["reasoning_tokens"] = details.get("reasoning_tokens", usage.get("reasoning_tokens", 0))
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise RouterError("upstream token counts must be non-negative integers")
        # Providers may omit or understate total_tokens. Reasoning tokens are
        # already included in completion_tokens; do not count them twice.
        counts["total_tokens"] = max(counts["total_tokens"],
                                     counts["prompt_tokens"] + counts["completion_tokens"])
        return counts

    MAX_MESSAGES = 256
    MAX_COMPLETION_TOKENS = 4096
    MAX_REQUEST_BYTES = 262144
    MAX_RESPONSE_BYTES = 2097152

    def complete(self, messages, **options):
        # No unbounded queue of blocked callers or outbound socket stampede.
        if not self._slots.acquire(blocking=False):
            raise RouterError("router saturated: inflight capacity exhausted")
        reservation = None
        spent = [0]
        try:
            reservation = self.spend.reserve(self._reservation_estimate(messages, options))
            return self._complete(messages, time.monotonic() + self.total_timeout, spent, **options)
        finally:
            # Admission failures, cancellation and settlement failures must all
            # return the inflight permit. Billing is independent of success.
            try:
                if reservation is not None:
                    self.spend.settle(reservation, spent[0])
            finally:
                self._slots.release()

    # English-oriented estimate, NOT a tokenizer upper bound. Unicode, model
    # templates, tools and billed retries can exceed it. Do not use this local
    # admission heuristic as a hard fleet-wide/provider monetary ceiling.
    PROMPT_CHARS_PER_TOKEN = 3
    def _reservation_estimate(self, messages, options) -> int:
        if not isinstance(messages, list): return 0
        chars = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict) and isinstance(m.get("content"), str))
        budget = options.get("max_completion_tokens", options.get("max_tokens", self.MAX_COMPLETION_TOKENS))
        if type(budget) is not int or budget < 1: budget = self.MAX_COMPLETION_TOKENS
        return math.ceil(chars / self.PROMPT_CHARS_PER_TOKEN) + budget

    def _complete(self, messages, deadline, spent=None, **options):
        if spent is None: spent = [0]
        # Sanitize the I/O boundary before any network cost is incurred.
        if not isinstance(messages, list) or not messages or len(messages) > self.MAX_MESSAGES:
            raise RouterError(f"messages must be a non-empty list of at most {self.MAX_MESSAGES} items")
        for m in messages:
            if not isinstance(m, dict) or not isinstance(m.get("role"), str) or not isinstance(m.get("content"), str):
                raise RouterError("each message needs string 'role' and 'content'")
        if sum(len(m["content"]) for m in messages) > self.MAX_REQUEST_BYTES:
            raise RouterError("prompt exceeds byte budget")
        if "model" in options: raise RouterError("model is chosen by the router; do not pass it")
        if "max_tokens" in options and "max_completion_tokens" in options:
            raise RouterError("provide exactly one completion budget")
        budget_key = "max_completion_tokens" if "max_completion_tokens" in options else "max_tokens"
        budget = options.get(budget_key, self.MAX_COMPLETION_TOKENS)
        if type(budget) is not int or not 1 <= budget <= self.MAX_COMPLETION_TOKENS:
            raise RouterError(f"completion budget must be an integer in 1..{self.MAX_COMPLETION_TOKENS}")
        if options.get("stream"):
            raise RouterError("streaming is not supported by the JSON completion router")
        if options.get("n", 1) != 1:
            raise RouterError("only one completion is supported per budget")
        payload={"messages":messages,**options, budget_key: budget}; trace=[]; last=None
        try:
            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, UnicodeError) as exc:
            raise RouterError("payload must be finite JSON") from exc
        if len(encoded) > self.MAX_REQUEST_BYTES:
            raise RouterError("payload exceeds byte budget")
        if not self._lock.acquire(timeout=self.acquire_timeout):
            raise RouterError(f"router saturated: lock not acquired within {self.acquire_timeout}s")
        try: self.metrics["requests"]+=1
        finally: self._lock.release()
        for index,model in enumerate(self.models):
            now=time.monotonic()
            if now >= deadline:
                break
            if not self._lock.acquire(timeout=self.acquire_timeout):
                raise RouterError(f"router saturated: lock not acquired within {self.acquire_timeout}s")
            try:
                allowed=now >= self._cooldown_until[model] and self.breakers[model].allow(now)
                is_probe = allowed and self.breakers[model].probing
                generation = self.breakers[model].generation
            finally: self._lock.release()
            if not allowed: trace.append({"model":model,"result":"circuit_open"}); continue
            if index and self._lock.acquire(timeout=self.acquire_timeout):
                try: self.metrics["fallbacks"]+=1
                finally: self._lock.release()
            try:
                for attempt in range(self.max_retries+1):
                    if attempt:
                        # Backoff is not a lease: another request may have
                        # opened the circuit or extended Retry-After meanwhile.
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        if not self._lock.acquire(timeout=min(self.acquire_timeout, remaining)):
                            raise RouterError("router saturated during retry admission")
                        try:
                            breaker = self.breakers[model]
                            if (breaker.generation != generation
                                    or breaker.opened_at is not None
                                    or time.monotonic() < self._cooldown_until[model]):
                                trace.append({"model": model, "result": "circuit_open"})
                                break
                        finally:
                            self._lock.release()
                    try:
                        # Half-open probe gets the shorter probe_timeout deadline.
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RouterError("router total deadline exhausted")
                        # Per-model deadline, always capped by the remaining
                        # total budget and the half-open probe budget.
                        base = self.probe_timeout if is_probe else self.model_timeouts.get(model, self.timeout)
                        data=self._transport(model,payload,min(remaining, base))
                        if not isinstance(data, dict):
                            raise RouterError("malformed upstream response")
                        # A rejected completion can still be billable. Account
                        # each response once, before validating its output, and
                        # before fallbacks can overwrite the upstream evidence.
                        counts = self._usage_counts(data)
                        spent[0] += counts["total_tokens"]
                        with self._lock:
                            for key, value in counts.items():
                                self.metrics[key] += value
                        if not isinstance(data.get("choices"), list) or not data["choices"]:
                            raise RouterError("malformed upstream response")
                        for choice in data["choices"]:
                            if not isinstance(choice, dict) or not isinstance(choice.get("message"), dict):
                                raise RouterError("malformed upstream choice")
                            if not isinstance(choice["message"].get("content"), str) or not choice["message"]["content"].strip():
                                if choice.get("finish_reason") == "length":
                                    exhausted = BudgetExhaustedError("completion budget consumed before any output text (reasoning tokens); raise max_tokens")
                                    exhausted.usage = counts
                                    raise exhausted
                                raise RouterError("upstream text completion content must be a non-empty string")
                        if len(data["choices"]) != 1:
                            raise RouterError("unexpected multiple completions")
                        if counts["completion_tokens"] > budget:
                            raise RouterError("upstream exceeded completion budget")
                        if not self._lock.acquire(timeout=self.acquire_timeout):
                            raise RouterError(f"router saturated: lock not acquired within {self.acquire_timeout}s")
                        try:
                            self.breakers[model].success(generation); self.metrics["successes"]+=1
                        finally: self._lock.release()
                        data["router"]={"selected_model":model,"fallback_chain":trace+[ {"model":model,"result":"success"} ]}
                        return data
                    except BudgetExhaustedError as exc:
                        # Fail fast: healthy upstream, wrong budget. Account spend, leave breaker CLOSED.
                        trace.append({"model":model,"result":"budget_exhausted","error":"BudgetExhaustedError","detail":"completion budget consumed by reasoning tokens","status":None})
                        if self._lock.acquire(timeout=self.acquire_timeout):
                            try:
                                # A budget-limited response proves the upstream is reachable.
                                # Release HALF_OPEN's exclusive probe as well as resetting
                                # CLOSED failure history; otherwise this route stays stuck
                                # probing forever after a reasoning-only recovery response.
                                self.breakers[model].success(generation)
                                self.metrics["failures"]+=1; self.metrics["budget_exhausted"]+=1
                            finally: self._lock.release()
                        exc.trace = trace; exc.status = None
                        raise
                    except Exception as exc:  # noqa: BLE001 -- isolate arbitrary injected transport failures
                        last=exc; trace.append({"model":model,"result":"failure","error":type(exc).__name__,"detail":f"upstream HTTP {exc.status}" if type(getattr(exc,"status",None)) is int else "upstream request failed","status":getattr(exc,"status",None)})
                        if self._lock.acquire(timeout=self.acquire_timeout):
                            try:
                                self.breakers[model].failure(time.monotonic(), generation)
                                if getattr(exc, "status", None) == 429:
                                    self._cooldown_until[model] = max(
                                        self._cooldown_until[model], time.monotonic() + self._retry_after(getattr(exc, "retry_after", 0)))
                            finally: self._lock.release()
                        status = getattr(exc, "status", None)
                        # Retry-After is route cooldown, not a worker sleep.
                        # Waiting here parks scarce inflight permits and delays
                        # healthy fallbacks even though the route is inadmissible.
                        # Prefer another route on 5xx too; retain bounded retries
                        # only at the end of the chain (no fallback remains).
                        if status == 429 or (
                                type(status) is int and 500 <= status < 600
                                and index + 1 < len(self.models)):
                            break
                        if is_probe or (status is not None and not 500 <= status < 600):
                            break
                        with self._lock:
                            if self.breakers[model].opened_at is not None:
                                break
                        if attempt < self.max_retries:
                            delay = self._retry_after(getattr(exc, "retry_after", 0)) or .1*(2**attempt)+random.random()*.05
                            # Never shorten Retry-After and hammer the same route.
                            if delay >= deadline - time.monotonic():
                                break
                            self._sleep(delay)
            finally:
                # BaseException (including cancellation) bypasses ordinary error
                # handling. Never strand the exclusive half-open probe lease.
                # This lock protects only in-memory bookkeeping, never I/O.
                if is_probe:
                    with self._lock:
                        breaker = self.breakers[model]
                        if breaker.generation == generation and breaker.probing:
                            breaker.failure(time.monotonic(), generation)
        if self._lock.acquire(timeout=self.acquire_timeout):
            try: self.metrics["failures"]+=1
            finally: self._lock.release()
        err = RouterError(f"all model routes failed: {trace}")
        # Preserve the last upstream HTTP status so callers can map 429/5xx
        # without parsing the trace text.
        if last is not None and getattr(last, "status", None) is not None:
            err.status = last.status
        raise err from last
    def get_metrics(self):
        with self._lock: base = dict(self.metrics)
        return {**base, **self.spend.snapshot(), "circuits":{m:b.state for m,b in self.breakers.items()}}
    def get_prometheus_metrics(self):
        m=self.get_metrics(); lines=[f"axiom_router_{k} {v}" for k,v in m.items() if isinstance(v,int)]
        lines += [f'axiom_router_circuit_state{{model="{name}",state="{state}"}} 1' for name,state in m["circuits"].items()]
        return "\n".join(lines)+"\n"
