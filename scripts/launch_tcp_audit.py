"""Bounded loopback-only launch audit. Synthetic clients, never real humans.
Run: python3 scripts/launch_tcp_audit.py --output runs/launch-tcp.json
Requires uvicorn, psutil and the overlay's dependencies. Nonzero means NO-GO.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import psutil

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ['/demo', '/apply', '/correct', '/api/extract-document', '/api/ask-document', '/api/graph/query']
FUZZ = [b'{', b'[]', b'null', b'', b'\xff', b'{"file":123}',
        b'{"file":"\\udcff"}', b'{"\\ud800":1}',
        b'{"file":"' + b'x'*10000 + b'"}', b'{"file":"a","n":1e999}',
        b'{"file":' + b'['*80 + b'0' + b']'*80 + b'}', b'{"query":{}}']

def percentile(values, q):
    values = sorted(values)
    return round(values[min(len(values)-1, int((len(values)-1)*q))], 3) if values else None

def summarize(rows, wall):
    codes = {}
    for row in rows:
        key = str(row['status'])
        codes[key] = codes.get(key, 0) + 1
    lat = [r['ms'] for r in rows]
    return dict(n=len(rows), codes=codes, wall_s=round(wall,3),
                rps=round(len(rows)/wall,2), p50_ms=percentile(lat,.5),
                p95_ms=percentile(lat,.95), p99_ms=percentile(lat,.99),
                max_ms=max(lat,default=0), transport_errors=sum(r['status']==-1 for r in rows),
                server_errors=sum(r['status']>=500 for r in rows))

def gate(report):
    failures=[]
    required={'health_1_client','health_100_clients','fuzz_100_clients','synthetic_120_clients','extraction_queue_100_clients','recovery'}
    if not required.issubset(report.get('scenarios',{})):
        failures.append('scenarios: incomplete')
    if report.get('personas_completed') != 120:
        failures.append('personas: incomplete')
    if set(report.get('probes',{})) != {'/healthz','/livez','/readyz','/metrics'}:
        failures.append('probes: incomplete')
    for name, group in report['scenarios'].items():
        if group['server_errors'] or group['transport_errors']:
            failures.append(name+': request errors')
    if report['scenarios'].get('recovery',{}).get('max_ms',float('inf')) >= 200:
        failures.append('recovery: at least one request >=200ms')
    if any(c != 200 for c in report['probes'].values()):
        failures.append('probes: not all ready')
    if (report.get('shutdown_exit') not in (0, -15) or not report.get('shutdown_complete')) or report.get('shutdown_s',99) > 25:
        failures.append('shutdown: unclean or deadline exceeded')
    if report.get('server_exception_markers'):
        failures.append('server: unhandled exception marker')
    if report.get('personas_completed') == 120 and report['scenarios'].get('synthetic_120_clients',{}).get('n') != 3000:
        failures.append('requests: missing recorded persona outcomes')
    if report.get('fd_growth', 1) > 0:
        failures.append('resources: FD growth requires investigation')
    return failures

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='runs/launch-tcp.json')
    args=parser.parse_args()
    output=Path(args.output).resolve(); output.parent.mkdir(parents=True,exist_ok=True)
    log=output.with_suffix('.server.log')
    report={'scope':'local real TCP; 120 seeded synthetic clients; not 100x measured production load',
            'scenarios':{}, 'probes':{}, 'resources':[], 'personas':120,
            'personas_completed':0, 'external_model_calls':0}
    with tempfile.TemporaryDirectory(prefix='axiom-audit-') as tmp, open(log,'wb') as logs:
        fixture=Path(tmp)/'memo.txt'
        fixture.write_text('CLASSIFIED MEMORANDUM\nTo: Engineering\nFrom: Operations\nDate: September 16, 2026\nSubject: Launch review\nClassification: CONFIDENTIAL\nAction required: Review the release before September 18, 2026.\n')
        key='loopback-audit-only'
        env=dict(os.environ, AXIOM_API_KEYS=key, AXIOM_REQUIRE_AUTH='1',
                 AXIOM_STATE_DIR=tmp, AXIOM_EXTRACTION_WORKERS='8',
                 AXIOM_EXTRACTION_QUEUE_DEPTH='64', AXIOM_PIPELINE_CONCURRENCY='16',
                 AXIOM_RATE_LIMIT_PER_MIN='1000000', AXIOM_RATE_LIMIT_PER_MIN_AUTH='1000000',
                 AXIOM_LOG_LEVEL='WARNING')
        # Never inherit live model credentials into a synthetic load test.
        for name in ('MELIOUS_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY'):
            env.pop(name,None)
        listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(2048)
        port=listener.getsockname()[1]
        shutdown_marker=Path(tmp)/'lifespan-completed'
        launcher='''import contextlib,sys
from pathlib import Path
import uvicorn
from overlay.server import app
original=app.router.lifespan_context
@contextlib.asynccontextmanager
async def observed_lifespan(app):
    async with original(app):
        yield
    Path(sys.argv[2]).write_text("completed")
app.router.lifespan_context=observed_lifespan
uvicorn.run(app,fd=int(sys.argv[1]),log_level="warning")
'''
        proc=subprocess.Popen([sys.executable,'-c',launcher,str(listener.fileno()),str(shutdown_marker)],
                              cwd=ROOT,env=env,pass_fds=(listener.fileno(),),stdout=logs,stderr=logs)
        listener.close(); process=psutil.Process(proc.pid)
        def request(path, body=None, timeout=10, content_type='application/json'):
            start=time.perf_counter()
            req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=body,
                    headers={'Content-Type':content_type,'Authorization':'Bearer '+key})
            status=-1
            try:
                with urllib.request.urlopen(req,timeout=timeout) as response:
                    status=response.status; response.read()
            except urllib.error.HTTPError as error:
                with error:
                    status=error.code; error.read()
            except (OSError,TimeoutError):
                pass
            return {'status':status,'ms':round((time.perf_counter()-start)*1000,3)}
        stop=threading.Event()
        def sample():
            while not stop.is_set():
                try:
                    report['resources'].append({'t':round(time.monotonic(),3),'rss_mb':round(process.memory_info().rss/1048576,2),
                        'fds':process.num_fds(),'threads':process.num_threads()})
                except psutil.Error:
                    return
                stop.wait(.05)
        sampler=None
        try:
            deadline=time.monotonic()+45
            while request('/healthz',timeout=.2)['status']!=200:
                if proc.poll() is not None or time.monotonic()>deadline:
                    raise RuntimeError('startup failed; inspect server log')
                stop.wait(.05)
            body=json.dumps({'file':str(fixture)}).encode()
            for route in ['/readyz','/metrics']:
                request(route)
            request('/demo',body)
            fd_base=process.num_fds()
            sampler=threading.Thread(target=sample); sampler.start()
            def burst(name, jobs, concurrency):
                start=time.perf_counter()
                with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                    rows=list(pool.map(lambda job: request(*job),jobs))
                report['scenarios'][name]=summarize(rows,time.perf_counter()-start)
                report['scenarios'][name]['concurrency']=concurrency
            burst('health_1_client',[('/healthz',)]*200,1)
            burst('health_100_clients',[('/healthz',)]*1000,100)
            burst('fuzz_100_clients',[(ROUTES[i%6],FUZZ[(i//6)%len(FUZZ)]) for i in range(720)],100)
            burst('extraction_queue_100_clients',[('/api/extract-document',body)]*200,100)
            def persona(pid):
                rng=random.Random(pid); rows=[]
                for step in range(20):
                    style=(pid+step)%8
                    if style==0:
                        rows.extend([request('/demo',body),request('/demo',body)])
                    elif style==1:
                        for accept in [True,False]:
                            rows.append(request('/apply',json.dumps({'ext_id':f'missing-{pid}','accept':accept}).encode()))
                    elif style==2:
                        # Close a real request socket without reading a response.
                        with socket.create_connection(('127.0.0.1',port),timeout=2) as sock:
                            sock.sendall(b'POST /demo HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer '+key.encode()+b'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
                        rows.append(request('/healthz'))
                    elif style==3:
                        rows.append(request(rng.choice(ROUTES),rng.choice(FUZZ)))
                    elif style==4:
                        rows.append(request('/demo',body,10,'text/plain'))
                    elif style==5:
                        rows.append(request('/api/ask-document',json.dumps({'doc_id':f'ghost-{pid}','question':'What changed?'}).encode()))
                    elif style==6:
                        rows.append(request('/metrics'))
                    else:
                        rows.append(request('/'))
                return rows
            start=time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=120) as pool:
                groups=list(pool.map(persona,range(120)))
            report['personas_completed']=len(groups)
            report['scenarios']['synthetic_120_clients']=summarize([row for group in groups for row in group],time.perf_counter()-start)
            report['abandoned_requests_sent']=300
            burst('recovery',[(ROUTES[i%6],b'{') for i in range(120)],1)
            report['probes']={path:request(path)['status'] for path in ['/healthz','/livez','/readyz','/metrics']}
            # This is an observation, not proof of socket/coroutine leak freedom.
            report['fd_targets_before_drain']={str(x):os.readlink(x) for x in Path(f'/proc/{proc.pid}/fd').iterdir() if x.exists()}
            drain_deadline=time.monotonic()+2
            while process.num_fds()>fd_base and time.monotonic()<drain_deadline:
                stop.wait(.01)  # bounded observation polling, not a runtime workaround
            report['fd_base']=fd_base; report['fd_after']=process.num_fds()
            report['fd_growth']=report['fd_after']-fd_base
        except Exception as exc:
            report['harness_error']=type(exc).__name__+': '+str(exc)
        finally:
            stop.set()
            if sampler: sampler.join(timeout=2)
            start=time.perf_counter(); proc.terminate()
            try: proc.wait(timeout=25)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=5)
            report['shutdown_s']=round(time.perf_counter()-start,3)
            report['shutdown_exit']=proc.returncode
        text=log.read_text(errors='replace')
        report['shutdown_complete']=shutdown_marker.exists()
        report['server_exception_markers']={marker:text.count(marker) for marker in
            ['Traceback (most recent call last)','Task exception was never retrieved','Task was destroyed but it is pending','Exception in ASGI application'] if marker in text}
        if report['resources']:
            report['rss_floor_mb']=min(x['rss_mb'] for x in report['resources'])
            report['rss_ceiling_mb']=max(x['rss_mb'] for x in report['resources'])
        report['failures']=gate(report) if 'recovery' in report['scenarios'] else ['harness incomplete']
        if 'harness_error' in report: report['failures'].append(report['harness_error'])
        report['passed']=not report['failures']
        output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='resources'},indent=2))
        return int(not report['passed'])

if __name__=='__main__':
    raise SystemExit(main())
