/* Independent native Node HTTP client diagnostic; loopback only, no provider.
   Does not replace the full Python torture gates or simulate recruited humans. */
import http from 'node:http';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn,spawnSync} from 'node:child_process';
import {performance} from 'node:perf_hooks';
import {once} from 'node:events';

const args=process.argv.slice(2);
const option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const repo=path.resolve(option('--repo',process.cwd()));
const output=path.resolve(option('--output','ingress-diagnostic.json'));
const concurrency=Number(option('--concurrency','100'));
const full=args.includes('--full');
const correctionStatus=Number(option('--unknown-correction-status','404'));
if(!Number.isInteger(concurrency)||concurrency<1||concurrency>1000)throw new Error('concurrency must be 1..1000');
const reservation=net.createServer();reservation.listen(0,'127.0.0.1');await once(reservation,'listening');
const port=reservation.address().port;await new Promise(resolve=>reservation.close(resolve));
const state=fs.mkdtempSync(path.join(os.tmpdir(),'axiom-native-load-'));
fs.mkdirSync(path.dirname(output),{recursive:true});
const fd=fs.openSync(`${output}.server.log`,'w');
const lifecycleFile=path.join(state,'shutdown.json');
const env={...process.env,AXIOM_STATE_DIR:state,AXIOM_REQUIRE_AUTH:'1',AXIOM_API_KEYS:'local-native-diagnostic-only',AXIOM_RATE_LIMIT_PER_MIN_AUTH:'20000',AXIOM_LIFECYCLE_FILE:lifecycleFile};
delete env.MELIOUS_API_KEY;delete env.KAIRO_GATEWAY_TEST_MODE;
const child=spawn(process.env.PYTHON||'python3',['-m','uvicorn','overlay.server:app','--host','127.0.0.1','--port',String(port),'--no-access-log'],{cwd:repo,env,stdio:['ignore',fd,fd]});
let spawnError=null;
const closed=new Promise(resolve=>{
    child.once('error',error=>{spawnError=error;resolve([-1,'SPAWN_ERROR']);});
    child.once('close',(code,signal)=>resolve([code,signal]));
});
const agent=new http.Agent({keepAlive:true,maxSockets:concurrency,maxFreeSockets:concurrency});
const quantiles=values=>{
    const sorted=values.slice().sort((a,b)=>a-b);
    return Object.fromEntries([['p50',.5],['p95',.95],['p99',.99],['max',1]].map(([k,q])=>[k,sorted.length?sorted[Math.ceil(sorted.length*q)-1]:null]));
};
function request(method,url,payload,expected){
    return new Promise(resolve=>{
        const body=payload===undefined?undefined:Buffer.from(JSON.stringify(payload));
        const headers={Authorization:'Bearer local-native-diagnostic-only'};
        if(body){headers['Content-Type']='application/json';headers['Content-Length']=String(body.length);}
        const started=performance.now();
        const req=http.request({host:'127.0.0.1',port,path:url,method,headers,agent},res=>{
            // Only capture bounded aggregate telemetry, never document bodies.
            const chunks=[];let bytes=0;
            if(url==='/metrics')res.on('data',chunk=>{
                bytes+=chunk.length;
                if(bytes<=512*1024)chunks.push(chunk);
            });
            else res.resume();
            res.on('end',()=>{
                let telemetry=null;
                if(url==='/metrics'&&bytes<=512*1024){
                    try{telemetry=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{}
                }
                resolve({status:res.statusCode,ms:performance.now()-started,
                mismatch:expected ? !expected.includes(res.statusCode) : false,
                telemetry,
                server_ms:Number(res.headers['server-timing']?.match(/app;dur=([0-9.]+)/)?.[1]),
                admission_ms:Number(res.headers['server-timing']?.match(/admission;dur=([0-9.]+)/)?.[1])});
            });
            res.on('error',()=>resolve({status:0,ms:performance.now()-started,server_ms:NaN,mismatch:Boolean(expected)}));
        });
        req.setTimeout(30000,()=>req.destroy(new Error('deadline')));
        req.on('error',()=>resolve({status:0,ms:performance.now()-started,server_ms:NaN,mismatch:Boolean(expected)}));
        req.end(body);
    });
}
const report={commit:spawnSync('git',['rev-parse','HEAD'],{cwd:repo,encoding:'utf8'}).stdout.trim(),working_tree_dirty:Boolean(spawnSync('git',['status','--porcelain'],{cwd:repo,encoding:'utf8'}).stdout.trim()),scope:full ? 'independent native Node HTTP full-workload loopback diagnostic; scripted identities, not humans' : 'independent native Node HTTP loopback ingress diagnostic',concurrency,synthetic_personas:full?120:0,unknown_correction_expected_status:correctionStatus,phases:[]};
try{
    const deadline=performance.now()+20000;
    while((await request('GET','/readyz')).status!==200){
        if(performance.now()>deadline||child.exitCode!==null||spawnError)throw new Error('readiness deadline');
        await new Promise(resolve=>setTimeout(resolve,50));
    }
    function summarize(name,results,started){
        const statuses={};for(const item of results)statuses[item.status]=(statuses[item.status]||0)+1;
        report.phases.push({name,requests:results.length,statuses,throughput_rps:results.length/(performance.now()-started)*1000,
            status_mismatches:results.filter(r=>r.mismatch).length,
            error_latency_ms:quantiles(results.filter(r=>r.status>=400).map(r=>r.ms)),
            successful_latency_ms:quantiles(results.filter(r=>r.status>=200&&r.status<300).map(r=>r.ms)),
            latency_ms:quantiles(results.map(r=>r.ms)),server_policy_to_headers_ms:quantiles(results.map(r=>r.server_ms).filter(Number.isFinite)),
            server_admission_wait_ms:quantiles(results.map(r=>r.admission_ms).filter(Number.isFinite))});
    }
    async function phase(name,items){
        let cursor=0;const results=[];const started=performance.now();
        await Promise.all(Array.from({length:concurrency},async()=>{
            while(cursor<items.length){const i=cursor++;results.push(await request(...items[i]));}
        }));
        summarize(name,results,started);
    }
    async function personas(groups){
        let active=0,peak=0;const waiting=[];const started=performance.now();
        async function measured(item){
            if(active>=concurrency)await new Promise(resolve=>waiting.push(resolve));
            else active++;
            peak=Math.max(peak,active);
            try{return await request(...item);}
            finally{if(waiting.length)waiting.shift()();else active--;}
        }
        const results=await Promise.all(groups.map(async items=>{
            const rows=[];for(const item of items)rows.push(await measured(item));return rows;
        }));
        report.persona_peak_measured_requests=peak;
        summarize('120_synthetic_personas',results.flat(),started);
    }
    await phase('health',Array.from({length:1000},()=>['GET','/healthz',undefined,[200]]));
    const hostile=[['POST','/api/extract-document',{file:''}],['POST','/api/extract-document',{file:'/etc/passwd'}],
        ['POST','/api/extract-document',{file:'a\0b'}],['POST','/api/extract-document',{file:'\ud800'}],
        ['POST','/api/extract-document',{file:['wrong']}],['POST','/api/ask-document',{file:'sample_memo_01.txt',question:''}]];
    await phase('hostile',Array.from({length:600},(_,i)=>[...hostile[i%hostile.length],[i%hostile.length===1?404:422]]));
    if(full){
        await phase('extraction_burst',Array.from({length:300},()=>['POST','/api/extract-document',{file:'sample_memo_01.txt'},[200]]));
        const personaItems=[];
        for(let identity=0;identity<120;identity++){
            const items=[];
            for(let step=0;step<20;step++){
                const choice=(identity+step)%6;
                if(choice===0)items.push(['GET','/healthz',undefined,[200]]);
                else if(choice===1)items.push(['POST','/api/extract-document',{file:'sample_memo_01.txt'},[200]]);
                else if(choice===2)items.push([...hostile[(identity+step)%hostile.length],[422]]);
                else if(choice===3)items.push(['POST','/correct',{ext_id:`conflict-${identity%10}`,field_name:'author',original:'original',corrected:`user-${identity}-step-${step}`,reason:'synthetic conflicting update'},[correctionStatus]]);
                else if(choice===4)items.push(['POST','/api/ask-document',{file:'sample_memo_01.txt',question:'What is the author?'},[200]]);
                else items.push(['GET','/api/source/missing',undefined,[404]]);
            }
            personaItems.push(items);
        }
        // Each identity runs its 20 actions sequentially. An event-driven
        // request gate caps actual measured calls before starting the timer.
        await personas(personaItems);
        await Promise.all(Array.from({length:120},()=>new Promise((resolve,reject)=>{
            const socket=net.connect(port,'127.0.0.1');
            socket.on('error',reject);socket.on('close',resolve);
            socket.on('connect',()=>{
                const body=JSON.stringify({file:'sample_memo_01.txt'});
                socket.end(`POST /api/extract-document HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: Bearer local-native-diagnostic-only\r\nContent-Type: application/json\r\nContent-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`);
                socket.destroy();
            });
        })));
        report.abandoned_sessions=120;
        await phase('post_abandon_recovery',Array.from({length:200},()=>['GET','/healthz',undefined,[200]]));
        report.diagnostic_gates={workload_complete:report.phases.length===5,
            no_status_mismatches:report.phases.every(p=>p.status_mismatches===0),
            zero_timed_5xx:report.phases.every(p=>Object.entries(p.statuses).every(([s,n])=>!(Number(s)>=500&&n))),
            zero_transport_errors:report.phases.every(p=>!p.statuses[0]),
            loaded_error_max_below_200ms:report.phases.every(p=>p.error_latency_ms.max===null||p.error_latency_ms.max<200)};
        report.scope_warning='120 deterministic script identities, not recruited humans or a soak/leak certification; provider traffic disabled.';
    }
    const telemetry=await request('GET','/metrics',undefined,[200]);
    if(telemetry.status!==200||!telemetry.telemetry||typeof telemetry.telemetry.errors_total!=='number'){
        throw new Error('all-server telemetry unavailable');
    }
    report.metrics=telemetry.telemetry;
    if(report.diagnostic_gates)report.diagnostic_gates.zero_all_server_5xx=report.metrics.errors_total===0;
}catch(error){report.harness_error=error.message;process.exitCode=1;}
finally{
    agent.destroy();
    const started=performance.now();child.kill('SIGTERM');
    const timer=setTimeout(()=>child.kill('SIGKILL'),10000);
    const [code,signal]=await closed;clearTimeout(timer);
    report.shutdown={code,signal,ms:performance.now()-started};
    let marker=null;
    try{marker=JSON.parse(fs.readFileSync(lifecycleFile,'utf8'));}catch{}
    report.shutdown.marker=marker;
    if(report.diagnostic_gates){
        report.diagnostic_gates.clean_worker_shutdown=Boolean(marker?.workers_joined&&marker?.state_closed&&signal!=='SIGKILL');
        const serverLog=fs.readFileSync(`${output}.server.log`,'utf8');
        report.diagnostic_gates.no_observed_unhandled_exceptions=!/Exception in ASGI application|Task exception was never retrieved|Fatal Python error/.test(serverLog);
        report.diagnostic_gates.no_harness_error=!report.harness_error;
        report.passed_requested_bounds=Object.values(report.diagnostic_gates).every(Boolean);
        if(!report.passed_requested_bounds)process.exitCode=1;
    }
    fs.closeSync(fd);fs.rmSync(state,{recursive:true,force:true});
    fs.writeFileSync(output,JSON.stringify(report,null,2));
    console.log(JSON.stringify({output,phases:report.phases}));
}