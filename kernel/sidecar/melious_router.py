"""Resilient Melious multi-model router. Credentials are read at call time only."""
from __future__ import annotations
from dataclasses import dataclass
import json, os, random, threading, time
from typing import Callable
from urllib import error, request

@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_seconds: float = 15.0
    failures: int = 0
    opened_at: float | None = None
    probing: bool = False
    def allow(self, now: float) -> bool:
        """CLOSED -> True. OPEN -> False. HALF_OPEN -> exactly one caller is
        admitted as the probe; concurrent callers keep failing fast so a
        recovering upstream is not stampeded (100x-load premortem #4)."""
        if self.opened_at is None: return True
        if now - self.opened_at < self.recovery_seconds or self.probing: return False
        self.probing = True; return True
    def success(self) -> None:
        self.failures, self.opened_at, self.probing = 0, None, False
    def failure(self, now: float) -> None:
        self.failures += 1; self.probing = False
        if self.failures >= self.failure_threshold: self.opened_at = now
    @property
    def state(self) -> str:
        if self.opened_at is None: return "CLOSED"
        return "HALF_OPEN" if time.monotonic()-self.opened_at >= self.recovery_seconds else "OPEN"

class RouterError(RuntimeError): pass

class MeliousModelRouter:
    """Bounded-time fallback router with independent, thread-safe breakers."""
    DEFAULT_MODELS = ("glm-5.3", "kimi-k3", "qwen3.8-27b")
    # Fallback chain is operator-tunable without a redeploy: MELIOUS_MODELS="a,b,c".
    # Every id in DEFAULT_MODELS was verified against the live gateway catalog
    # (GET /v1/models) — a dead id silently shortens the fallback chain (404).
    def __init__(self, models=None, base_url=None, timeout=10.0, max_retries=1,
                 transport: Callable | None=None, sleep: Callable=time.sleep):
        env_models=tuple(m.strip() for m in os.getenv("MELIOUS_MODELS","").split(",") if m.strip())
        self.models=tuple(models or env_models or self.DEFAULT_MODELS)
        if not self.models: raise RouterError("no models configured")
        self.base_url=(base_url or os.getenv("MELIOUS_BASE_URL","https://api.melious.ai/v1")).rstrip("/")
        self.timeout=float(timeout); self.max_retries=max(0,int(max_retries))
        self._transport=transport or self._http_transport; self._sleep=sleep
        self._lock=threading.RLock(); self.breakers={m:CircuitBreaker() for m in self.models}
        self.metrics={"requests":0,"successes":0,"failures":0,"fallbacks":0,"prompt_tokens":0,"completion_tokens":0,"reasoning_tokens":0,"total_tokens":0}
    def _http_transport(self, model, payload, timeout):
        key=os.getenv("MELIOUS_API_KEY")
        if not key: raise RouterError("MELIOUS_API_KEY is not configured")
        body=json.dumps({**payload,"model":model}).encode()
        req=request.Request(self.base_url+"/chat/completions",body,{"Authorization":"Bearer "+key,"Content-Type":"application/json"})
        try:
            with request.urlopen(req,timeout=timeout) as r: return json.loads(r.read())
        except error.HTTPError as exc:
            retry=exc.headers.get("Retry-After") if exc.headers else None
            e=RouterError(f"upstream HTTP {exc.code}"); e.retry_after=float(retry or 0); e.status=exc.code; raise e
    MAX_MESSAGES = 256
    def complete(self, messages, **options):
        # Sanitize the I/O boundary before any network cost is incurred.
        if not isinstance(messages, list) or not messages or len(messages) > self.MAX_MESSAGES:
            raise RouterError("messages must be a non-empty list of at most %d items" % self.MAX_MESSAGES)
        for m in messages:
            if not isinstance(m, dict) or not isinstance(m.get("role"), str) or not isinstance(m.get("content"), str):
                raise RouterError("each message needs string 'role' and 'content'")
        if "model" in options: raise RouterError("model is chosen by the router; do not pass it")
        payload={"messages":messages,**options}; trace=[]; last=None
        with self._lock: self.metrics["requests"]+=1
        for index,model in enumerate(self.models):
            now=time.monotonic()
            with self._lock: allowed=self.breakers[model].allow(now)
            if not allowed: trace.append({"model":model,"result":"circuit_open"}); continue
            if index: 
                with self._lock: self.metrics["fallbacks"]+=1
            for attempt in range(self.max_retries+1):
                try:
                    data=self._transport(model,payload,self.timeout)
                    if not isinstance(data, dict) or not isinstance(data.get("choices"), list) or not data["choices"]:
                        raise RouterError("malformed upstream response")
                    with self._lock:
                        self.breakers[model].success(); self.metrics["successes"]+=1
                        usage=data.get("usage",{}); details=usage.get("completion_tokens_details",{}) or {}
                        for k in ("prompt_tokens","completion_tokens","total_tokens"): self.metrics[k]+=int(usage.get(k,0) or 0)
                        self.metrics["reasoning_tokens"]+=int(details.get("reasoning_tokens",usage.get("reasoning_tokens",0)) or 0)
                    data["router"]={"selected_model":model,"fallback_chain":trace+[ {"model":model,"result":"success"} ]}
                    return data
                except Exception as exc:
                    last=exc; trace.append({"model":model,"result":"failure","error":type(exc).__name__,"detail":str(exc)[:120],"status":getattr(exc,"status",None)})
                    with self._lock: self.breakers[model].failure(time.monotonic())
                    if attempt < self.max_retries:
                        delay=min(float(getattr(exc,"retry_after",0) or 0) or .1*(2**attempt)+random.random()*.05,2.0); self._sleep(delay)
        with self._lock: self.metrics["failures"]+=1
        raise RouterError(f"all model routes failed: {trace}") from last
    def get_metrics(self):
        with self._lock: return {**self.metrics,"circuits":{m:b.state for m,b in self.breakers.items()}}
    def get_prometheus_metrics(self):
        m=self.get_metrics(); lines=[f"axiom_router_{k} {v}" for k,v in m.items() if isinstance(v,int)]
        lines += [f'axiom_router_circuit_state{{model="{name}",state="{state}"}} 1' for name,state in m["circuits"].items()]
        return "\n".join(lines)+"\n"
