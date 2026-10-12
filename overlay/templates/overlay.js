/* Axiom-Grid local engineering preview. All untrusted data uses text nodes. */
(() => {
'use strict';
const byId = id => document.getElementById(id);
const run = byId('run-pipeline-btn');
const doc = byId('doc-content');
const suggestions = byId('suggestions-container');
const trace = byId('trace-container');
const select = byId('fixture-select');
let active = null;
let apiKey = '';
let connectionEpoch = 0;
let viewEpoch = 0;
const busy = new Map();
const uploadNotice = 'API access expires after one hour. Local cleanup is deferred; not encrypted at rest.';
function current(epoch, view = viewEpoch) { return epoch === connectionEpoch && view === viewEpoch; }
function documentBusy(value) {
    for (const control of [run, select, byId('upload-btn'), byId('document-upload')]) control.disabled = value;
    doc.setAttribute('aria-busy', String(value));
}
function lock(id) { const token = Symbol(id); busy.set(id, token); return token; }
function unlock(id, token) { if (busy.get(id) === token) busy.delete(id); }

function node(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = String(text ?? '');
    return el;
}
async function api(path, body, binary = false) {
    const epoch = connectionEpoch;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 30000);
    try {
        const headers = body === undefined ? {} : {'Content-Type': binary ? 'application/octet-stream' : 'application/json'};
        if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
        const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST',
            headers,
            body: body === undefined ? undefined : binary ? body : JSON.stringify(body), signal: controller.signal});
        let data;
        try { data = await response.json(); }
        catch { throw new Error(`HTTP ${response.status}: server returned an unreadable response.`); }
        if (epoch !== connectionEpoch) throw new Error("Connection changed; result discarded");
        if (!response.ok || data.success === false) {
            const error = new Error(data.detail || data.error || `HTTP ${response.status}`);
            error.status = response.status; throw error;
        }
        return data;
    } catch (error) {
        if (error.name === 'AbortError') throw new Error('Request timed out; the server outcome may be unknown. Check before retrying.');
        if (error instanceof TypeError) throw new Error('Network unavailable; the server outcome may be unknown. Check before retrying.');
        throw error;
    } finally { clearTimeout(timer); }
}
byId('connection-form').addEventListener('submit', async event => {
    event.preventDefault();
    const button = byId('connect-btn');
    if (button.disabled) return;
    const key = byId('connection-key');
    const candidate = key.value.trim();
    key.value = '';
    if (location.protocol !== 'https:' && !['localhost','127.0.0.1','[::1]'].includes(location.hostname)) {
        byId('connection-status').textContent = 'HTTPS is required before sending a deployment key.';
        return;
    }
    button.disabled = true;
    const epoch = ++connectionEpoch;
    clearOwnedSession();
    button.disabled = true;
    apiKey = candidate;
    try {
        await api('/api/traces/stats');
        if (epoch === connectionEpoch) {
            byId('connection-status').textContent = candidate ? 'Connected with deployment authentication.' : 'Connected without a deployment key.';
        }
    } catch (error) {
        if (epoch === connectionEpoch) {
            apiKey = '';
            byId('connection-status').textContent = `Connection rejected: ${error.message}`;
        }
    } finally { if (epoch === connectionEpoch) button.disabled = false; }
});
byId('disconnect-btn').addEventListener('click', () => {
    ++connectionEpoch;
    apiKey = '';
    byId('connection-key').value = '';
    clearOwnedSession();
    byId('connection-status').textContent = 'Deployment key forgotten.';
});
function clearOwnedSession() {
    ++viewEpoch;
    closeModal(); busy.clear();
    documentBusy(false); run.textContent = 'Process Document';
    byId('connect-btn').disabled = false;
    byId('upload-status').textContent = uploadNotice;
    byId('sidecar-status').textContent = 'Authentication not checked';
    tabs('suggestions');
    suggestions.replaceChildren(); trace.replaceChildren();
    doc.textContent = 'Select a document and run the pipeline.';
    select.querySelectorAll('option[data-owned]').forEach(option => option.remove());
    byId('document-upload').value = '';
}
byId('upload-btn').addEventListener('click', async () => {
    const button = byId('upload-btn');
    if (button.disabled) return;
    const file = byId('document-upload').files[0];
    if (!file) { byId('upload-status').textContent = 'Select a document first.'; return; }
    if (file.size > 2 * 1024 * 1024) { byId('upload-status').textContent = 'Document exceeds 2 MiB.'; return; }
    const epoch = connectionEpoch;
    documentBusy(true);
    byId('upload-status').textContent = 'Uploading owned copy…';
    try {
        const result = await api(`/api/documents?filename=${encodeURIComponent(file.name)}`, file, true);
        if (!current(epoch)) return;
        const option = node('option', '', file.name);
        option.value = result.file; option.dataset.owned = 'true';
        select.append(option); select.value = option.value;
        byId('upload-status').textContent = 'Owned copy uploaded. Click Process Document. API access expires after one hour; local cleanup is deferred. Not encrypted at rest.';
    } catch (error) { if (current(epoch)) byId('upload-status').textContent = `Upload failed: ${error.message}`; }
    finally { if (current(epoch)) documentBusy(false); }
});
function status(container, text, className = '') {
    container.replaceChildren(node('div', className, text));
}
function tabs(which) {
    for (const name of ['suggestions', 'trace']) {
        const tab = byId(name === 'suggestions' ? 'tab-suggestions' : 'tab-trace');
        const panel = byId(`panel-${name}`);
        tab.classList.toggle('active', name === which);
        tab.setAttribute('aria-selected', String(name === which));
        tab.tabIndex = name === which ? 0 : -1;
        panel.hidden = name !== which;
        panel.style.display = name === which ? 'block' : 'none';
    }
}
byId('tab-suggestions').addEventListener('click', () => tabs('suggestions'));
byId('tab-trace').addEventListener('click', () => tabs('trace'));
for (const name of ['suggestions', 'trace']) {
    byId(`tab-${name}`).addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const which = event.key === 'Home' ? 'suggestions' : event.key === 'End' ? 'trace' : name === 'trace' ? 'suggestions' : 'trace';
        tabs(which); byId(`tab-${which}`).focus();
    });
}
async function mutate(item, container, operation, button) {
    if (busy.has(item.ext_id)) return;
    const token = lock(item.ext_id);
    const epoch = connectionEpoch, view = viewEpoch;
    const buttons = [...container.querySelectorAll('button')];
    buttons.forEach(b => { b.disabled = true; });
    try {
        if (operation === 'accept') {
            await api('/apply', {ext_id: item.ext_id, accept: true});
            if (!current(epoch, view)) return;
            status(container, 'Applied; inspect the returned verification evidence.', 'action-status applied');
        } else {
            const review = await api('/correct', {ext_id: item.ext_id, field_name: item.field_name,
                original: item.value, corrected: '', reason: 'User rejected suggestion', expected_revision:item.revision || 0});
            if (!current(epoch, view)) return;
            item.revision = review.revision; item.value = '';
            status(container, 'Rejected; correction recorded.', 'action-status rejected');
        }
    } catch (err) {
        if (!current(epoch, view)) return;
        let message = container.querySelector('.request-error');
        if (!message) { message = node('div', 'request-error'); container.append(message); }
        message.textContent = `Failed: ${err.message}`;
        buttons.forEach(b => { b.disabled = false; });
        if (button) button.focus();
    } finally { unlock(item.ext_id, token); }
}
function renderSuggestions(items) {
    suggestions.replaceChildren();
    if (!Array.isArray(items) || !items.length) { status(suggestions, 'No grounded suggestions.'); return; }
    for (const item of items) {
        const card = node('div', 'card'); card.id = `card-${item.ext_id}`;
        const head = node('div', 'card-header');
        head.append(node('div', 'field-name', item.field_name));
        const confidence = Number(item.confidence);
        head.append(node('div', 'confidence-badge', Number.isFinite(confidence) ? `${Math.round(confidence * 100)}% confidence` : 'No confidence'));
        card.append(head, node('div', 'card-value', item.value));
        const source = node('button', 'chip', `Source page ${item.page ?? '?'} — ${String(item.chunk_id ?? '').slice(0, 8)}`);
        source.type = 'button';
        source.addEventListener('click', async () => {
            source.disabled = true;
            const epoch = connectionEpoch, view = viewEpoch;
            try {
                const data = await api(`/source/${encodeURIComponent(item.ext_id)}`);
                // Text-view preview cannot honestly map PDF coordinates. Show
                // the actual source evidence instead of inventing an overlay.
                if (current(epoch, view)) status(card.querySelector('.source-evidence'), JSON.stringify(data, null, 2));
            } catch (err) { if (current(epoch, view)) status(card.querySelector('.source-evidence'), `Source unavailable: ${err.message}`); }
            finally { source.disabled = false; }
        });
        card.append(source, node('pre', 'source-evidence'));
        const actions = node('div', 'card-actions'); actions.id = `actions-${item.ext_id}`;
        for (const [operation, label] of [['accept','Accept'], ['edit','Edit'], ['reject','Reject']]) {
            const button = node('button', `btn-card btn-${operation}`, label); button.type = 'button';
            button.addEventListener('click', () => {
                if (busy.has(item.ext_id)) return;
                if (operation !== 'edit') { void mutate(item, actions, operation, button); return; }
                active = {item, actions, card, trigger: button};
                byId('modal-error').textContent = '';
                byId('modal-submit-btn').disabled = busy.has(item.ext_id);
                byId('modal-field').value = item.field_name;
                byId('modal-original').value = item.value;
                byId('modal-corrected').value = item.value;
                byId('modal-reason').value = '';
                byId('edit-modal').hidden = false;
                byId('edit-modal').classList.add('open');
                for (const el of document.querySelectorAll('body > header, body > form, body > main')) el.inert = true;
                byId('modal-corrected').focus();
            }); actions.append(button);
        }
        card.append(actions); suggestions.append(card);
    }
}
function renderTrace(data) {
    trace.replaceChildren();
    if (data?.halted) trace.append(node('div', 'request-error', `Pipeline halted: ${data.halt_reason || 'No reason supplied.'}`));
    if (!data?.stages?.length) trace.append(node('div', '', 'No pipeline trace stages available.'));
    for (const stage of data?.stages ?? []) {
        const entry = node('div', `trace-node ${stage.status === 'halted' ? 'halted' : 'ok'}`);
        entry.append(node('div','trace-title',stage.name), node('div','trace-meta',`${stage.duration_ms ?? 0} ms | ${stage.status}`),
            node('pre','trace-data',JSON.stringify({input:stage.input_data,output:stage.output_data},null,2)));
        trace.append(entry);
    }
}
run.addEventListener('click', async () => {
    if (run.disabled) return;
    const epoch = connectionEpoch, view = ++viewEpoch;
    closeModal(); busy.clear(); documentBusy(true); run.textContent = 'Processing…';
    status(doc, 'Processing document…'); suggestions.replaceChildren(); trace.replaceChildren();
    try {
        const data = await api('/demo', {file: select.value});
        if (!current(epoch, view)) return;
        const text = node('pre', '', data.document_text || 'No document text available.'); text.style.whiteSpace = 'pre-wrap';
        doc.replaceChildren(text); renderSuggestions(data.suggestions); renderTrace(data.trace);
        byId('sidecar-status').textContent = 'Connected — engineering preview';
    } catch (err) { if (current(epoch, view)) status(doc, `Unable to process document: ${err.message}`); }
    finally { if (current(epoch, view)) { documentBusy(false); run.textContent = 'Process Document'; } }
});
function closeModal() {
    const trigger = active?.trigger;
    byId('edit-modal').classList.remove('open'); byId('edit-modal').hidden = true; active = null;
    for (const el of document.querySelectorAll('body > header, body > form, body > main')) el.inert = false;
    for (const id of ['modal-field', 'modal-original', 'modal-corrected', 'modal-reason']) byId(id).value = '';
    byId('modal-error').textContent = ''; byId('modal-submit-btn').disabled = false;
    if (trigger?.isConnected) trigger.focus();
}
byId('modal-cancel-btn').addEventListener('click', closeModal);
document.addEventListener('keydown', event => {
    if (!active) return;
    if (event.key === 'Escape') { event.preventDefault(); closeModal(); return; }
    if (event.key !== 'Tab') return;
    const controls = [...byId('edit-modal').querySelectorAll('input, textarea, button')].filter(el => !el.disabled);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});
byId('modal-submit-btn').addEventListener('click', async () => {
    if (!active || busy.has(active.item.ext_id)) return;
    const editor = active;
    const {item, actions, card} = editor;
    const epoch = connectionEpoch, view = viewEpoch;
    const corrected = byId('modal-corrected').value; const reason = byId('modal-reason').value;
    const token = lock(item.ext_id); byId('modal-submit-btn').disabled = true;
    byId('modal-error').textContent = '';
    try {
        const review = await api('/correct', {ext_id:item.ext_id,field_name:item.field_name,original:item.value,corrected,reason,expected_revision:item.revision || 0});
        if (!current(epoch, view)) return;
        item.revision = review.revision; item.value = corrected;
        card.querySelector('.card-value').textContent = corrected;
        let annotation = card.querySelector('.review-status');
        if (!annotation) { annotation = node('div', 'review-status'); card.append(annotation); }
        annotation.textContent = 'Human correction recorded; not re-grounded.';
        card.querySelector('.confidence-badge').textContent = 'Original-source confidence (not review confidence)';
        if (active === editor) closeModal();
    } catch (err) {
        if (!current(epoch, view)) return;
        const currentSession = () => current(epoch, view);
        if (err.status === 409) {
            try {
                const current = await api(`/api/reviews/${encodeURIComponent(item.ext_id)}`);
                if (!currentSession()) return;
                item.revision = current.revision; item.value = current.value;
                if (active === editor) byId('modal-original').value = current.value;
                card.querySelector('.card-value').textContent = current.value;
                err.message = 'Another review changed this field. Current value reloaded; review your edit and submit again.';
            } catch (reload) { err.message = `Review reload failed: ${reload.message}`; }
        }
        if (currentSession() && active === editor) byId('modal-error').textContent = `Correction failed: ${err.message}`;
    } finally { unlock(item.ext_id, token); if (active === editor) byId('modal-submit-btn').disabled = false; }
});
const healthEpoch = connectionEpoch;
api('/healthz').then(() => { if (current(healthEpoch)) byId('sidecar-status').textContent = 'Service reachable — authentication checked separately'; })
    .catch(() => { if (current(healthEpoch)) byId('sidecar-status').textContent = 'Service unavailable'; });
const file = new URLSearchParams(location.search).get('file');
if (file) { const option = node('option','',file); option.value = file; select.append(option); select.value = file; run.click(); }
})();
