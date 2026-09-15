"""Regression: reasoning models that consume the whole completion budget before
emitting text (live Melious observation, 15 Sep 2026: 3/4 default routes returned
content="" with finish_reason=length at max_tokens=16) must fail fast instead of
cascading through the fallback chain and tripping healthy breakers."""
import pytest

from kernel.sidecar.melious_router import (
    BudgetExhaustedError,
    MeliousModelRouter,
    RouterError,
)

LENGTH_EMPTY = {
    "choices": [{"message": {"content": ""}, "finish_reason": "length"}],
    "usage": {"prompt_tokens": 17, "completion_tokens": 16, "total_tokens": 33,
              "completion_tokens_details": {"reasoning_tokens": 16}},
}


def test_budget_exhausted_fails_fast_without_fallback_or_breaker_trip():
    calls = []
    def transport(model, payload, timeout):
        calls.append(model)
        return LENGTH_EMPTY
    router = MeliousModelRouter(models=["r1", "r2", "r3", "r4"], transport=transport, max_retries=1)
    with pytest.raises(BudgetExhaustedError) as info:
        router.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert calls == ["r1"], "must not retry the same route nor cascade to other models"
    assert isinstance(info.value, RouterError)
    assert info.value.status is None
    assert info.value.trace[-1]["result"] == "budget_exhausted"
    m = router.get_metrics()
    assert m["budget_exhausted"] == 1 and m["failures"] == 1 and m["fallbacks"] == 0
    assert m["reasoning_tokens"] == 16 and m["total_tokens"] == 33, "spend must still be accounted"
    assert all(state == "CLOSED" for state in m["circuits"].values()), "healthy upstream must not trip breakers"


def test_budget_exhausted_reports_in_prometheus_and_releases_slot():
    router = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: LENGTH_EMPTY, max_retries=0, max_inflight=1)
    for _ in range(2):  # a second call proves the inflight slot was released
        with pytest.raises(BudgetExhaustedError):
            router.complete([{"role": "user", "content": "hi"}], max_tokens=8)
    assert "axiom_router_budget_exhausted 2" in router.get_prometheus_metrics()


def test_empty_content_with_stop_still_falls_back():
    calls = []
    def transport(model, payload, timeout):
        calls.append(model)
        if model == "empty":
            return {"choices": [{"message": {"content": "   "}, "finish_reason": "stop"}]}
        return {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]}
    router = MeliousModelRouter(models=["empty", "working"], transport=transport, max_retries=0)
    assert router.complete([{"role": "user", "content": "hi"}], max_tokens=32)["choices"][0]["message"]["content"] == "OK"
    assert calls == ["empty", "working"]


def test_budget_exhaustion_releases_half_open_probe_for_next_request():
    import time

    calls = []
    def transport(model, payload, timeout):
        calls.append(model)
        if len(calls) == 1:
            return LENGTH_EMPTY
        return {"choices": [{"message": {"content": "ready"}}]}

    router = MeliousModelRouter(models=["r1"], transport=transport, max_retries=0)
    breaker = router.breakers["r1"]
    breaker.failures = breaker.failure_threshold
    breaker.opened_at = time.monotonic() - breaker.recovery_seconds - 1
    with pytest.raises(BudgetExhaustedError):
        router.complete([{"role": "user", "content": "hi"}], max_tokens=16)
    assert not breaker.probing, "a budget error must release the sole recovery probe"
    assert breaker.state == "CLOSED", "a valid budget-limited response proves recovery"
    assert router.complete([{"role": "user", "content": "hi"}], max_tokens=512)["choices"][0]["message"]["content"] == "ready"
    assert calls == ["r1", "r1"]
