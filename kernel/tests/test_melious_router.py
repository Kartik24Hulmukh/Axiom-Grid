from kernel.sidecar.melious_router import MeliousModelRouter, RouterError


def test_fallback_and_usage():
 calls=[]
 def tx(model,payload,timeout):
  calls.append(model)
  if model=="a": raise TimeoutError()
  return {"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":2,"completion_tokens":3,"total_tokens":5,"completion_tokens_details":{"reasoning_tokens":1}}}
 r=MeliousModelRouter(models=("a","b"),max_retries=0,transport=tx)
 out=r.complete([{"role":"user","content":"x"}])
 assert calls==["a","b"] and out["router"]["selected_model"]=="b"
 assert r.get_metrics()["total_tokens"]==5

MSG=[{"role":"user","content":"x"}]

def test_breaker_opens_and_skips():
 import pytest
 calls=[]
 def tx(*args): calls.append(1); raise TimeoutError()
 r=MeliousModelRouter(models=("a",),max_retries=0,transport=tx)
 for _ in range(3):
  with pytest.raises(RouterError): r.complete(MSG)
 assert r.breakers["a"].state=="OPEN" and len(calls)==3
 with pytest.raises(RouterError, match="circuit_open"): r.complete(MSG)
 assert len(calls)==3  # OPEN breaker fails fast without touching the transport

def test_missing_secret_fails_closed(monkeypatch):
 import pytest
 monkeypatch.delenv("MELIOUS_API_KEY",raising=False)
 r=MeliousModelRouter(models=("a",),max_retries=0)
 with pytest.raises(RouterError, match="all model routes failed"): r.complete(MSG)


def _ok():
 return {"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1,"completion_tokens":1,"total_tokens":2}}

def test_half_open_admits_single_probe_then_recloses():
 import threading
 admitted=[];gate=threading.Event();lock=threading.Lock()
 def tx(model,payload,timeout):
  if not gate.is_set(): raise TimeoutError()
  with lock: admitted.append(model)
  return _ok()
 r=MeliousModelRouter(models=("a",),max_retries=0,transport=tx)
 r.breakers["a"].recovery_seconds=0.0
 for _ in range(3):
  try:r.complete([{"role":"user","content":"x"}])
  except RouterError:pass
 b=r.breakers["a"]; assert b.opened_at is not None
 gate.set()
 # Manually drive the breaker: first caller is the probe, concurrent second caller is rejected.
 now=b.opened_at+1
 assert b.allow(now) is True and b.allow(now) is False
 b.success(); assert b.state=="CLOSED" and b.allow(now) is True
 out=r.complete([{"role":"user","content":"x"}]); assert out["router"]["selected_model"]=="a" and admitted==["a"]

def test_half_open_failed_probe_reopens():
 from kernel.sidecar.melious_router import CircuitBreaker
 b=CircuitBreaker(failure_threshold=1,recovery_seconds=0.0)
 b.failure(0.0); assert b.allow(1.0) and not b.allow(1.0)
 b.failure(1.0); assert b.opened_at==1.0 and b.probing is False

def test_input_sanitization_never_hits_transport():
 calls=[]
 def tx(*a): calls.append(a); return _ok()
 r=MeliousModelRouter(models=("a",),transport=tx)
 import pytest
 for bad in ([],"hi",[{"role":"user"}],[{"role":1,"content":"x"}],[{"role":"user","content":"x"}]*300):
  with pytest.raises(RouterError): r.complete(bad)
 with pytest.raises(RouterError): r.complete([{"role":"user","content":"x"}],model="b")
 assert calls==[] and r.breakers["a"].state=="CLOSED"

def test_malformed_upstream_response_falls_back():
 seen=[]
 def tx(model,payload,timeout):
  seen.append(model); return ["not","a","dict"] if model=="a" else {"choices":[]} if model=="b" else _ok()
 r=MeliousModelRouter(models=("a","b","c"),max_retries=0,transport=tx)
 out=r.complete([{"role":"user","content":"x"}])
 assert seen==["a","b","c"] and out["router"]["selected_model"]=="c" and r.get_metrics()["fallbacks"]==2

def test_concurrent_completion_metrics_are_consistent():
 import threading
 def tx(model,payload,timeout): return _ok()
 r=MeliousModelRouter(models=("a",),max_retries=0,transport=tx)
 def w():
  for _ in range(50): r.complete([{"role":"user","content":"x"}])
 ts=[threading.Thread(target=w) for _ in range(20)];[t.start() for t in ts];[t.join() for t in ts]
 m=r.get_metrics(); assert m["requests"]==m["successes"]==1000 and m["total_tokens"]==2000
 assert "axiom_router_requests 1000" in r.get_prometheus_metrics()


def test_models_env_override_and_trace_detail(monkeypatch):
 monkeypatch.setenv("MELIOUS_MODELS"," x , y ")
 def tx(model,payload,timeout):
  if model=="x":
   e=RouterError("upstream HTTP 404"); e.status=404; raise e
  return _ok()
 r=MeliousModelRouter(max_retries=0,transport=tx)
 assert r.models==("x","y")
 out=r.complete(MSG); chain=out["router"]["fallback_chain"]
 assert chain[0]["status"]==404 and "HTTP 404" in chain[0]["detail"] and chain[-1]["result"]=="success"

def test_default_models_are_distinct_and_nonempty():
 assert len(set(MeliousModelRouter.DEFAULT_MODELS))==4 and all(MeliousModelRouter.DEFAULT_MODELS)
