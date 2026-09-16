"""SEC-015 regression: lone UTF-16 surrogates in JSON must never yield 5xx.

Root cause: a JSON escape for a lone surrogate (U+DC00..U+DFFF / U+D800..U+DBFF)
decodes to a Python str that is not UTF-8-encodable. It passes the byte-level
SEC-014 sanitizer, then Starlette's JSONResponse.render() raises
UnicodeEncodeError in the ASGI send path -- after every handler try/except --
so each ingress route returned 500. Surrogates are built with chr() because
pytest's assertion rewriter cannot compile a module containing one literally.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from statistics import quantiles

import pytest
from fastapi.testclient import TestClient

from overlay import server

LO, HI, TOP = chr(0xDCFF), chr(0xD800), chr(0xDFFF)
ROUTES = ["/demo", "/apply", "/correct", "/api/extract-document", "/api/ask-document", "/api/graph/query"]
JSON = {"Content-Type": "application/json"}
ALL_FIELDS = ["file", "text", "question", "doc_id", "query", "ext_id", "field_name", "original", "corrected", "reason"]
VECTORS = {
    "value_lone_low": json.dumps({**{k: LO for k in ALL_FIELDS}, "accept": True}),
    "value_lone_high": json.dumps({"file": "a" + HI + "b", "ext_id": HI, "doc_id": HI, "query": HI}),
    "key_surrogate": json.dumps({LO: 1}),
    "nested_list": json.dumps({"file": [LO], "query": {"x": [TOP]}}),
    "mixed_with_valid_unicode": json.dumps({"file": "\u00e9\u4e2d" + LO, "doc_id": "ok"}),
}
for _body in VECTORS.values():
    _body.encode("utf-8")  # the wire bytes are pure ASCII JSON escapes


@pytest.fixture(autouse=True)
def _isolate_rate_limit(monkeypatch):
    monkeypatch.setattr(server, "_rate_limit_buckets", {}, raising=False)


@pytest.fixture(scope="module")
def client():
    with TestClient(server.app, raise_server_exceptions=False) as c:
        yield c


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("name,body", list(VECTORS.items()))
def test_surrogate_payload_never_5xx(client, route, name, body):
    r = client.post(route, content=body, headers=JSON)
    assert r.status_code < 500, (route, name, r.status_code, r.text[:200])
    assert r.status_code in (400, 404, 422)
    r.json()  # body must itself be valid, decodable JSON
    assert LO not in r.text and HI not in r.text


def test_render_is_total():
    hostile = {"detail": LO, HI: [TOP, float("nan")], "obj": object()}
    body = server.JSONResponse(status_code=422, content=hostile).body
    assert isinstance(body, bytes)
    json.loads(body.decode("utf-8"))  # strictly decodable + parseable


def test_sanitizer_scrubs_surrogate_strings():
    out = server._sanitize_validation_payload({"input": "a" + LO + "b", "nested": [HI]})
    json.dumps(out, ensure_ascii=False).encode("utf-8")
    assert LO not in out["input"] and HI not in out["nested"][0]


def test_ingress_model_rejects_surrogates_with_422(client):
    body = json.dumps({"ext_id": "x", "field_name": LO, "original": "a", "corrected": "b", "reason": "c"})
    r = client.post("/correct", content=body, headers=JSON)
    assert r.status_code == 422
    assert "surrogate" in r.text


def test_surrogate_burst_100_workers_zero_5xx_and_recovery_slo(client):
    bodies = list(VECTORS.values())
    lat, codes = [], []

    def hit(i):
        t = time.perf_counter()
        r = client.post(ROUTES[i % len(ROUTES)], content=bodies[i % len(bodies)], headers=JSON)
        return r.status_code, (time.perf_counter() - t) * 1000

    with ThreadPoolExecutor(max_workers=100) as pool:
        for code, ms in pool.map(hit, range(600)):
            codes.append(code)
            lat.append(ms)
    assert not any(c >= 500 for c in codes), set(codes)
    assert client.get("/healthz").status_code == 200  # still alive afterwards
    q = quantiles(lat, n=100)
    assert q[49] < 200, ("P50 error-recovery SLO", q[49], q[94], q[98])


def test_chaotic_human_journey_stays_up(client):
    # rapid double-submit hostile payload, abandon, then conflicting state updates
    for _ in range(2):
        assert client.post("/demo", content=VECTORS["value_lone_low"], headers=JSON).status_code < 500
    assert client.post("/apply", json={"ext_id": "nope", "accept": True}).status_code < 500
    assert client.post("/apply", json={"ext_id": "nope", "accept": False}).status_code < 500
    assert client.get("/healthz").status_code == 200
    assert client.get("/metrics").status_code == 200


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("body", ["[" * 5000 + "]" * 5000, '{"a":' * 3000 + "1" + "}" * 3000, json.dumps({"file": "x"} if False else {"q": [[[[[[LO]]]]]]})])
def test_nesting_bomb_and_deep_surrogate_never_5xx(client, route, body):
    r = client.post(route, content=body, headers=JSON)
    assert r.status_code in (400, 404, 422), (route, r.status_code, r.text[:200])


def test_contains_surrogate_is_iterative_and_depth_bounded():
    deep = {"a": 1}
    for _ in range(5000):
        deep = {"a": deep}
    with pytest.raises(ValueError, match="nesting"):
        server._contains_surrogate(deep)
    assert server._contains_surrogate({"k": [{"x": (LO,)}]}) is True
    assert server._contains_surrogate({"k": [{"x": ("ok",)}]}) is False


def test_sanitizer_is_depth_capped_no_recursion_error():
    deep = ["x"]
    for _ in range(5000):
        deep = [deep]
    out = server._sanitize_validation_payload({"input": deep})
    json.dumps(out)  # never raises, never RecursionError
