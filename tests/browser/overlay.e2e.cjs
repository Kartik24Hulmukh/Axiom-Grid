/* Real loopback server/browser E2E; one explicitly labelled response-fuzz test. */
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const fs=require('node:fs'); const os=require('node:os');const path=require('node:path');const net=require('node:net');
const {chromium}=require('playwright');
const authenticatedMode=process.env.AXIOM_BROWSER_AUTH_TEST==='1';
const deploymentKey='axiom-browser-fixture-only';
let browser,server,base,state,log;
const repo=path.resolve(__dirname,'../..');
const errors=[];
before(async()=>{
    const reserve=net.createServer(); await new Promise(r=>reserve.listen(0,'127.0.0.1',r));
    const port=reserve.address().port; await new Promise(r=>reserve.close(r));base=`http://127.0.0.1:${port}`;
    state=fs.mkdtempSync(path.join(os.tmpdir(),'axiom-browser-'));
    log=fs.openSync(path.join(state,'server.log'),'w');
    const env={...process.env,AXIOM_STATE_DIR:state,AXIOM_RATE_LIMIT_PER_MIN:'20000'};
    delete env.MELIOUS_API_KEY;delete env.KAIRO_GATEWAY_TEST_MODE;delete env.AXIOM_API_KEYS;delete env.AXIOM_REQUIRE_AUTH;
    if(authenticatedMode){env.AXIOM_REQUIRE_AUTH='1';env.AXIOM_API_KEYS=deploymentKey;env.AXIOM_RATE_LIMIT_PER_MIN_AUTH='20000';}
    server=spawn(process.env.PYTHON || 'python3',['-m','uvicorn','overlay.server:app','--host','127.0.0.1','--port',String(port),'--no-access-log'],{cwd:repo,env,stdio:['ignore',log,log]});
    let ready=false;
    for(let i=0;i<200;i++){
        try {if((await fetch(`${base}/readyz`)).ok){ready=true;break;}}catch{}
        if(server.exitCode!==null)throw new Error('server exited before readiness');
        await new Promise(r=>setTimeout(r,50));
    }
    assert.ok(ready,'readiness deadline');
    browser=await chromium.launch({headless:true,args:['--no-sandbox'],...(process.env.AXIOM_BROWSER_EXECUTABLE_PATH?{executablePath:process.env.AXIOM_BROWSER_EXECUTABLE_PATH}:{})});
});
after(async()=>{
    if(browser)await browser.close();
    if(server&&server.exitCode===null){const exit=new Promise(r=>server.once('exit',r));server.kill();await exit;}
    if(log!==undefined)fs.closeSync(log);
    if(state)fs.rmSync(state,{recursive:true,force:true});
});
async function page(){const p=await browser.newPage();p.on('pageerror',e=>errors.push(e.message));return p;}
async function connect(p){
    if(!authenticatedMode)return;
    await p.locator('#connection-key').fill(deploymentKey);
    await p.locator('#connect-btn').click();
    await p.getByText('Connected with deployment authentication.',{exact:true}).waitFor();
    assert.equal(await p.locator('#connection-key').inputValue(),'');
}
async function processDocument(p){
    await p.goto(base);await connect(p);
    const response=p.waitForResponse(r=>r.url()===`${base}/demo`);
    await p.locator('#run-pipeline-btn').click();
    assert.equal((await response).status(),200);
    await p.locator('.card').first().waitFor();
}
test('real document pipeline, tabs and source evidence render without browser exceptions',async()=>{
    const p=await page();try{
        await processDocument(p);
        assert.match(await p.locator('#doc-content').innerText(),/MEMO|CLASSIFIED|SECRET/i);
        await p.locator('#tab-trace').click();await p.locator('.trace-node').first().waitFor();
        await p.locator('#tab-suggestions').click();
        await p.locator('.chip').first().click();
        await p.waitForFunction(()=>document.querySelector('.source-evidence').textContent.length>0);
        assert.equal(errors.length,0,errors.join('\n'));
    }finally{await p.close();}
});
test('100 synchronous rapid clicks send exactly one real pipeline request',async()=>{
    const p=await page();try{
        let calls=0;p.on('request',r=>{if(r.url()===`${base}/demo`)calls++;});await p.goto(base);await connect(p);
        await p.evaluate(()=>{for(let i=0;i<100;i++)document.getElementById('run-pipeline-btn').click();});
        await p.locator('.card').first().waitFor();assert.equal(calls,1);
        assert.equal(await p.locator('#run-pipeline-btn').isEnabled(),true);
    }finally{await p.close();}
});
test('missing document surfaces HTTP failure and restores controls',async()=>{
    const p=await page();try{
        await p.goto(base);await connect(p);
        await p.evaluate(()=>{const option=document.createElement('option');option.value='/etc/passwd';option.textContent='Missing document';document.getElementById('fixture-select').append(option);document.getElementById('fixture-select').value=option.value;});
        const result=p.waitForResponse(r=>r.url()===`${base}/demo`);
        await p.locator('#run-pipeline-btn').click();
        assert.equal((await result).status(),404);
        await p.waitForFunction(()=>document.getElementById('doc-content').textContent.includes('Unable to process'));
        assert.equal(await p.locator('#run-pipeline-btn').isEnabled(),true);
        assert.equal(await p.locator('.card').count(),0);
    }finally{await p.close();}
});
test('real correction records markup as text; native desktop action is explicitly gated',async()=>{
    const p=await page();try{
        await processDocument(p);
        await p.locator('.btn-accept').first().click();
        await p.waitForFunction(()=>document.querySelector('.request-error')?.textContent.includes('native writer'));
        const malicious='<img src=x onerror="window.pwned=1">';
        await p.locator('.btn-edit').first().click();await p.locator('#modal-corrected').fill(malicious);
        await p.locator('#modal-reason').fill('Browser safety regression');await p.locator('#modal-submit-btn').click();
        await p.waitForFunction(()=>!document.getElementById('edit-modal').classList.contains('open'));
        assert.equal(await p.locator('.card-value').first().innerText(),malicious);
        assert.equal(await p.locator('.card-value img').count(),0);
        assert.equal(await p.evaluate(()=>window.pwned),undefined);
        if(await p.locator('.btn-reject').count()){
            await p.locator('.btn-reject').first().click();
            await p.getByText('Rejected; correction recorded.').waitFor();
        }
    }finally{await p.close();}
});
test('isolated response-fuzz: hostile fields, identifiers and trace outputs cannot create HTML',async()=>{
    const p=await page();try{
        const payload='<img src=x onerror="window.pwned=1">';
        // This interception is a rendering security oracle, NOT a claim of
        // end-to-end document extraction or a real upstream action.
        await p.route(`${base}/demo`,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,document_text:payload,
            suggestions:[{ext_id:"id'\"<img>",field_name:payload,value:payload,confidence:.9,page:1,chunk_id:payload}],
            trace:{stages:[{name:payload,status:'ok',duration_ms:1,input_data:{value:payload},output_data:{value:payload}}]}})}));
        await processDocument(p);
        assert.equal(await p.locator('#doc-content').innerText(),payload);
        assert.equal(await p.locator('.card-value').innerText(),payload);
        await p.locator('#tab-trace').click();
        assert.equal(await p.locator('img').count(),0);
        assert.equal(await p.evaluate(()=>window.pwned),undefined);
        assert.equal(errors.length,0,errors.join('\n'));
    }finally{await p.close();}
});
test('mid-flight page abandonment does not prevent the next real session',async()=>{
    const p=await page();await p.goto(base);await connect(p);await p.locator('#run-pipeline-btn').click();await p.close();
    const next=await page();try{await processDocument(next);assert.equal(errors.length,0);}finally{await next.close();}
});
if(authenticatedMode)test('deployment key is checked, rejected on failure, forgotten and never persisted',async()=>{
    const p=await page();try{
        await p.goto(base);
        await p.locator('#connection-key').fill('wrong-fixture-key');await p.locator('#connect-btn').click();
        await p.waitForFunction(()=>document.getElementById('connection-status').textContent.includes('Connection rejected'));
        const rejected=p.waitForResponse(r=>r.url()===`${base}/demo`);await p.locator('#run-pipeline-btn').click();
        assert.equal((await rejected).status(),401);
        await connect(p);
        const success=p.waitForResponse(r=>r.url()===`${base}/demo`);await p.locator('#run-pipeline-btn').click();
        assert.equal((await success).status(),200);await p.locator('.card').first().waitFor();
        assert.deepEqual(await p.evaluate(()=>({local:localStorage.length,session:sessionStorage.length})),{local:0,session:0});
        await p.locator('#disconnect-btn').click();
        const forgotten=p.waitForResponse(r=>r.url()===`${base}/demo`);await p.locator('#run-pipeline-btn').click();
        assert.equal((await forgotten).status(),401);
        await connect(p);await p.reload();
        const reloaded=p.waitForResponse(r=>r.url()===`${base}/demo`);await p.locator('#run-pipeline-btn').click();
        assert.equal((await reloaded).status(),401);
        assert.equal(errors.length,0,errors.join('\n'));
    }finally{await p.close();}
});
if(authenticatedMode)test('forgetting a key fences a paused real authentication response',async()=>{
    const p=await page();try{
        await p.goto(base);
        let release;
        const paused=new Promise(resolve=>{release=resolve;});
        await p.route(`${base}/api/traces/stats`,route=>release(route));
        await p.locator('#connection-key').fill(deploymentKey);await p.locator('#connect-btn').click();
        const route=await paused;
        await p.locator('#disconnect-btn').click();
        await route.continue(); // Real backend, delayed transport; no fabricated response.
        await p.waitForFunction(()=>!document.getElementById('connect-btn').disabled);
        assert.equal(await p.locator('#connection-status').innerText(),'Deployment key forgotten.');
        assert.equal(await p.locator('#connection-key').inputValue(),'');
        const result=p.waitForResponse(r=>r.url()===`${base}/demo`);
        await p.locator('#run-pipeline-btn').click();assert.equal((await result).status(),401);
    }finally{await p.close();}
});

test('actual owned upload completes preview, source and repeated review CAS',async()=>{
    const p=await page();try{
        await p.goto(base);await connect(p);
        await p.locator('#document-upload').setInputFiles({name:'user-owned-memo.txt',mimeType:'text/plain',buffer:fs.readFileSync(path.join(repo,'fixtures/wedge/sample_memo_01.txt'))});
        const uploaded=p.waitForResponse(r=>r.url().includes('/api/documents?'));
        await p.locator('#upload-btn').click();assert.equal((await uploaded).status(),200);
        await p.waitForFunction(()=>document.getElementById('fixture-select').value.startsWith('uploaded:'));
        const processed=p.waitForResponse(r=>r.url()===`${base}/demo`);
        await p.locator('#run-pipeline-btn').click();assert.equal((await processed).status(),200);
        await p.locator('.card').first().waitFor();
        for(const value of ['First human review','Second human review']){
            await p.locator('.btn-edit').first().click();await p.locator('#modal-corrected').fill(value);
            const corrected=p.waitForResponse(r=>r.url()===`${base}/correct`);
            await p.locator('#modal-submit-btn').click();assert.equal((await corrected).status(),200);
            await p.waitForFunction(()=>!document.getElementById('edit-modal').classList.contains('open'));
            assert.equal(await p.locator('.card-value').first().innerText(),value);
        }
        await p.locator('.chip').first().click();
        await p.waitForFunction(()=>document.querySelector('.source-evidence').textContent.length>0);
        assert.equal(errors.length,0);
        if(authenticatedMode){await p.locator('#disconnect-btn').click();assert.equal(await p.locator('.card').count(),0);}
    }finally{await p.close();}
});
test('actual conflicting review reloads current revision before explicit retry',async()=>{
    const p=await page();try{
        const response=p.waitForResponse(r=>r.url()===`${base}/demo`);
        await processDocument(p);const data=await (await response).json();const item=data.suggestions[0];
        const headers={'Content-Type':'application/json',...(authenticatedMode?{Authorization:`Bearer ${deploymentKey}`}:{})};
        const external=await fetch(`${base}/correct`,{method:'POST',headers,body:JSON.stringify({ext_id:item.ext_id,field_name:item.field_name,original:item.value,corrected:'Concurrent review',reason:'second session fixture',expected_revision:0})});
        assert.equal(external.status,200);
        await p.locator('.btn-edit').first().click();await p.locator('#modal-corrected').fill('Explicit reviewed retry');
        const conflict=p.waitForResponse(r=>r.url()===`${base}/correct`);
        await p.locator('#modal-submit-btn').click();assert.equal((await conflict).status(),409);
        await p.getByText('Correction failed: Another review changed this field. Current value reloaded; review your edit and submit again.',{exact:true}).waitFor();
        assert.equal(await p.locator('.card-value').first().innerText(),'Concurrent review');
        const retry=p.waitForResponse(r=>r.url()===`${base}/correct`);
        await p.locator('#modal-submit-btn').click();assert.equal((await retry).status(),200);
        await p.waitForFunction(()=>!document.getElementById('edit-modal').classList.contains('open'));
        assert.equal(await p.locator('.card-value').first().innerText(),'Explicit reviewed retry');
    }finally{await p.close();}
});

test('owned upload and process controls stay reachable at mobile and desktop widths',async()=>{
    const p=await page();try{
        for(const width of [320,768,1280]){
            await p.setViewportSize({width,height:900});await p.goto(base);await connect(p);
            for(const id of ['document-upload','upload-btn','run-pipeline-btn']){
                const box=await p.locator('#'+id).boundingBox();
                assert.ok(box&&box.x>=0&&box.x+box.width<=width+1,`${id} clipped at ${width}`);
            }
            assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
            if(process.env.AXIOM_SCREENSHOT_DIR&&[320,1280].includes(width)){
                fs.mkdirSync(process.env.AXIOM_SCREENSHOT_DIR,{recursive:true});
                await p.screenshot({path:path.join(process.env.AXIOM_SCREENSHOT_DIR,`overlay-${authenticatedMode?'auth':'local'}-${width}.png`),fullPage:true});
            }
        }
    }finally{await p.close();}
});
