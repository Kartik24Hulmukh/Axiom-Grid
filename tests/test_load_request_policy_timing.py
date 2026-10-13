"""Request policy timing is scoped and never a wire/handler-only measurement."""
import asyncio
import logging
from collections import deque
from types import SimpleNamespace

import pytest
from starlette.responses import JSONResponse

from overlay.admission import AdmissionTiming, admission_timing
from overlay.request_policy import RequestPolicyMiddleware


def server_with(checks):
    return SimpleNamespace(
        _REQUEST_ID_MAX_LEN=64,
        OPS_METRICS={'requests_total': 0, 'latency_ms_total': 0.0,
                     'latency_samples': deque(maxlen=16), 'latency_ms_max': 0.0,
                     'status_counts': {}, 'errors_total': 0},
        logger=logging.getLogger('test.load.policy'),
        rate_limit_middleware=checks[0], api_key_auth_middleware=checks[1],
        enforce_origin_gate=checks[2], _auth_enabled=lambda: False,
    )


async def invoke(policy, path):
    sent = []
    scope = {'type': 'http', 'path': path, 'method': 'GET', 'headers': [],
             'scheme': 'http', 'server': ('localhost', 80), 'query_string': b''}

    async def receive():
        return {'type': 'http.request', 'body': b''}

    async def send(message):
        sent.append(message)

    await policy(scope, receive, send)
    return sent


@pytest.mark.asyncio
async def test_parallel_requests_do_not_share_queue_timing():
    arrived = asyncio.Queue()
    release = asyncio.Event()
    observed = []

    async def check(request, next_call):
        return await next_call(request)

    async def app(scope, receive, send):
        timing = admission_timing.get()
        observed.append(timing)
        timing.queue_wait_ms = 7.0 if scope['path'] == '/a' else 11.0
        arrived.put_nowait(True)
        await release.wait()
        await JSONResponse({'ok': True})(scope, receive, send)

    policy = RequestPolicyMiddleware(app, server_with([check] * 3))
    outer = AdmissionTiming(queue_wait_ms=999)
    token = admission_timing.set(outer)
    try:
        a = asyncio.create_task(invoke(policy, '/a'))
        b = asyncio.create_task(invoke(policy, '/b'))
        await arrived.get()
        await arrived.get()
        release.set()
        results = await asyncio.gather(a, b)
        for result, expected in zip(results, (b'7.000', b'11.000')):
            headers = dict(result[0]['headers'])
            assert headers[b'server-timing'].startswith(b'app;dur=')
            assert b'admission;dur=' + expected in headers[b'server-timing']
        assert observed[0] is not observed[1]
        assert admission_timing.get() is outer
        assert outer.queue_wait_ms == 999
    finally:
        admission_timing.reset(token)


@pytest.mark.asyncio
async def test_quota_rejection_precedence_and_headers_unchanged():
    called = []

    async def quota(request, next_call):
        called.append('quota')
        return JSONResponse({'detail': 'Too many requests'}, status_code=429,
                            headers={'Retry-After': '17'})

    async def forbidden(*args):
        raise AssertionError('auth/origin/app must not run after quota refusal')

    server = server_with([quota, forbidden, forbidden])
    results = await invoke(RequestPolicyMiddleware(forbidden, server), '/correct')
    headers = dict(results[0]['headers'])
    assert called == ['quota']
    assert results[0]['status'] == 429
    assert headers[b'retry-after'] == b'17'
    assert headers[b'x-content-type-options'] == b'nosniff'
    assert b'admission;dur=0.000' in headers[b'server-timing']
    assert server.OPS_METRICS['status_counts'] == {'429': 1}
    assert admission_timing.get() is None


@pytest.mark.asyncio
async def test_exception_restores_timing_context():
    async def check(request, next_call):
        return await next_call(request)

    async def app(*args):
        raise RuntimeError('failure')

    with pytest.raises(RuntimeError, match='failure'):
        await invoke(RequestPolicyMiddleware(app, server_with([check] * 3)), '/x')
    assert admission_timing.get() is None
