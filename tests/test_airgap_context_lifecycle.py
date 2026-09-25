"""Scoped audit interception must not suppress unrelated trace writes."""
import os
import socket
import pytest
from kairo.oracles.airgap_egress import SocketEgressInterceptor

KEYS = ("KAIRO_AIRGAP", "KAIRO_SEALED", "NO_PROXY", "no_proxy")

@pytest.mark.parametrize("existing", [None, "0", "1"])
@pytest.mark.parametrize("raises", [False, True])
def test_context_restores_environment_and_socket(monkeypatch, existing, raises):
    for key in KEYS:
        if existing is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, existing)
    before = {key: os.environ.get(key) for key in KEYS}
    connect = socket.socket.connect
    try:
        with SocketEgressInterceptor():
            assert os.environ["KAIRO_SEALED"] == "1"
            assert socket.socket.connect is not connect
            if raises:
                raise ValueError("test exception")
    except ValueError:
        pass
    assert socket.socket.connect is connect
    assert {key: os.environ.get(key) for key in KEYS} == before


def test_nested_context_restores_outer_state(monkeypatch):
    for key in KEYS:
        monkeypatch.delenv(key, raising=False)
    with SocketEgressInterceptor():
        outer_connect = socket.socket.connect
        with SocketEgressInterceptor():
            assert os.environ["KAIRO_SEALED"] == "1"
        assert os.environ["KAIRO_SEALED"] == "1"
        assert socket.socket.connect is outer_connect
    assert "KAIRO_SEALED" not in os.environ
