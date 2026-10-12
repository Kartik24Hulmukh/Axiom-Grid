"""Bounded loopback TCP torture: 100 clients, 120 synthetic personas.
No production endpoint, provider key, recruited-human or 100x-scale claim.
Exit 1 on strict requested launch-bound failures; always persist evidence.
"""
from __future__ import annotations
import argparse
import asyncio
from collections import Counter
import json
import math
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import psutil


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return {}
    return {name: round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 3)
            for name, fraction in [('p50', .50), ('p95', .95), ('p99', .99), ('max', 1)]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--output', required=True)
    parser.add_argument('--concurrency', type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 1000:
        parser.error('concurrency must be 1..1000')
    repo = Path(args.repo).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    auth = {'Authorization': 'Bearer local-torture-only'}
    report = {'scope': 'loopback TCP, synthetic users, no live provider',
              'concurrency': args.concurrency, 'synthetic_personas': 120,
              'baseline_concurrency_for_100x': None,
              'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
              'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo)),
              'phases': []}
    samples = []
    shutdown_timeout = False
    with tempfile.TemporaryDirectory(prefix='axiom-load-') as temporary:
        env = {**os.environ, 'AXIOM_REQUIRE_AUTH': '1', 'AXIOM_API_KEYS': 'local-torture-only',
               'AXIOM_STATE_DIR': temporary, 'AXIOM_RATE_LIMIT_PER_MIN_AUTH': '20000',
               'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
               'AXIOM_LIFECYCLE_FILE': str(Path(temporary) / 'shutdown.json')}
        env.pop('MELIOUS_API_KEY', None)
        env.pop('KAIRO_GATEWAY_TEST_MODE', None)
        log_path = output.with_suffix('.server.log')
        with log_path.open('wb') as log:
            process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'overlay.server:app',
                '--host', '127.0.0.1', '--port', str(port), '--no-access-log'], cwd=repo,
                env=env, stdout=log, stderr=log)
            base = f'http://127.0.0.1:{port}'
            monitor = psutil.Process(process.pid)
            async def exercise():
                stop = asyncio.Event()
                async def sample():
                    while not stop.is_set():
                        try:
                            samples.append({'rss': monitor.memory_info().rss, 'fd': monitor.num_fds(),
                                            'threads': monitor.num_threads()})
                        except psutil.Error:
                            return
                        await asyncio.sleep(.05)
                sampler = None
                limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
                async with httpx.AsyncClient(base_url=base, headers=auth, timeout=30, limits=limits) as client:
                    for _ in range(200):
                        try:
                            if (await client.get('/readyz')).status_code == 200:
                                break
                        except httpx.HTTPError:
                            if process.poll() is not None:
                                raise RuntimeError('server exited during startup')
                        await asyncio.sleep(.05)
                    else:
                        raise RuntimeError('readiness deadline exceeded')
                    report['idle_before'] = {'fd': monitor.num_fds(), 'rss': monitor.memory_info().rss}
                    sampler = asyncio.create_task(sample())
                    semaphore = asyncio.Semaphore(args.concurrency)
                    async def request(item):
                        method, path, payload, expected = item
                        async with semaphore:
                            started = time.perf_counter()
                            try:
                                kwargs = {} if payload is None else {'content': json.dumps(payload, ensure_ascii=True).encode(), 'headers': {'Content-Type': 'application/json'}}
                                result = await client.request(method, path, **kwargs)
                                code = result.status_code
                                # Read entire response before returning the slot.
                                result.read()
                                timing = re.search(r'(?:^|,)\s*app;dur=([0-9.]+)', result.headers.get('server-timing', ''))
                                return code, (time.perf_counter() - started) * 1000, code not in expected, float(timing[1]) if timing else None
                            except httpx.HTTPError:
                                return 0, (time.perf_counter() - started) * 1000, True, None
                    async def phase(name, items):
                        started = time.perf_counter()
                        results = await asyncio.gather(*(request(item) for item in items))
                        elapsed = time.perf_counter() - started
                        row = {'name': name, 'requests': len(results), 'statuses': dict(Counter(r[0] for r in results)),
                               'status_mismatches': sum(r[2] for r in results),
                               'throughput_rps': round(len(results) / elapsed, 2),
                               'latency_ms': quantiles([r[1] for r in results]),
                               'error_latency_ms': quantiles([r[1] for r in results if r[0] >= 400]),
                               'server_policy_to_headers_ms': quantiles([r[3] for r in results if r[3] is not None]),
                               'rss': monitor.memory_info().rss, 'fd': monitor.num_fds()}
                        report['phases'].append(row)
                    await phase('health', [('GET', '/healthz', None, {200})] * 1000)
                    hostile = [
                        ('POST', '/api/extract-document', {'file': ''}, {422}),
                        ('POST', '/api/extract-document', {'file': '/etc/passwd'}, {404}),
                        ('POST', '/api/extract-document', {'file': 'a\x00b'}, {422}),
                        ('POST', '/api/extract-document', {'file': '\ud800'}, {422}),
                        ('POST', '/api/extract-document', {'file': ['wrong']}, {422}),
                        ('POST', '/api/ask-document', {'file': 'sample_memo_01.txt', 'question': ''}, {422}),
                    ]
                    await phase('hostile', hostile * 100)
                    await phase('extraction_burst', [('POST', '/api/extract-document', {'file': 'sample_memo_01.txt'}, {200})] * 300)
                    # 120 stateful script identities with distinct correction
                    # values and staggered actions. Unknown IDs MUST return404;
                    # real CAS races are independently tested against known IDs.
                    # These are not humans.
                    async def persona(identity):
                        items = []
                        for step in range(20):
                            choice = (identity + step) % 6
                            if choice == 0:
                                item = ('GET', '/healthz', None, {200})
                            elif choice == 1:
                                item = ('POST', '/api/extract-document', {'file': 'sample_memo_01.txt'}, {200})
                            elif choice == 2:
                                item = hostile[(identity + step) % len(hostile)]
                            elif choice == 3:
                                item = ('POST', '/correct', {'ext_id': f'conflict-{identity % 10}', 'field_name': 'author',
                                    'original': 'original', 'corrected': f'user-{identity}-step-{step}', 'reason': 'synthetic conflicting update'}, {404})
                            elif choice == 4:
                                item = ('POST', '/api/ask-document', {'file': 'sample_memo_01.txt', 'question': 'What is the author?'}, {200})
                            else:
                                item = ('GET', '/api/source/missing', None, {404})
                            items.append(await request(item))
                        return items
                    start = time.perf_counter()
                    groups = await asyncio.gather(*(persona(i) for i in range(120)))
                    results = [row for group in groups for row in group]
                    report['phases'].append({'name': '120_synthetic_personas', 'requests': len(results),
                        'statuses': dict(Counter(r[0] for r in results)), 'status_mismatches': sum(r[2] for r in results),
                        'latency_ms': quantiles([r[1] for r in results]),
                        'error_latency_ms': quantiles([r[1] for r in results if r[0] >= 400]),
                        'server_policy_to_headers_ms': quantiles([r[3] for r in results if r[3] is not None]),
                        'throughput_rps': round(len(results)/(time.perf_counter()-start), 2)})
                    # Abandon in-flight TCP sessions. Record the subsequent
                    # recovery rather than misclassifying deliberate closes.
                    async def abandon(_):
                        reader, writer = await asyncio.open_connection('127.0.0.1', port)
                        body = json.dumps({'file': 'sample_memo_01.txt'}).encode()
                        writer.write(f'POST /api/extract-document HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer local-torture-only\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n'.encode()+body)
                        await writer.drain()
                        writer.close()
                        await writer.wait_closed()
                    await asyncio.gather(*(abandon(i) for i in range(120)))
                    report['abandoned_sessions'] = 120
                    await phase('post_abandon_recovery', [('GET', '/healthz', None, {200})] * 200)
                    report['metrics'] = (await client.get('/metrics')).json()
                if sampler:
                    stop.set()
                    await sampler
                # Client closure does not synchronously close server sockets.
                # Poll an actual quiescence condition, not an arbitrary grace
                # sleep or a single FD snapshot. Keep a bounded 5s deadline.
                drain_started = time.perf_counter()
                deadline = drain_started + 5
                while time.perf_counter() < deadline:
                    connections = monitor.net_connections(kind='tcp')
                    if not any(c.status != psutil.CONN_LISTEN for c in connections):
                        break
                    await asyncio.sleep(.01)
                connections = monitor.net_connections(kind='tcp')
                report['drain'] = {
                    'ms': round((time.perf_counter() - drain_started) * 1000, 3),
                    'remaining_tcp_sessions': sum(c.status != psutil.CONN_LISTEN for c in connections),
                }
                report['idle_after'] = {'fd': monitor.num_fds(), 'rss': monitor.memory_info().rss}
            try:
                asyncio.run(exercise())
                report['server_alive_after_workload'] = process.poll() is None
            except Exception as exc:
                report['harness_error'] = type(exc).__name__
            finally:
                start = time.perf_counter()
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    shutdown_timeout = True
                report['shutdown_ms'] = round((time.perf_counter() - start) * 1000, 3)
                report['shutdown_timeout'] = shutdown_timeout
                report['server_exit_code'] = process.returncode
                marker = Path(temporary) / 'shutdown.json'
                report['lifecycle'] = json.loads(marker.read_text()) if marker.exists() else {}
        text = log_path.read_text(errors='replace')
        markers = ['Exception in ASGI application', 'Task exception was never retrieved', 'Fatal Python error']
        report['unhandled_markers'] = {marker: text.count(marker) for marker in markers}
        report['application_shutdown_complete'] = 'Application shutdown complete.' in text
    if samples:
        report['resources'] = {'rss_floor': min(s['rss'] for s in samples), 'rss_ceiling': max(s['rss'] for s in samples),
            'fd_floor': min(s['fd'] for s in samples), 'fd_ceiling': max(s['fd'] for s in samples),
            'threads_ceiling': max(s['threads'] for s in samples), 'samples': len(samples)}
    report['strict_gates'] = {
        'no_harness_error': 'harness_error' not in report,
        'workload_complete': len(report['phases']) == 5,
        'no_status_mismatches': all(p['status_mismatches'] == 0 for p in report['phases']),
        'zero_5xx': all(not any(int(k) >= 500 and v for k,v in p['statuses'].items()) for p in report['phases'])
            and report.get('metrics', {}).get('errors_total', 1) == 0,
        'loaded_error_max_below_200ms': all(p['error_latency_ms'].get('max', 0) < 200 for p in report['phases']),
        'no_unhandled_exception_markers': not any(report['unhandled_markers'].values()),
        'clean_shutdown': not shutdown_timeout and report['server_exit_code'] in (0, -15)
            and report.get('lifecycle') == {'workers_joined': True, 'state_closed': True},
        'fd_returns_to_idle': report.get('drain', {}).get('remaining_tcp_sessions', 1) == 0
            and report.get('idle_after', {}).get('fd', 1) <= report.get('idle_before', {}).get('fd', 0),
    }
    report['passed_requested_bounds'] = all(report['strict_gates'].values())
    output.write_text(json.dumps(report, indent=2))
    print(json.dumps({'output':str(output), 'strict_gates':report['strict_gates'], 'phases':report['phases']}, indent=2))
    return 0 if report['passed_requested_bounds'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
