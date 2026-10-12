"""Actual ASGI ownership and review checks, not response interception."""
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from overlay import server
from kernel.sidecar.evidence_store import EvidenceStore
from overlay.document_store import DocumentStore


@pytest.fixture
def authenticated(monkeypatch,tmp_path):
    a='axiom-tenant-alpha-fixture';b='axiom-tenant-bravo-fixture'
    monkeypatch.setattr(server,'_API_KEY_DIGESTS',{hashlib.sha256(k.encode()).hexdigest():hashlib.sha256(k.encode()).hexdigest() for k in (a,b)})
    monkeypatch.setattr(server,'_AUTH_REQUIRED',True)
    monkeypatch.setattr(server,'evidence_store',EvidenceStore(tmp_path/'scoped.db'))
    monkeypatch.setattr(server,'document_store',DocumentStore(tmp_path/'uploads'))
    server._rate_limit_buckets.clear()
    with TestClient(server.app) as client:
        yield client, {'Authorization':'Bearer '+a}, {'Authorization':'Bearer '+b}


def test_upload_extract_source_ownership_filesystem_and_review_cas(authenticated,tmp_path):
    c,a,b=authenticated
    secret=tmp_path/'not-owned.txt';secret.write_text('SUBJECT: private\nAUTHOR: Alice\n')
    assert c.post('/api/extract-document',headers=a,json={'file':str(secret)}).status_code==404
    original=Path(server.FIXTURES_DIR/'sample_memo_01.txt').read_bytes()
    up=c.post('/api/documents?filename=../../memo.txt',headers=a,content=original)
    assert up.status_code==200,up.text
    ref=up.json()['file'];assert ref.startswith('uploaded:')
    assert c.post('/demo',headers=b,json={'file':ref}).status_code==404
    response=c.post('/demo',headers=a,json={'file':ref});assert response.status_code==200,response.text
    data=response.json();ext=data['suggestions'][0]
    source='/api/source/'+data['doc_id']
    text=c.get(source,headers=a).json()['source_text']
    assert text and c.get(source,headers=b).status_code==404
    assert c.get('/source/'+ext['ext_id'],headers=a).status_code==200
    assert c.get('/source/'+ext['ext_id'],headers=b).status_code==404
    assert c.get('/api/traces',headers=b).json()==[]
    assert len(c.get('/api/traces',headers=a).json())==1
    body={'ext_id':ext['ext_id'],'field_name':ext['field_name'],'original':ext['value'],
          'corrected':'review value','reason':'fixture','expected_revision':0}
    assert c.post('/correct',headers=b,json=body).status_code==404
    assert c.post('/correct',headers=a,json={**body,'field_name':'wrong'}).status_code==409
    assert c.post('/correct',headers=a,json=body).json()['revision']==1
    assert c.post('/correct',headers=a,json=body).status_code==409
    review=c.get('/api/reviews/'+ext['ext_id'],headers=a).json()
    assert review['revision']==1 and review['value']=='review value' and review['source_value']==ext['value']
    assert c.get('/api/reviews/'+ext['ext_id'],headers=b).status_code==404
    assert c.get(source,headers=a).json()['source_text']==text
    unknown={**body,'ext_id':'never-existed'}
    assert c.post('/correct',headers=a,json=unknown).status_code==404
    for route in ['/api/graph','/api/eval/report','/api/compression/stats']:
        assert c.get(route,headers=a).status_code==501
    assert c.get('/static/page_images/unknown.png',headers=a).status_code==404
    assert c.post('/apply',headers=a,json={'ext_id':ext['ext_id'],'accept':True}).json()['post_state']['status']=='not_executed'
    assert secret.read_text()=='SUBJECT: private\nAUTHOR: Alice\n'


def test_upload_limits_formats_and_source_coordinates(authenticated):
    c,a,b=authenticated
    assert c.post('/api/documents?filename=file.exe',headers=a,content=b'a').status_code==422
    assert c.post('/api/documents?filename=file.txt',headers=a,content=b'').status_code==413
    assert c.post('/api/documents?filename=file.txt',headers=a,content=b'a'*(server.MAX_UPLOAD_BYTES+1)).status_code==413
    assert c.get('/api/source/missing?page=0',headers=a).status_code==422


def test_quality_block_never_returns_a_fact_or_action(authenticated,monkeypatch):
    """Explicit gate-fault injection; real ingestion, not an upstream model claim."""
    from kernel.core.contracts import GateResult, GateVerdict
    def blocked(self,extraction):
        return GateResult(verdict=GateVerdict.BLOCK,calibrated_confidence=.1,reasons=['test block oracle'])
    monkeypatch.setattr(server.LocalQualityGate,'check',blocked)
    client,a,b=authenticated
    result=client.post('/api/extract-document',headers=a,json={'file':'sample_memo_01.txt'})
    assert result.status_code==200 and result.json()['fields']=={} and result.json()['refused_fields']
    demo=client.post('/demo',headers=a,json={'file':'sample_memo_01.txt'})
    assert demo.status_code==200 and demo.json()['suggestions']==[] and demo.json()['trace']['halted']


def test_real_scoped_review_feedback_can_block_future_facts_without_cross_tenant_effect(authenticated):
    """Actual pack, source, review store and quality gate; no model interception."""
    client,a,b=authenticated
    for index in range(5):
        response=client.post('/api/extract-document',headers=a,json={'file':'sample_memo_01.txt'})
        assert response.status_code==200,response.text
        field=response.json()['fields']['author']
        result=client.post('/correct',headers=a,json={'ext_id':field['ext_id'],'field_name':'author',
            'original':field['value'],'corrected':'Human contradictory review '+str(index),
            'reason':'scope and block regression','expected_revision':0})
        assert result.status_code==200,result.text
    blocked=client.post('/api/extract-document',headers=a,json={'file':'sample_memo_01.txt'}).json()
    assert 'author' not in blocked['fields'] and 'author' in blocked['refused_fields']
    other=client.post('/api/extract-document',headers=b,json={'file':'sample_memo_01.txt'}).json()
    assert 'author' in other['fields'] and other['fields']['author']['grounded']
