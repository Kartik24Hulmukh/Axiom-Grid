"""Aggregate provider spend governor (Session 14, premortem blocker #4).

Per-call max_tokens bounds one response, not the fleet. Under a 100x burst the
router must refuse admission *before* any network cost once committed+reserved
tokens would breach the operator ceiling, settle reservations to the usage the
upstream actually billed, and give unused reservations back on failure.
"""
import threading

import pytest

from kernel.sidecar.melious_router import (
    BudgetExhaustedError,
    MeliousModelRouter,
    RouterError,
    SpendCeilingError,
    SpendGovernor,
)

OK = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
      "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}}
LENGTH_EMPTY = {"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9,
                          "completion_tokens_details": {"reasoning_tokens": 4}}}
MSG = [{"role": "user", "content": "hi"}]  # 2 chars -> ceil(2/3)=1 prompt token estimate


class Upstream(Exception):
    def __init__(self, status): super().__init__(status); self.status = status


def test_ceiling_refuses_before_any_network_cost():
    calls = []
    def transport(model, payload, timeout): calls.append(model); return OK
    router = MeliousModelRouter(models=["r1"], transport=transport, spend_ceiling=10)
    router.complete(MSG, max_tokens=4)  # reserves 5, settles to 8 committed
    with pytest.raises(SpendCeilingError) as info:
        router.complete(MSG, max_tokens=4)  # 8 + 5 > 10
    assert isinstance(info.value, RouterError)
    assert calls == ["r1"], "refused request must never reach the transport"
    m = router.get_metrics()
    assert m["spend_committed"] == 8 and m["spend_reserved"] == 0 and m["spend_refused"] == 1
    assert m["requests"] == 1, "a refused request is not a routed request"
    assert "axiom_router_spend_refused 1" in router.get_prometheus_metrics()
    assert "axiom_router_spend_ceiling 10" in router.get_prometheus_metrics()


def test_reservation_settles_to_actual_usage_not_estimate():
    router = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: OK, spend_ceiling=1000)
    router.complete(MSG, max_tokens=200)  # estimate 201, actual 8
    m = router.get_metrics()
    assert m["spend_committed"] == 8 and m["spend_reserved"] == 0
    assert m["spend_committed"] == m["total_tokens"], "ledger and metrics must agree"


def test_failed_route_releases_reservation():
    def transport(model, payload, timeout): raise Upstream(503)
    router = MeliousModelRouter(models=["r1", "r2"], transport=transport, max_retries=0, spend_ceiling=20)
    with pytest.raises(RouterError): router.complete(MSG, max_tokens=8)
    m = router.get_metrics()
    assert m["spend_reserved"] == 0 and m["spend_committed"] == 0, "nothing billed, nothing held"
    router.spend = SpendGovernor(20); router._transport = lambda m, p, t: OK
    router.complete(MSG, max_tokens=8)  # capacity was returned, so this admits


def test_budget_exhausted_still_bills_ledger():
    router = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: LENGTH_EMPTY, max_retries=0, spend_ceiling=100)
    with pytest.raises(BudgetExhaustedError): router.complete(MSG, max_tokens=4)
    m = router.get_metrics()
    assert m["spend_committed"] == 9 and m["spend_reserved"] == 0, "reasoning tokens are real spend"


def test_100x_barrier_burst_never_overshoots_ceiling():
    """100 callers released simultaneously against a ceiling that admits ~40:
    admitted + refused == 100, transport calls == admitted, committed <= ceiling."""
    ceiling = 200  # each call reserves 1 + 4 = 5 -> at most 40 admitted; each bills 8
    calls = []; guard = threading.Lock(); barrier = threading.Barrier(100)
    def transport(model, payload, timeout):
        with guard: calls.append(model)
        return OK
    router = MeliousModelRouter(models=["r1"], transport=transport, max_inflight=100, spend_ceiling=ceiling)
    outcomes = []
    def worker():
        barrier.wait()
        try: router.complete(MSG, max_tokens=4); outcomes.append("ok")
        except SpendCeilingError: outcomes.append("refused")
    threads = [threading.Thread(target=worker) for _ in range(100)]
    for th in threads: th.start()
    for th in threads: th.join(timeout=30)
    assert not any(th.is_alive() for th in threads)
    m = router.get_metrics()
    admitted = outcomes.count("ok"); refused = outcomes.count("refused")
    assert admitted + refused == 100 and len(calls) == admitted
    assert admitted >= 1 and refused >= 1, "ceiling must bite under burst"
    assert m["spend_reserved"] == 0, "no reservation may leak after the burst"
    assert m["spend_committed"] == 8 * admitted <= ceiling + 8 * admitted - 5 * admitted
    # The invariant the governor guarantees: reserved-at-admission never exceeded the ceiling.
    assert 5 * admitted <= ceiling
    assert m["spend_refused"] == refused


def test_ceiling_from_environment_and_validation(monkeypatch):
    monkeypatch.setenv("MELIOUS_TOKEN_CEILING", "7")
    router = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: OK)
    assert router.spend.ceiling == 7
    with pytest.raises(SpendCeilingError): router.complete(MSG, max_tokens=7)  # 1 + 7 > 7
    monkeypatch.setenv("MELIOUS_TOKEN_CEILING", "-3")
    with pytest.raises(RouterError): MeliousModelRouter(models=["r1"], transport=lambda m, p, t: OK)
    with pytest.raises(RouterError): SpendGovernor(0)
    with pytest.raises(RouterError): SpendGovernor(True)


def test_shared_governor_spans_routers():
    shared = SpendGovernor(12)
    a = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: OK, spend=shared)
    b = MeliousModelRouter(models=["r2"], transport=lambda m, p, t: OK, spend=shared)
    a.complete(MSG, max_tokens=4)  # commits 8
    with pytest.raises(SpendCeilingError): b.complete(MSG, max_tokens=4)  # 8 + 5 > 12 across routers


def test_unlimited_default_keeps_ledger_without_refusals(monkeypatch):
    monkeypatch.delenv("MELIOUS_TOKEN_CEILING", raising=False)
    router = MeliousModelRouter(models=["r1"], transport=lambda m, p, t: OK)
    for _ in range(3): router.complete(MSG, max_tokens=4)
    m = router.get_metrics()
    assert m["spend_ceiling"] == 0 and m["spend_refused"] == 0 and m["spend_committed"] == 24
