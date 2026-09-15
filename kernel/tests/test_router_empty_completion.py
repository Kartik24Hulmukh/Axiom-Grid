from kernel.sidecar.melious_router import MeliousModelRouter


def test_empty_reasoning_only_completion_falls_back():
    calls = []
    def transport(model, payload, timeout):
        calls.append(model)
        return {"choices": [{"message": {"content": "" if model == "empty" else "OK"}}]}
    router = MeliousModelRouter(models=["empty", "working"], transport=transport, max_retries=0)
    result = router.complete([{"role": "user", "content": "hi"}], max_tokens=32)
    assert result["choices"][0]["message"]["content"] == "OK"
    assert calls == ["empty", "working"]
    assert router.get_metrics()["successes"] == 1


def test_inference_logs_respect_writable_state_root(monkeypatch, tmp_path):
    from kernel.sidecar.inference_gateway import TieredInferenceGateway
    monkeypatch.setenv("AXIOM_STATE_DIR", str(tmp_path / "state"))
    gateway = TieredInferenceGateway(tier3_enabled=False)
    assert gateway.log_dir == tmp_path / "state" / "inference_logs"
    assert gateway.log_dir.is_dir()
    explicit = TieredInferenceGateway(tier3_enabled=False, log_dir=str(tmp_path / "explicit"))
    assert explicit.log_dir == tmp_path / "explicit"
