"""A rate-limited route must not park workers while a fallback is available."""
import pytest
from kernel.sidecar.melious_router import MeliousModelRouter, RouterError


@pytest.mark.parametrize("retry_after", [0, 0.01, 1, 10, 120])
def test_429_immediately_falls_back_without_sleep(retry_after):
    calls, delays = [], []

    def transport(model, payload, timeout):
        calls.append(model)
        if model == "limited":
            exc = RouterError("rate limited")
            exc.status, exc.retry_after = 429, retry_after
            raise exc
        return {"choices": [{"message": {"content": "ok"}}]}

    router = MeliousModelRouter(models=("limited", "healthy"), transport=transport,
                                sleep=delays.append, max_retries=3)
    result = router.complete([{"role": "user", "content": "x"}], max_tokens=8)
    assert result["router"]["selected_model"] == "healthy"
    assert calls == ["limited", "healthy"]
    assert delays == [], "429 must release the worker to fallback, not consume its deadline"
    if retry_after >= 1:
        router.complete([{"role": "user", "content": "x"}], max_tokens=8)
        assert calls == ["limited", "healthy", "healthy"]


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_5xx_prefers_fallback_over_blocking_retry(status):
    calls, delays = [], []

    def transport(model, payload, timeout):
        calls.append(model)
        if model == "failed":
            exc = RouterError("unavailable")
            exc.status = status
            raise exc
        return {"choices": [{"message": {"content": "ok"}}]}

    router = MeliousModelRouter(models=("failed", "healthy"), transport=transport,
                                sleep=delays.append, max_retries=3)
    assert router.complete([{"role": "user", "content": "x"}])["router"]["selected_model"] == "healthy"
    assert calls == ["failed", "healthy"]
    assert delays == []


def test_last_route_retains_bounded_5xx_retry():
    calls, delays = [], []

    def transport(model, payload, timeout):
        calls.append(model)
        if len(calls) == 1:
            exc = RouterError("unavailable")
            exc.status = 503
            raise exc
        return {"choices": [{"message": {"content": "ok"}}]}

    router = MeliousModelRouter(models=("only",), transport=transport,
                                sleep=delays.append, max_retries=1)
    assert router.complete([{"role": "user", "content": "x"}])["router"]["selected_model"] == "only"
    assert calls == ["only", "only"]
    assert len(delays) == 1
