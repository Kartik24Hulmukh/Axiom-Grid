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

def test_breaker_opens_and_skips():
 def tx(*args): raise TimeoutError()
 r=MeliousModelRouter(models=("a",),max_retries=0,transport=tx)
 for _ in range(3):
  try:r.complete([])
  except RouterError:pass
 assert r.breakers["a"].state=="OPEN"
 try:r.complete([])
 except RouterError as e: assert "circuit_open" in str(e)

def test_missing_secret_fails_closed(monkeypatch):
 monkeypatch.delenv("MELIOUS_API_KEY",raising=False)
 r=MeliousModelRouter(models=("a",),max_retries=0)
 try:r.complete([])
 except RouterError as e: assert "all model routes failed" in str(e)
