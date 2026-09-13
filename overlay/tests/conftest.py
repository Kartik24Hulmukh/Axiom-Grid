"""Every overlay test owns an ASGI lifespan; no requests to stopped services."""
import pytest
from fastapi.testclient import TestClient

from overlay import server


@pytest.fixture(autouse=True)
def running_overlay():
    with TestClient(server.app):
        yield
