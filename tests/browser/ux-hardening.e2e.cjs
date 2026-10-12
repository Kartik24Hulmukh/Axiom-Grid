/* Real loopback server/browser E2E; one explicitly labelled response-fuzz test. */
const {test,before,after}=require('node:test');
const assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs'); const os=require('node:os');const path=require('node:path');const net=require('node:net');
const {chromium}=require('playwright');
const authenticatedMode=true;
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
async function page(){
    const p=await browser.newPage();p.on('pageerror',e=>errors.push(e.message));
    if(process.env.AXIOM_UX_BASELINE_ASSETS==='1') {
        // Reconstructed static assets from the frozen SHA; backend remains real.
        // Screenshots are captured after remediation, NOT before-edit captures.
        for(const [url,file,type] of [[`${base}/`,'index.html','text/html'],[`${base}/assets/overlay.js`,'overlay.js','application/javascript']]) {
            const body=execFileSync('git',['show',`4f3a822:overlay/templates/${file}`],{cwd:repo});
            await p.route(url,r=>r.fulfill({status:200,contentType:type,body}));
        }
    }
    return p;
}
async function screenshot(p,name) {
    if(!process.env.AXIOM_UX_EVIDENCE_DIR)return;
    fs.mkdirSync(process.env.AXIOM_UX_EVIDENCE_DIR,{recursive:true});
    await p.screenshot({path:path.join(process.env.AXIOM_UX_EVIDENCE_DIR,`${name}.png`),fullPage:!name.startsWith('modal-'),animations:'disabled'});
}

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
// Actual backend responses are paused at the transport boundary, never invented.
async function hold(p, endpoint) {
    let unlock, parked;
    const release=new Promise(r=>unlock=r), ready=new Promise(r=>parked=r);
    await p.route(`${base}${endpoint}`,async route=>{
        const response=await route.fetch(); parked(response);
        await release; await route.fulfill({response});
    });
    return {ready, release:()=>unlock()};
}
async function settled(p, id) { await p.waitForFunction(id=>!document.getElementById(id).disabled,id); }
test('UX01 forget during actual processing cannot overwrite cleared document',async()=>{
    const p=await page();try{
        await p.goto(base);await connect(p);const pending=await hold(p,'/demo');
        await p.locator('#run-pipeline-btn').click();assert.equal((await pending.ready).status(),200);
        await p.locator('#disconnect-btn').click();pending.release();await settled(p,'run-pipeline-btn');
        // Give the real delayed response handler a browser event-loop turn.
        await p.waitForTimeout(150);
        assert.equal(await p.locator('#doc-content').innerText(),'Select a document and run the pipeline.');
        assert.equal(await p.locator('.card').count(),0);
    }finally{await p.close();}
});
test('UX02 forget during actual upload leaves no owned option or stale status',async()=>{
    const p=await page();try{
        await p.goto(base);await connect(p);await p.locator('#document-upload').setInputFiles({name:'abandoned.txt',mimeType:'text/plain',buffer:Buffer.from('SECRET MEMO: test owned document')});
        const pending=await hold(p,'/api/documents?filename=abandoned.txt');
        await p.locator('#upload-btn').click();assert.equal((await pending.ready).status(),200);
        await p.locator('#disconnect-btn').click();pending.release();await settled(p,'upload-btn');await p.waitForTimeout(150);
        assert.equal(await p.locator('option[data-owned]').count(),0);
        assert.ok(!(await p.locator('#upload-status').innerText()).includes('failed'));
    }finally{await p.close();}
});
test('UX03 hidden correction controls cannot receive keyboard focus',async()=>{
    const p=await page();try{await p.goto(base);
        await p.locator('#modal-corrected').evaluate(e=>e.focus());
        assert.notEqual(await p.evaluate(()=>document.activeElement.id),'modal-corrected');
    }finally{await p.close();}
});
test('UX04 keyboard tabs expose selected state and arrow navigation',async()=>{
    const p=await page();try{await processDocument(p);
        assert.equal(await p.locator('#tab-suggestions').getAttribute('role'),'tab');
        await p.locator('#tab-suggestions').focus();await p.keyboard.press('ArrowRight');
        assert.equal(await p.locator('#tab-trace').getAttribute('aria-selected'),'true');
        assert.equal(await p.evaluate(()=>document.activeElement.id),'tab-trace');
    }finally{await p.close();}
});
test('UX05 correction traps keyboard, Escape returns focus, labels resolve',async()=>{
    const p=await page();try{await processDocument(p);await p.locator('.btn-edit').first().click();
        assert.equal(await p.locator('#edit-modal').getAttribute('role'),'dialog');
        assert.equal(await p.getByLabel('Corrected Value',{exact:true}).count(),1);
        await p.locator('#modal-submit-btn').focus();await p.keyboard.press('Tab');
        assert.equal(await p.evaluate(()=>document.activeElement.id),'modal-field');
        await p.keyboard.press('Escape');assert.equal(await p.locator('.btn-edit').first().evaluate(e=>e===document.activeElement),true);
    }finally{await p.close();}
});
test('UX06 conflict retains draft and updates displayed original before explicit retry',async()=>{
    const p=await page();try{
        const result=p.waitForResponse(r=>r.url()===`${base}/demo`);await processDocument(p);const item=(await (await result).json()).suggestions[0];
        const current=await fetch(`${base}/correct`,{method:'POST',headers:{'Content-Type':'application/json',Authorization:`Bearer ${deploymentKey}`},body:JSON.stringify({ext_id:item.ext_id,field_name:item.field_name,original:item.value,corrected:'Other reviewer value',reason:'UX conflict',expected_revision:0})});assert.equal(current.status,200);
        await p.locator('.btn-edit').first().click();await p.locator('#modal-corrected').fill('My retained draft');await p.locator('#modal-submit-btn').click();
        await p.getByText('Correction failed: Another review changed this field. Current value reloaded; review your edit and submit again.',{exact:true}).waitFor();
        assert.equal(await p.locator('#modal-original').inputValue(),'Other reviewer value');
        assert.equal(await p.locator('#modal-corrected').inputValue(),'My retained draft');
        await p.locator('#modal-cancel-btn').click();await p.locator('.btn-edit').first().click();assert.equal(await p.locator('#modal-error').innerText(),'');
    }finally{await p.close();}
});
test('UX07 delayed save from closed editor cannot close a newer editor',async()=>{
    const p=await page();try{await processDocument(p);const pending=await hold(p,'/correct');
        await p.locator('.btn-edit').first().click();await p.locator('#modal-submit-btn').click();assert.equal((await pending.ready).status(),200);
        await p.keyboard.press('Escape');await p.locator('.btn-edit').nth(1).click();await p.locator('#modal-corrected').fill('New editor draft');
        pending.release();await settled(p,'modal-submit-btn');await p.waitForTimeout(150);
        assert.equal(await p.locator('#edit-modal').evaluate(e=>e.classList.contains('open')),true);
        assert.equal(await p.locator('#modal-corrected').inputValue(),'New editor draft');
    }finally{await p.close();}
});
test('UX08 modal fits 320px viewport with keyboard-height constraint',async()=>{
    const p=await page();try{await p.setViewportSize({width:320,height:480});await processDocument(p);await p.locator('.btn-edit').first().click();
        await screenshot(p,'modal-320x480');
        const box=await p.locator('.modal-content').boundingBox();assert.ok(box.x>=0&&box.x+box.width<=321&&box.y>=0&&box.y+box.height<=481,JSON.stringify(box));
        await p.locator('#modal-submit-btn').click({trial:true});
        await screenshot(p,'modal-actions-320x480');
    }finally{await p.close();}
});
test('UX09 document controls lock together; duplicate owned upload sends one request',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        await p.locator('#document-upload').setInputFiles({name:'double.txt',mimeType:'text/plain',buffer:Buffer.from('Memo text')});
        const pending=await hold(p,'/api/documents?filename=double.txt');let calls=0;p.on('request',r=>{if(r.url().includes('/api/documents?'))calls++;});
        await p.evaluate(()=>{for(let i=0;i<100;i++)document.getElementById('upload-btn').click();});await pending.ready;
        for(const id of ['fixture-select','document-upload','upload-btn','run-pipeline-btn'])assert.equal(await p.locator('#'+id).isDisabled(),true);
        pending.release();await settled(p,'upload-btn');assert.equal(calls,1);assert.equal(await p.locator('option[data-owned]').count(),1);
    }finally{await p.close();}
});
test('UX10 old pipeline completion cannot unlock or replace newer same-key session',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        const unlock=[],ready=[],done=[];
        const gates=[0,1].map(i=>({release:new Promise(r=>unlock[i]=r),ready:new Promise(r=>ready[i]=r),done:new Promise(r=>done[i]=r)}));let calls=0;
        await p.route(`${base}/demo`,async route=>{const i=calls++;const response=await route.fetch();ready[i](response);await gates[i].release;await route.fulfill({response});done[i]();});
        await p.locator('#run-pipeline-btn').click();await gates[0].ready;await p.locator('#disconnect-btn').click();await connect(p);
        await p.locator('#run-pipeline-btn').click();await gates[1].ready;
        unlock[0]();await gates[0].done;await p.waitForTimeout(150);assert.equal(await p.locator('#run-pipeline-btn').isDisabled(),true);assert.equal(await p.locator('#doc-content').innerText(),'Processing document…');
        unlock[1]();await gates[1].done;await p.locator('.card').first().waitFor();await settled(p,'run-pipeline-btn');
    }finally{await p.close();}
});
test('UX11 forget during actual source lookup removes evidence and late failure',async()=>{
    const p=await page();try{await processDocument(p);const result=p.waitForResponse(r=>r.url().startsWith(`${base}/source/`));
        let release,ready;const barrier=new Promise(r=>release=r),parked=new Promise(r=>ready=r);
        await p.route(`${base}/source/*`,async route=>{const response=await route.fetch();ready(response);await barrier;await route.fulfill({response});});
        await p.locator('.chip').first().click();assert.equal((await parked).status(),200);
        await p.locator('#disconnect-btn').click();release();await result;await p.waitForTimeout(150);
        assert.equal(await p.locator('.source-evidence').count(),0);assert.equal(await p.locator('.request-error').count(),1);assert.equal(await p.locator('#modal-error').innerText(),'');
    }finally{await p.close();}
});
test('UX12 escape then forget during actual save wipes review draft and ignores completion',async()=>{
    const p=await page();try{await processDocument(p);const pending=await hold(p,'/correct');
        await p.locator('.btn-edit').first().click();await p.locator('#modal-corrected').fill('Forget this draft');await p.locator('#modal-submit-btn').click();await pending.ready;
        await p.keyboard.press('Escape');await p.locator('#disconnect-btn').click();pending.release();await p.waitForTimeout(150);
        for(const id of ['modal-original','modal-corrected','modal-reason'])assert.equal(await p.locator('#'+id).inputValue(),'');
        assert.equal(await p.locator('.card').count(),0);assert.equal(await p.locator('#modal-error').innerText(),'');
    }finally{await p.close();}
});
test('UX13 actual short owned note has no grounded suggestions (not a universal no-heading rule)',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        await p.locator('#document-upload').setInputFiles({name:'no-fields.txt',mimeType:'text/plain',buffer:Buffer.from('brief note.')});
        await p.locator('#upload-btn').click();await settled(p,'upload-btn');const result=p.waitForResponse(r=>r.url()===`${base}/demo`);await p.locator('#run-pipeline-btn').click();
        const response=await result;assert.equal(response.status(),200);const data=await response.json();assert.equal(data.suggestions.length,0);
        await p.getByText('No grounded suggestions.',{exact:true}).waitFor();assert.equal(await p.locator('.btn-accept').count(),0);
    }finally{await p.close();}
});
test('UX14 isolated empty/refused response oracle states text, trace and halt honestly',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        // Fabricated rendering oracle: not real blocked extraction or human evidence.
        await p.route(`${base}/demo`,r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({success:true,document_text:'',suggestions:[],trace:{halted:true,halt_reason:'Refused fixture oracle',stages:[]}})}));
        await p.locator('#run-pipeline-btn').click();await p.getByText('No document text available.',{exact:true}).waitFor();
        await p.getByText('No grounded suggestions.',{exact:true}).waitFor();await p.locator('#tab-trace').click();
        await p.getByText('Pipeline halted: Refused fixture oracle',{exact:true}).waitFor();await p.getByText('No pipeline trace stages available.',{exact:true}).waitFor();assert.equal(await p.locator('.btn-accept').count(),0);
    }finally{await p.close();}
});
test('UX15 actual missing source response is recoverable and not fictional evidence',async()=>{
    const p=await page();try{await processDocument(p);
        // Reroute to a real unknown-ID backend lookup, not a fabricated response.
        await p.route(`${base}/source/*`,async route=>route.fulfill({response:await route.fetch({url:`${base}/source/ux-unknown-observation`})}));
        await p.locator('.chip').first().click();await p.getByText(/Source unavailable:/).waitFor();assert.equal(await p.locator('.chip').first().isEnabled(),true);
    }finally{await p.close();}
});
test('UX16 missing and oversize upload make no requests; filename markup stays literal',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);let calls=0;p.on('request',r=>{if(r.url().includes('/api/documents?'))calls++;});
        await p.locator('#upload-btn').click();await p.getByText('Select a document first.',{exact:true}).waitFor();
        await p.locator('#document-upload').setInputFiles({name:'too-large.txt',mimeType:'text/plain',buffer:Buffer.alloc(2*1024*1024+1)});await p.locator('#upload-btn').click();await p.getByText('Document exceeds 2 MiB.',{exact:true}).waitFor();assert.equal(calls,0);
        const filename='<b>私の note</b>.txt';await p.locator('#document-upload').setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from('Short note')});await p.locator('#upload-btn').click();await settled(p,'upload-btn');
        assert.equal(calls,1);assert.equal(await p.locator('option[data-owned]').innerText(),filename);assert.equal(await p.locator('option b').count(),0);
    }finally{await p.close();}
});
test('UX17 isolated proxy HTML error oracle preserves HTTP status and restores controls',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        await p.route(`${base}/demo`,r=>r.fulfill({status:503,contentType:'text/html',body:'<h1>Service unavailable</h1>'}));
        await p.locator('#run-pipeline-btn').click();await p.getByText('Unable to process document: HTTP 503: server returned an unreadable response.',{exact:true}).waitFor();assert.equal(await p.locator('#run-pipeline-btn').isEnabled(),true);assert.equal(await p.locator('.card').count(),0);
    }finally{await p.close();}
});
test('UX18 timeout clock oracle explains uncertain server outcome without auto retry',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);await p.clock.install();
        let parked;const ready=new Promise(r=>parked=r);
        await p.route(`${base}/demo`,async route=>{parked(); /* transport intentionally never completes */});
        await p.locator('#run-pipeline-btn').click();await ready;await p.clock.fastForward(30001);
        await p.getByText('Unable to process document: Request timed out; the server outcome may be unknown. Check before retrying.',{exact:true}).waitFor();assert.equal(await p.locator('#run-pipeline-btn').isEnabled(),true);
    }finally{await p.close();}
});

test('UX19 pinned axe-core audits actual initial, processed and correction views',async()=>{
    const axe=require('./ux-a11y/node_modules/axe-core');const p=await page();const failures=[];
    try{
        await p.setViewportSize({width:320,height:900});await p.goto(base);await connect(p);
        for(const state of ['initial','processed','correction']){
            if(state==='processed'){await p.locator('#run-pipeline-btn').click();await p.locator('.card').first().waitFor();}
            if(state==='correction')await p.locator('.btn-edit').first().click();
            await p.evaluate(axe.source);
            const result=await p.evaluate(async()=>axe.run());
            if(process.env.AXIOM_UX_EVIDENCE_DIR){fs.mkdirSync(process.env.AXIOM_UX_EVIDENCE_DIR,{recursive:true});fs.writeFileSync(path.join(process.env.AXIOM_UX_EVIDENCE_DIR,`axe-${state}.json`),JSON.stringify(result,null,2));}
            await screenshot(p,`${state}-320x900`);
            failures.push(...result.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>({state,id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)})));
        }
        assert.deepEqual(failures,[],'serious/critical accessibility violations');
        assert.equal(errors.length,0,errors.join('\n'));
    }finally{await p.close();}
});

// Additional v5 usability contracts: real pages, plus one explicit CSS-only
// motion-preference oracle. They are not manual assistive-technology evidence.
test('UX20 actual page has one H1 and a named connection landmark',async()=>{
    const p=await page();try{await p.goto(base);await connect(p);
        assert.equal(await p.locator('h1').count(),1,'document needs a top-level heading');
        assert.equal(await p.getByRole('form',{name:'Deployment connection'}).count(),1);
        const axe=require('./ux-a11y/node_modules/axe-core');await p.evaluate(axe.source);
        const result=await p.evaluate(async()=>axe.run(document,{runOnly:{type:'rule',values:['page-has-heading-one','region']}}));
        assert.deepEqual(result.violations.map(v=>v.id),[]);
    }finally{await p.close();}
});
function relativeLuminance(rgb){
    const values=rgb.slice(0,3).map(x=>{const c=x/255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4;});
    return .2126*values[0]+.7152*values[1]+.0722*values[2];
}
function contrastRatio(a,b){const x=relativeLuminance(a),y=relativeLuminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
async function opaqueButtonContrast(p,selector){
    const style=await p.locator(selector).first().evaluate(e=>{const s=getComputedStyle(e);return {color:s.color,background:s.backgroundColor,image:s.backgroundImage};});
    const parse=s=>s.match(/[\d.]+/g).map(Number);
    const fg=parse(style.color);assert.ok(fg.length===3||fg[3]===1,'transparent text needs a separate compositing audit');
    // Test every fully opaque gradient stop when present; translucent stops are
    // intentionally not counted as certified. One failing opaque stop is enough
    // to demonstrate a baseline contrast defect without guessing its backdrop.
    const stops=style.image==='none'?[parse(style.background)]:[...style.image.matchAll(/rgba?\([^)]*\)/g)].map(x=>parse(x[0]));
    const opaque=stops.filter(x=>x.length===3||x[3]===1);
    assert.ok(opaque.length,'solid/opaque stop needed for this contrast proof');
    for(const bg of opaque)assert.ok(contrastRatio(fg,bg)>=4.5,JSON.stringify({selector,style,ratio:contrastRatio(fg,bg)}));
}
test('UX21 actual primary and hovered action text meet 4.5 opaque-color contrast',async()=>{
    const p=await page();try{await processDocument(p);
        await opaqueButtonContrast(p,'#run-pipeline-btn');
        for(const selector of ['.btn-accept','.btn-edit','.btn-reject']){
            await p.locator(selector).first().hover();
            // Wait for the actual CSS transition boundary, not a workload delay.
            await p.locator(selector).first().evaluate(e=>Promise.all(e.getAnimations().map(a=>a.finished.catch(()=>{}))));
            await opaqueButtonContrast(p,selector);
        }
    }finally{await p.close();}
});
test('UX22 actual correction keeps multiline text readable and roundtrips newlines',async()=>{
    const p=await page();try{await p.setViewportSize({width:320,height:480});await processDocument(p);await p.locator('.btn-edit').first().click();
        for(const id of ['modal-original','modal-corrected'])assert.equal(await p.locator('#'+id).evaluate(e=>e.tagName),'TEXTAREA');
        const value='First retained line\nSecond retained line\n第三行 — source review';
        await p.locator('#modal-corrected').fill(value);await p.locator('#modal-reason').fill('Multiline UX workflow');
        const response=p.waitForResponse(r=>r.url()===`${base}/correct`);await p.locator('#modal-submit-btn').click();assert.equal((await response).status(),200);
        await p.locator('#edit-modal').waitFor({state:'hidden'});await p.locator('.btn-edit').first().click();
        assert.equal(await p.locator('#modal-original').inputValue(),value);
        await p.locator('#modal-submit-btn').click({trial:true});
    }finally{await p.close();}
});
test('UX23 CSS-only reduced-motion oracle disables highlight pulse and transitions',async()=>{
    const p=await page();try{await p.emulateMedia({reducedMotion:'reduce'});await p.goto(base);
        // Explicit styling oracle, not a fabricated source or pipeline result.
        const motion=await p.evaluate(()=>{const e=document.createElement('div');e.className='highlight-bbox';e.setAttribute('aria-hidden','true');document.body.append(e);const s=getComputedStyle(e);const result={animation:s.animationName,transition:s.transitionDuration};e.remove();return result;});
        assert.equal(motion.animation,'none');assert.equal(motion.transition,'0s');
    }finally{await p.close();}
});
