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
