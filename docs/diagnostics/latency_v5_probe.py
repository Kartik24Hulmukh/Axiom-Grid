"""Bounded causal diagnostic: actual offline extraction, never a load/SLO gate."""
import asyncio
import cProfile
import contextvars
import json
import pathlib
import pstats
import sys
import time
from collections import defaultdict
import httpx
from overlay import server

label = contextvars.ContextVar('diagnostic_label', default='unknown')
rows = defaultdict(dict)
profiles = []
acquire = server._admission.acquire
async def timed_acquire(*args, **kwargs):
    began = time.perf_counter()
    try:
        return await acquire(*args, **kwargs)
    finally:
        rows[label.get()].setdefault('acquires_ms', []).append((time.perf_counter()-began)*1000)
server._admission.acquire = timed_acquire
for lane in ('extraction', 'evidence'):
    pool = getattr(server, f'_{lane}_pool')
    submit = pool.submit
    def measured_submit(fn, *args, _submit=submit, _lane=lane, **kwargs):
        ident = label.get()
        queued = time.perf_counter()
        def run():
            began, cpu = time.perf_counter(), time.thread_time()
            profile = cProfile.Profile() if ident.startswith('profile') else None
            if profile:
                profile.enable()
            try:
                return fn(*args, **kwargs)
            finally:
                if profile:
                    profile.disable()
                    profiles.append(profile)
                rows[ident].setdefault('lanes', {})[_lane] = dict(executor_ms=(began-queued)*1000,
                                   worker_ms=(time.perf_counter()-began)*1000,
                                   thread_cpu_ms=(time.thread_time()-cpu)*1000)
        return _submit(run)
    pool.submit = measured_submit

async def main():
    lag = []
    active = True
    loop = asyncio.get_running_loop()
    def tick(expected):
        now = loop.time()
        lag.append(max(0, (now-expected)*1000))
        if active:
            loop.call_later(.005, tick, now+.005)
    loop.call_later(.005, tick, loop.time()+.005)
    async with server._lifespan(server.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://local') as client:
            async def req(ident, method, path, body=None):
                token = label.set(ident)
                began = time.perf_counter()
                try:
                    response = await client.request(method, path, json=body)
                    rows[ident].update(status=response.status_code, total_ms=(time.perf_counter()-began)*1000,
                                       timing=response.headers.get('server-timing'))
                    assert response.status_code == (422 if ident.startswith('invalid') else 404 if ident.startswith(('missing', 'denied')) else 200), response.text
                finally:
                    label.reset(token)
            await req('warmup', 'POST', '/api/extract-document', {'file':'sample_memo_01.txt'})
            for i in range(3):
                await req(f'serial-{i}', 'POST', '/api/extract-document', {'file':'sample_memo_01.txt'})
            await asyncio.gather(*(req(f'extract-{i}', 'POST', '/api/extract-document', {'file':'sample_memo_01.txt'}) for i in range(8)),
                                 req('invalid', 'POST', '/correct', {}),
                                 req('missing', 'GET', '/api/source/never-existed'), req('health', 'GET', '/healthz'),
                                 req('denied', 'POST', '/api/extract-document', {'file':'/etc/passwd'}))
            await req('profile-one', 'POST', '/api/extract-document', {'file':'sample_memo_01.txt'})
    active = False
    output = pathlib.Path(sys.argv[1])
    for i, profile in enumerate(profiles):
        profile.dump_stats(str(output.with_suffix(f'.{i}.pstats')))
        with output.with_suffix(f'.{i}.profile.txt').open('w') as f:
            pstats.Stats(profile, stream=f).strip_dirs().sort_stats('cumtime').print_stats(30)
    output.write_text(json.dumps({'scope':'17 real ASGI requests; eight extraction contenders, not TCP/100-client SLO',
                                'commit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip(),
                                'workers':server.EXTRACTION_WORKERS, 'loop_lag_max_ms':max(lag, default=0), 'rows':dict(rows)}, indent=2))
    print('Saved', output, 'max loop lag', max(lag, default=0))

if __name__ == '__main__':
    asyncio.run(main())
