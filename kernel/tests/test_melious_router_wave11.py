"""Malformed upstream metadata must not corrupt accounting or expose secrets."""
import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError

MSG = [{"role": "user", "content": "x"}]


@pytest.mark.parametrize("usage", [None, [], {"prompt_tokens": 3, "completion_tokens": "bad"}, {"prompt_tokens": -1}, {"total_tokens": True}, {"completion_tokens_details": []}])
def test_bad_usage_falls_back_without_partial_success(usage):
    def transport(model, payload, timeout):
        return {"choices": [{"message": {"content": "ok"}}], "usage": usage if model == "a" else {"total_tokens": 2}}
    router = MeliousModelRouter(models=("a", "b"), max_retries=0, transport=transport)
    result = router.complete(MSG)
    assert result["router"]["selected_model"] == "b"
    metrics = router.get_metrics()
    assert metrics["successes"] == 1
    assert metrics["prompt_tokens"] == 0
    assert metrics["total_tokens"] == 2


def test_transport_exception_text_not_exposed_in_trace():
    def transport(*args):
        raise RuntimeError("credential=PRIVATE_SENTINEL document=CONFIDENTIAL")
    router = MeliousModelRouter(models=("a",), max_retries=0, transport=transport)
    with pytest.raises(RouterError) as error:
        router.complete(MSG)
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert "CONFIDENTIAL" not in str(error.value)


def test_success_fallback_trace_does_not_leak_transport_message():
    def transport(model, *args):
        if model == "a":
            raise RuntimeError("PRIVATE_SENTINEL")
        return {"choices": [{"message": {"content": "ok"}}]}
    router = MeliousModelRouter(models=("a", "b"), max_retries=0, transport=transport)
    assert "PRIVATE_SENTINEL" not in str(router.complete(MSG))


@pytest.mark.parametrize("failure", [TimeoutError, ConnectionResetError])
def test_network_failure_falls_back(failure):
    def transport(model, *args):
        if model == "a":
            raise failure("synthetic dropout")
        return {"choices": [{"message": {"content": "ok"}}]}
    router = MeliousModelRouter(models=("a", "b"), max_retries=0, transport=transport)
    assert router.complete(MSG)["router"]["selected_model"] == "b"


def test_rate_limit_retry_delay_is_bounded_and_falls_back():
    delays, calls = [], []
    def transport(model, *args):
        calls.append(model)
        if model == "a":
            error = RouterError("rate limited")
            error.status, error.retry_after = 429, 120
            raise error
        return {"choices": [{"message": {"content": "ok"}}]}
    router = MeliousModelRouter(models=("a", "b"), max_retries=1,
                               transport=transport, sleep=delays.append)
    assert router.complete(MSG)["router"]["selected_model"] == "b"
    assert calls == ["a", "a", "b"]
    assert delays == [2.0]


def test_out_of_order_success_keeps_usage_atomic():
    import concurrent.futures
    import threading

    first_entered, second_done = threading.Event(), threading.Event()
    def transport(model, payload, timeout):
        if payload["messages"][0]["content"] == "first":
            first_entered.set()
            assert second_done.wait(3)
            count = 2
        else:
            assert first_entered.wait(3)
            count = 3
            second_done.set()
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": count}}
    router = MeliousModelRouter(models=("a",), max_retries=0, transport=transport)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        first = pool.submit(router.complete, [{"role": "user", "content": "first"}])
        second = pool.submit(router.complete, MSG)
        first.result(timeout=4)
        second.result(timeout=4)
    metrics = router.get_metrics()
    assert metrics["successes"] == 2 and metrics["total_tokens"] == 5
