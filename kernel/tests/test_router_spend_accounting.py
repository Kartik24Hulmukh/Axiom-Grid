"""Reported provider usage must survive response rejection and local failures."""
import pytest

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError, SpendGovernor

MSG = [{"role": "user", "content": "hi"}]


def response(content="ok", completion=3, total=8):
    return {"choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": completion,
                      "total_tokens": total}}


@pytest.mark.parametrize("bad", [
    {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}},
    response(content=""), response(completion=20, total=25),
])
def test_rejected_billable_response_still_accounted(bad):
    router = MeliousModelRouter(models=["a"], max_retries=0,
                                transport=lambda *args: bad)
    with pytest.raises(RouterError):
        router.complete(MSG, max_tokens=4)
    assert router.spend.snapshot()["spend_committed"] == bad["usage"]["total_tokens"]
    assert router.get_metrics()["total_tokens"] == bad["usage"]["total_tokens"]
    assert router.spend.snapshot()["spend_reserved"] == 0


def test_billed_rejected_fallbacks_are_all_accounted():
    def transport(model, *_):
        return response(content="" if model == "a" else "ok")
    router = MeliousModelRouter(models=["a", "b"], max_retries=0, transport=transport)
    router.complete(MSG, max_tokens=4)
    assert router.spend.snapshot()["spend_committed"] == 16
    assert router.get_metrics()["total_tokens"] == 16


@pytest.mark.parametrize("total", [None, 0, 2])
def test_total_cannot_undercount_reported_components(total):
    data = response(total=total)
    if total is None:
        del data["usage"]["total_tokens"]
    router = MeliousModelRouter(models=["a"], transport=lambda *args: data)
    router.complete(MSG, max_tokens=4)
    assert router.spend.snapshot()["spend_committed"] == 8
    assert router.get_metrics()["total_tokens"] == 8


def test_admission_cancellation_does_not_leak_slot():
    class CancelOnce(SpendGovernor):
        def reserve(self, tokens):
            if not hasattr(self, "cancelled"):
                self.cancelled = True
                raise KeyboardInterrupt()
            return super().reserve(tokens)
    router = MeliousModelRouter(models=["a"], max_inflight=1, spend=CancelOnce(),
                                transport=lambda *args: response())
    with pytest.raises(KeyboardInterrupt):
        router.complete(MSG, max_tokens=4)
    router.complete(MSG, max_tokens=4)
    assert router.spend.snapshot()["spend_reserved"] == 0


def test_settlement_failure_does_not_leak_slot():
    class FailOnce(SpendGovernor):
        def settle(self, reservation, actual):
            super().settle(reservation, actual)
            if not hasattr(self, "failed"):
                self.failed = True
                raise RuntimeError("ledger unavailable")
    router = MeliousModelRouter(models=["a"], max_inflight=1, spend=FailOnce(),
                                transport=lambda *args: response())
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        router.complete(MSG, max_tokens=4)
    router.complete(MSG, max_tokens=4)
    assert router.spend.snapshot()["spend_reserved"] == 0
    assert router.spend.snapshot()["spend_committed"] == 16


def test_reported_usage_is_not_clamped_to_admission_estimate():
    router = MeliousModelRouter(models=["a"], spend_ceiling=5,
                                transport=lambda *args: response())
    router.complete(MSG, max_tokens=4)
    # Admission estimates are not hard billing caps. Never hide overshoot.
    assert router.spend.snapshot()["spend_committed"] == 8
    assert router.spend.snapshot()["spend_reserved"] == 0
