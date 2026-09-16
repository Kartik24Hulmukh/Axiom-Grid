import json,os,subprocess,sys,time,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
KEY=sys.argv[1]
REPO=os.path.abspath('Axiom-Grid'); os.chdir(REPO); sys.path.insert(0,REPO)
HOST,PORT='127.0.0.1',8991
def pct(v,q):
    v=sorted(v); i=(len(v)-1)*q; lo=int(i); hi=min(lo+1,len(v)-1); f=i-lo
    return round(v[lo]*(1-f)+v[hi]*f,1)
server=subprocess.Popen([sys.executable,'-m','uvicorn','overlay.server:app','--host',HOST,'--port',str(PORT),'--log-level','warning'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
for _ in range(120):
    try:
        urllib.request.urlopen('http://%s:%d/healthz'%(HOST,PORT),timeout=1); break
    except Exception: time.sleep(0.25)
rep={}
def post(path,body):
    req=urllib.request.Request('http://%s:%d%s'%(HOST,PORT,path),data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
    t0=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=30) as r: c=r.status; r.read()
    except urllib.error.HTTPError as e: c=e.code; e.read()
    except Exception: c=-1
    return c,(time.perf_counter()-t0)*1000
for tag,N,C in [('extract_burst_200',200,100),('extract_burst_400',400,100)]:
    with ThreadPoolExecutor(C) as p:
        res=list(p.map(lambda _: post('/api/extract-document',{'file':'fixtures/wedge/sample_memo_01.txt'}), range(N)))
    codes=Counter(c for c,_ in res); dts=[d for _,d in res]
    rep[tag]={'n':N,'conc':C,'codes':dict(codes),'p50':pct(dts,.5),'p95':pct(dts,.95),'p99':pct(dts,.99),'shed503':codes.get(503,0)}
lat=[post('/api/extract-document',{'file':'nope.txt'})[1] for _ in range(60)]
rep['error_recovery']={'p50':pct(lat,.5),'p95':pct(lat,.95),'p99':pct(lat,.99)}
for p in ('/healthz','/livez','/readyz','/metrics'):
    try:
        rep.setdefault('probes',{})[p]=urllib.request.urlopen('http://%s:%d%s'%(HOST,PORT,p),timeout=5).status
    except urllib.error.HTTPError as e: rep.setdefault('probes',{})[p]=e.code
server.terminate(); server.wait(10)
from kernel.sidecar.melious_router import MeliousModelRouter
r=MeliousModelRouter(timeout=20.0)
mel={}
for m in r.models:
    body=json.dumps({'model':m,'messages':[{'role':'user','content':'Reply with the single word: OK'}],'max_tokens':8,'temperature':0}).encode()
    req=urllib.request.Request(r.base_url+'/chat/completions',data=body,headers={'Content-Type':'application/json','Authorization':'Bearer '+KEY},method='POST')
    t0=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=40) as resp: c=resp.status; resp.read()
    except urllib.error.HTTPError as e: c=e.code; e.read()
    except Exception: c=-1
    mel[m]={'status':c,'ms':round((time.perf_counter()-t0)*1000,1)}
try:
    out=r.complete([{'role':'user','content':'Say OK'}])
    mel['router_complete']={'ok':True,'model':getattr(out,'model',None)}
except Exception as ex:
    mel['router_complete']={'ok':False,'err':str(ex)[:200]}
rep['melious_live']=mel
print(json.dumps(rep,indent=2))
os.makedirs('runs',exist_ok=True)
open('runs/session27_live_report.json','w').write(json.dumps(rep,indent=2))
