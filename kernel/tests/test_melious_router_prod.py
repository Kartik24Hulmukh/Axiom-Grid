"""Production boundary regression and property tests; no network egress."""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from kernel.sidecar.melious_router import MeliousModelRouter, RouterError

MSG = [{"role": "user", "content": "x"}]

@pytest.mark.parametrize("choice", [None, 1, {}, {"message": []}, {"message": {}}, {"message": {"content": 7}}])
def test_malformed_choice_falls_back(choice):
    def transport(model, payload, timeout):
        return {"choices": [choice if model == "a" else {"message": {"content": "ok"}}]}
    router = MeliousModelRouter(models=("a", "b"), max_retries=0, transport=transport)
    assert router.complete(MSG)["router"]["selected_model"] == "b"

@pytest.mark.parametrize("budget", [0, -1, True, 1.5, "4", None, 4097])
def test_invalid_budget_rejected_before_transport(budget):
    calls = []
    router = MeliousModelRouter(models=("a",), transport=lambda *args: calls.append(args))
    with pytest.raises(RouterError, match="budget"):
        router.complete(MSG, max_tokens=budget)
    assert calls == []

def test_default_budget_is_sent_and_over_budget_response_falls_back():
    def transport(model, payload, timeout):
        assert payload["max_tokens"] == 4096
        return {"choices": [{"message": {"content": "ok"}}],
                "usage": {"completion_tokens": 4097 if model == "a" else 2}}
    router = MeliousModelRouter(models=("a", "b"), max_retries=0, transport=transport)
    assert router.complete(MSG)["router"]["selected_model"] == "b"
    assert router.get_metrics()["completion_tokens"] == 2

def test_conflicting_token_limits_rejected():
    router = MeliousModelRouter(models=("a",))
    with pytest.raises(RouterError, match="budget"):
        router.complete(MSG, max_tokens=1, max_completion_tokens=2)

@given(st.one_of(st.none(), st.booleans(), st.integers(), st.text(), st.lists(st.integers())))
def test_fuzz_invalid_messages_never_reach_transport(messages):
    calls = []
    router = MeliousModelRouter(models=("a",), transport=lambda *args: calls.append(args))
    with pytest.raises(RouterError):
        router.complete(messages)
    assert not calls
