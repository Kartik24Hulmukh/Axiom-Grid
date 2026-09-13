"""Adversarial admission, retry and I/O boundaries (offline fault injection)."""
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import formatdate
from threading import Event

import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError

MSG = [{"role": "user", "content": "x"}]
OK = {"choices": [{"message": {"content": "ok"}}]}


def test_100_concurrent_callers_shed_without_waiting():
    entered, release = Event(), Event()
    def transport(*args):
        entered.set()
        assert release.wait(5)
        return OK.copy()
    router = MeliousModelRouter(models=("a",), transport=transport, max_inflight=1)
    with ThreadPoolExecutor(max_workers=100) as pool:
        active = pool.submit(router.complete, MSG)
        assert entered.wait(2)
        def rejected(_):
            with pytest.raises(RouterError, match="saturated"):
                router.complete(MSG)
        try:
            list(pool.map(rejected, range(100)))
        finally:
            release.set()
        assert active.result()["choices"]
    assert router.complete(MSG)["choices"]  # slot is released


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 0, -1])
def test_invalid_timeouts(value):
    with pytest.raises(RouterError, match="timeouts"):
        MeliousModelRouter(total_timeout=value)


@pytest.mark.parametrize("value", ["junk", "nan", "inf", "-1", None])
def test_retry_after_malformed(value):
    assert MeliousModelRouter._retry_after(value) == 0


def test_retry_after_http_date():
    assert 8 <= MeliousModelRouter._retry_after(formatdate(time.time()+10, usegmt=True)) <= 10


def test_long_retry_after_falls_back_without_early_retry():
    calls, sleeps = [], []
    def transport(model, *args):
        calls.append(model)
        if model == "a":
            exc = RouterError("429")
            exc.status, exc.retry_after = 429, 300
            raise exc
        return OK.copy()
    router = MeliousModelRouter(models=("a", "b"), transport=transport, sleep=sleeps.append)
    assert router.complete(MSG)["router"]["selected_model"] == "b"
    assert calls == ["a", "b"] and sleeps == []


def test_nonretryable_404_not_retried():
    calls = []
    def transport(model, *args):
        calls.append(model)
        exc = RouterError("404")
        exc.status = 404
        raise exc
    with pytest.raises(RouterError):
        MeliousModelRouter(models=("a",), transport=transport).complete(MSG)
    assert calls == ["a"]


def test_total_budget_passed_to_transport():
    def transport(model, payload, timeout):
        assert 0 < timeout <= 0.05
        return OK.copy()
    MeliousModelRouter(models=("a",), timeout=10, total_timeout=.05, transport=transport).complete(MSG)


def test_prompt_byte_limit_and_json_validation():
    calls = []
    router = MeliousModelRouter(transport=lambda *args: calls.append(args))
    for text in ["x" * 262145, "界" * 100000]:
        with pytest.raises(RouterError, match="byte budget"):
            router.complete([{"role": "user", "content": text}])
    with pytest.raises(RouterError, match="finite JSON"):
        router.complete(MSG, temperature=float("nan"))
    assert not calls


def test_retry_after_cooldown_applies_to_other_requests():
    calls = []
    def transport(model, *args):
        calls.append(model)
        if model == "a":
            exc = RouterError("429")
            exc.status, exc.retry_after = 429, 300
            raise exc
        return OK.copy()
    router = MeliousModelRouter(models=("a", "b"), transport=transport)
    router.complete(MSG)
    router.complete(MSG)
    assert calls == ["a", "b", "b"]


def test_failed_half_open_probe_is_not_retried():
    calls = []
    def transport(*args):
        calls.append(1)
        raise TimeoutError()
    router = MeliousModelRouter(models=("a",), max_retries=5, transport=transport)
    router.breakers["a"].failures = 3
    router.breakers["a"].opened_at = time.monotonic() - 30
    with pytest.raises(RouterError):
        router.complete(MSG)
    assert calls == [1]
