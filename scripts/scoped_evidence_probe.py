"""Real two-worker ownership, 100-way CAS and restart probe; loopback only."""
import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
import httpx

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo',default=str(Path(__file__).resolve().parents[1]))
parser.add_argument('--output',default='launch-evidence/scoped-evidence.json')
args=parser.parse_args()
repo=Path(args.repo).resolve();output=Path(args.output).resolve();out=output.parent;out.mkdir(parents=True,exist_ok=True)
a='axiom-scoped-chaos-fixture-alpha';b='axiom-scoped-chaos-fixture-bravo'
report={'scope':'two real loopback processes sharing one local volume; 100 synthetic concurrent review attempts; no external providers','tested_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()}

async def exercise():
    servers=[]
    with tempfile.TemporaryDirectory() as state:
        def launch(identity, port=None):
            if port is None:
                with socket.socket() as reserve:reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
            env={**os.environ,'AXIOM_STATE_DIR':state,'AXIOM_REQUIRE_AUTH':'1','AXIOM_API_KEYS':a+','+b,'AXIOM_RATE_LIMIT_PER_MIN_AUTH':'20000','AXIOM_EXTRACTION_ISOLATION':'process','AXIOM_LIFECYCLE_FILE':state+'/closed-'+identity+'.json'}
            env.pop('MELIOUS_API_KEY',None);env.pop('KAIRO_GATEWAY_TEST_MODE',None)
            log=open(out/('scoped-chaos-'+identity+'.server.log'),'wb')
            p=subprocess.Popen([sys.executable,'-m','uvicorn','overlay.server:app','--host','127.0.0.1','--port',str(port),'--no-access-log'],cwd=repo,env=env,stdout=log,stderr=log)
            server=(p,'http://127.0.0.1:'+str(port),log,port,identity);servers.append(server);return server
        async with httpx.AsyncClient(timeout=20,limits=httpx.Limits(max_connections=100,max_keepalive_connections=100)) as client:
            async def req(server, method, path, key=a, **kwargs):
                return await client.request(method,server[1]+path,headers={'Authorization':'Bearer '+key},**kwargs)
            async def ready(server):
                deadline=time.monotonic()+20
                while time.monotonic()<deadline:
                    try:
                        if (await req(server,'GET','/readyz')).status_code==200:return
                    except httpx.TransportError:pass
                    if server[0].poll() is not None:raise RuntimeError('server exited')
                    await asyncio.sleep(.05)
                raise RuntimeError('readiness deadline')
            try:
                one=launch('one');two=launch('two');await ready(one);await ready(two)
                fixture=(repo/'fixtures/wedge/sample_memo_01.txt').read_bytes()
                upload=await req(one,'POST','/api/documents?filename=owned.txt',content=fixture);assert upload.status_code==200
                ref=upload.json()['file'];extracted=await req(two,'POST','/api/extract-document',json={'file':ref});assert extracted.status_code==200,extracted.text
                data=extracted.json();field_name,field=next(iter(data['fields'].items()));source='/api/source/'+data['doc_id']
                original=(await req(one,'GET',source)).json()['source_text']
                report['other_credential_source_status']=(await req(one,'GET',source,key=b)).status_code
                report['other_credential_upload_status']=(await req(two,'POST','/api/extract-document',key=b,json={'file':ref})).status_code
                report['owner_other_worker_source_status']=(await req(one,'GET',source)).status_code
                async def review(i):
                    started=time.perf_counter();r=await req((one,two)[i%2],'POST','/correct',json={'ext_id':field['ext_id'],'field_name':field_name,'original':field['value'],'corrected':'review-'+str(i),'reason':'100-way CAS fixture','expected_revision':0})
                    return r.status_code,(time.perf_counter()-started)*1000
                results=await asyncio.gather(*(review(i) for i in range(100)))
                report['concurrent_review_statuses']=dict(Counter(status for status,_ in results))
                lat=sorted(ms for _,ms in results);report['review_wire_latency_ms']={name:lat[index] for name,index in [('p50',49),('p95',94),('p99',98),('max',99)]}
                current=(await req(two,'GET','/api/reviews/'+field['ext_id'])).json();report['review_revision']=current['revision']
                report['source_unchanged_after_review']=(await req(two,'GET',source)).json()['source_text']==original
                # Replace a real worker process; do not merely reopen a Python object.
                two[0].terminate();await asyncio.to_thread(two[0].wait,10);two[2].close()
                restarted=launch('restarted',two[3]);await ready(restarted)
                report['owner_source_after_process_restart_status']=(await req(restarted,'GET',source)).status_code
                report['review_revision_after_process_restart']=(await req(restarted,'GET','/api/reviews/'+field['ext_id'])).json()['revision']
                report['owned_upload_after_process_restart_status']=(await req(restarted,'POST','/api/extract-document',json={'file':ref})).status_code
                report['gates']={
                    'owner_source_shared_and_restarted':report['owner_other_worker_source_status']==report['owner_source_after_process_restart_status']==200,
                    'other_credential_denied':report['other_credential_source_status']==report['other_credential_upload_status']==404,
                    'exactly_one_cas_winner':report['concurrent_review_statuses']=={200:1,409:99},
                    'review_revision_durable':report['review_revision']==report['review_revision_after_process_restart']==1,
                    'immutable_source':report['source_unchanged_after_review'],
                    'owned_upload_durable':report['owned_upload_after_process_restart_status']==200}
                report['passed_scoped_gates']=all(report['gates'].values())
            finally:
                for p,base,log,port,identity in servers:
                    if p.poll() is None:p.terminate()
                    try:await asyncio.to_thread(p.wait,10)
                    except subprocess.TimeoutExpired:p.kill();await asyncio.to_thread(p.wait)
                    if not log.closed:log.close()
                report['shutdown']=[{'worker':identity,'exit_code':p.returncode} for p,_,_,_,identity in servers]
try:asyncio.run(exercise())
except Exception as exc:report['harness_error']=type(exc).__name__;report['passed_scoped_gates']=False
report.setdefault('gates',{})['clean_shutdown']=all(s['exit_code'] in (0,-15) for s in report.get('shutdown',[]))
report['passed_scoped_gates']=report.get('passed_scoped_gates',False) and report['gates']['clean_shutdown']
output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

raise SystemExit(0 if report["passed_scoped_gates"] else 1)
