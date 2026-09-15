"""Deterministic overlapping requests: no sleeps and no external traffic."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError

MSG = [{"role": "user", "content": "x"}]
OK = {"choices": [{"message": {"content": "ok"}}]}


@pytest.mark.parametrize("budget_response", [False, True])
def test_stale_success_cannot_close_newly_opened_circuit(budget_response):
    entered, release = threading.Event(), threading.Event()

    def transport(model, payload, timeout):
        if payload["messages"][0]["content"] == "old":
            entered.set()
            assert release.wait(3)
            if budget_response:
                return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
            return dict(OK)
        raise TimeoutError("controlled failure")

    router = MeliousModelRouter(models=("a",), transport=transport, max_retries=0)
    router.breakers["a"].failure_threshold = 1
    with ThreadPoolExecutor(1) as pool:
        old = pool.submit(router.complete, [{"role": "user", "content": "old"}])
        try:
            assert entered.wait(3)
            with pytest.raises(RouterError):
                router.complete(MSG)
        finally:
            release.set()
        if budget_response:
            with pytest.raises(RouterError):
                old.result(timeout=3)
        else:
            old.result(timeout=3)
    assert router.breakers["a"].state == "OPEN"
    with pytest.raises(RouterError, match="circuit_open"):
        router.complete(MSG)


def test_cancelled_half_open_probe_releases_lease_and_inflight_slot():
    class Cancelled(BaseException):
        pass

    def transport(*args):
        raise Cancelled()

    router = MeliousModelRouter(models=("a",), transport=transport, max_retries=0, max_inflight=1)
    breaker = router.breakers["a"]
    breaker.failures = breaker.failure_threshold
    breaker.opened_at = time.monotonic() - breaker.recovery_seconds - 1
    with pytest.raises(Cancelled):
        router.complete(MSG)
    assert not breaker.probing
    assert breaker.state == "OPEN"
    assert router._slots.acquire(blocking=False)
    router._slots.release()


def test_stale_failure_cannot_release_another_requests_half_open_probe():
    old_entered, old_release = threading.Event(), threading.Event()
    probe_entered, probe_release = threading.Event(), threading.Event()

    def transport(model, payload, timeout):
        name = payload["messages"][0]["content"]
        if name == "old":
            old_entered.set()
            assert old_release.wait(3)
            raise TimeoutError()
        if name == "probe":
            probe_entered.set()
            assert probe_release.wait(3)
            return dict(OK)
        raise TimeoutError()

    router = MeliousModelRouter(models=("a",), transport=transport, max_retries=0)
    breaker = router.breakers["a"]
    breaker.failure_threshold = 1
    with ThreadPoolExecutor(2) as pool:
        old = pool.submit(router.complete, [{"role": "user", "content": "old"}])
        try:
            assert old_entered.wait(3)
            with pytest.raises(RouterError):
                router.complete(MSG)
            breaker.opened_at -= breaker.recovery_seconds + 1
            probe = pool.submit(router.complete, [{"role": "user", "content": "probe"}])
            assert probe_entered.wait(3)
            old_release.set()
            with pytest.raises(RouterError):
                old.result(timeout=3)
            assert breaker.probing, "stale failure stole the active probe lease"
            with pytest.raises(RouterError, match="circuit_open"):
                router.complete(MSG)
        finally:
            old_release.set()
            probe_release.set()
        assert probe.result(timeout=3)["router"]["selected_model"] == "a"
    assert breaker.state == "CLOSED"


def test_retry_rechecks_admission_after_other_request_opens_circuit():
    sleeping, resume = threading.Event(), threading.Event()
    calls = []

    def transport(model, payload, timeout):
        calls.append(payload["messages"][0]["content"])
        raise TimeoutError()

    def wait_for_other_request(delay):
        sleeping.set()
        assert resume.wait(3)

    router = MeliousModelRouter(models=("a",), transport=transport,
                                max_retries=1, sleep=wait_for_other_request)
    router.breakers["a"].failure_threshold = 2
    with ThreadPoolExecutor(1) as pool:
        first = pool.submit(router.complete, [{"role": "user", "content": "first"}])
        try:
            assert sleeping.wait(3)
            with pytest.raises(RouterError):
                router.complete(MSG)
        finally:
            resume.set()
        with pytest.raises(RouterError):
            first.result(timeout=3)
    assert calls == ["first", "x"], "retry bypassed the newly OPEN circuit"


def test_100_callers_only_one_recovery_probe_and_no_permit_leak():
    from collections import Counter

    start = threading.Barrier(100)
    decisions = threading.Barrier(100)
    calls = []
    guard = threading.Lock()

    def transport(*args):
        with guard:
            calls.append(1)
        decisions.wait(timeout=10)
        return dict(OK)

    router = MeliousModelRouter(models=("a",), transport=transport,
                                max_retries=0, max_inflight=100)
    breaker = router.breakers["a"]
    breaker.failures = breaker.failure_threshold
    breaker.opened_at = time.monotonic() - breaker.recovery_seconds - 1

    def hit(_):
        start.wait(timeout=10)
        try:
            router.complete(MSG)
            return "success"
        except RouterError as exc:
            assert "circuit_open" in str(exc)
            decisions.wait(timeout=10)
            return "rejected"

    with ThreadPoolExecutor(100) as pool:
        results = Counter(pool.map(hit, range(100)))
    assert results == {"success": 1, "rejected": 99}
    assert len(calls) == 1 and breaker.state == "CLOSED"
    for _ in range(100):
        assert router._slots.acquire(blocking=False)
    assert not router._slots.acquire(blocking=False)
    for _ in range(100):
        router._slots.release()
