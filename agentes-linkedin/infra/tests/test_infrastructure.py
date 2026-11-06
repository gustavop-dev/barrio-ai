import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import httpx
import pytest
from knowledge import agents,db,ingest,memory,providers,retrieval

def test_explicit_container_source_root(monkeypatch):
    from pathlib import Path
    from knowledge import config
    monkeypatch.setattr(config,'INFRA',Path('/app'))
    monkeypatch.setenv('SOURCE_ROOT','/workspace')
    assert config.root()==Path('/workspace')

def test_originals_and_scope():
    assert ingest.verify()['passed']
    result=db.status()
    assert result['units']==1035
    assert [r['session'] for r in result['classes']]==[1,2,3,4,5,6]

def test_idempotent_ingestion_and_persistent_cache():
    before=db.status()
    with db.connect() as c:
        sha=c.execute('SELECT sha256 FROM chunks LIMIT 1').fetchone()['sha256']
        c.execute('INSERT INTO embedding_cache(content_hash,model,dimensions,embedding) VALUES(%s,%s,1536,%s::vector)',(sha,providers.embedding_model(),json.dumps([1.0]+[0.0]*1535)))
    ingest.ingest()
    after=db.status()
    assert all(before[k]==after[k] for k in ['units','chunks','evidence','edges'])
    assert after['embedding_cache']==1
    assert ingest.verify()['passed']

def test_sources_namespaced():
    with db.connect() as c:
        a=c.execute("SELECT original FROM evidence WHERE key='01:qt00007'").fetchone()
        b=c.execute("SELECT original FROM evidence WHERE key='02:qt00007'").fetchone()
    assert a and b and a!=b
    assert retrieval.unit('LI-02-V016-K01')['sources']

def test_original_evidence_preserves_null_characters():
    with db.connect() as c:rows=c.execute('SELECT original FROM evidence').fetchall()
    assert any('\x00' in json.dumps(r,ensure_ascii=False).replace('\\u0000','\x00') for r in rows)

def test_unit_not_exclusive():
    query='titular palabras cliente busca semillas'
    for agent in retrieval.AGENTS:
        results=retrieval.search(query,agent,20)['results']
        assert 'LI-02-V016-K01' in {r['id'] for r in results}

def test_no_fake_semantic_search():
    r=retrieval.search('compradores divulgadores barrio',mode='hybrid')
    assert r['mode']=='lexical' and r['warnings'] and r['results']

def test_unknown_agent_and_sql_input():
    with pytest.raises(ValueError):retrieval.search('titular',agent='admin')
    retrieval.search("'; DROP TABLE units; --")
    assert db.status()['units']==1035

def test_context_keeps_limits_and_original():
    ctx=agents.context('compradores referidores divulgadores barrio','perfil')
    assert ctx['units'] and ctx['context_tokens']<=16000
    for u in ctx['units']:
        assert u['original']==retrieval.unit(u['unit_id'])['original']
        assert 'limits_errors' in u['original'] and u['source_keys']
    assert not ctx['confirmed_user_memory']

def test_context_preserves_top_semantic_evidence(monkeypatch):
    monkeypatch.setattr(agents,'search',lambda *a,**kw:{'results':[{'id':'LI-02-V016-K01'}],
        'relations':[],'semantic_top_id':'LI-06-M001-K04'})
    ctx=agents.context('gancho','perfil','hybrid')
    assert [u['unit_id'] for u in ctx['units']]==['LI-06-M001-K04','LI-02-V016-K01']

def test_memory_confirmation_and_conflicts():
    p=memory.propose('user','nicho',{'value':'provisional'},'perfil','Hipótesis por validar')
    assert not memory.latest(True)
    with pytest.raises(ValueError):memory.propose('user','nicho',{},'perfil','fuente',0)
    c=memory.confirm(p['id'],1)
    assert c['version']==2 and memory.latest(True)[0]['value']=={'value':'provisional'}
    memory.propose('user','nicho',{'value':'nuevo borrador'},'perfil','Nueva hipótesis',2)
    assert memory.latest(True)[0]['value']=={'value':'provisional'}
    with pytest.raises(ValueError):memory.confirm(p['id'],1)

def test_working_memory_cannot_be_confirmed():
    p=memory.propose('working','borrador',{},'perfil','Tarea')
    with pytest.raises(ValueError):memory.confirm(p['id'],1)

def test_budget_includes_uncertain_reservations(monkeypatch):
    monkeypatch.setenv('OPENAI_LIMIT_USD','0.10')
    rid=providers.reserve('openai','test','0.08');providers.settle(rid,'uncertain')
    with pytest.raises(ValueError):providers.reserve('openai','test','0.03')
    providers.settle(rid,'complete',{'total_tokens':2},Decimal('0.01'))
    providers.reserve('openai','test','0.09')

def test_concurrent_reservations_do_not_overspend(monkeypatch):
    monkeypatch.setenv('OPENAI_LIMIT_USD','0.10')
    def attempt(_):
        try:providers.reserve('openai','test','0.07');return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:assert sum(pool.map(attempt,range(2)))==1

def test_embedding_cache_and_model_separation(monkeypatch):
    monkeypatch.setenv('LIVE_PROVIDERS','true');monkeypatch.setenv('OPENAI_API_KEY','test-only')
    calls=[]
    def fake(url,**kw):
        texts=kw['json']['input'];calls.append(texts)
        return httpx.Response(200,json={'data':[{'index':i,'embedding':[1.0]+[0.0]*1535} for i,_ in enumerate(texts)],'usage':{'total_tokens':10}})
    monkeypatch.setattr('httpx.post',fake)
    a=providers.embeddings(['prueba','prueba'])
    assert len(a)==2 and len(calls)==1
    providers.embeddings(['prueba']);assert len(calls)==1
    monkeypatch.setenv('EMBEDDING_MODEL','text-embedding-3-large')
    providers.embeddings(['prueba']);assert len(calls)==2

def test_timeout_holds_reservation_no_retry(monkeypatch):
    monkeypatch.setenv('LIVE_PROVIDERS','true');monkeypatch.setenv('OPENAI_API_KEY','test-only')
    calls=[]
    def timeout(*a,**kw):calls.append(1);raise httpx.ReadTimeout('test')
    monkeypatch.setattr('httpx.post',timeout)
    with pytest.raises(ValueError):providers.embeddings(['timeout'])
    with pytest.raises(ValueError,match='idéntica pendiente o incierta'):providers.embeddings(['timeout'])
    assert len(calls)==1
    with db.connect() as c:assert c.execute('SELECT status FROM usage_ledger').fetchone()['status']=='uncertain'

def test_hybrid_search_uses_vectors_and_warns_partial(monkeypatch):
    vector=[1.0]+[0.0]*1535
    with db.connect() as c:
        row=c.execute("SELECT sha256 FROM chunks WHERE unit_id='LI-01-M006-K02' LIMIT 1").fetchone()
        c.execute('INSERT INTO embedding_cache(content_hash,model,dimensions,embedding) VALUES(%s,%s,1536,%s::vector)',(row['sha256'],providers.embedding_model(),json.dumps(vector)))
    monkeypatch.setattr(retrieval,'embeddings',lambda texts:[vector for _ in texts])
    result=retrieval.search('identidad urgencia transformación freno',mode='hybrid')
    assert result['mode']=='hybrid' and result['warnings']
    assert any(r['id']=='LI-01-M006-K02' and 'semantic' in r['channels'] for r in result['results'])

def test_operator_retry_keeps_original_uncertain_cost(monkeypatch):
    monkeypatch.setenv('OPENAI_LIMIT_USD','0.10')
    rid=providers.reserve('openai','test','0.04','same-request')
    providers.settle(rid,'uncertain')
    with pytest.raises(ValueError):providers.reserve('openai','test','0.04','same-request')
    providers.authorize_uncertain_retry(rid,'Reviewed finished worker; retain possible spend')
    second=providers.reserve('openai','test','0.04','same-request')
    providers.settle(second,'uncertain')
    with pytest.raises(ValueError):providers.reserve('openai','test','0.01','same-request')
    with pytest.raises(ValueError):providers.reserve('openai','other','0.03')
    with pytest.raises(ValueError):providers.authorize_uncertain_retry(rid,'Again')

def test_connection_failures_are_not_billed_and_retries_bounded(monkeypatch):
    monkeypatch.setenv('LIVE_PROVIDERS','true');monkeypatch.setenv('OPENAI_API_KEY','test-only')
    monkeypatch.setattr(providers.time,'sleep',lambda _:None)
    calls=[]
    def connect_fail(*args,**kwargs):calls.append(1);raise httpx.ConnectError('test')
    monkeypatch.setattr('httpx.post',connect_fail)
    with pytest.raises(ValueError,match='no se envió'):providers.embeddings(['connect-failure'])
    assert len(calls)==3
    with db.connect() as c:
        row=c.execute('SELECT status,usage FROM usage_ledger').fetchone()
        assert row['status']=='rejected' and row['usage']['request_not_sent']

def test_claude_adapter_accounts_for_usage(monkeypatch):
    monkeypatch.setenv('LIVE_PROVIDERS','true');monkeypatch.setenv('ANTHROPIC_API_KEY','test-only')
    calls=[]
    def fake(url,**kw):
        calls.append(url)
        if url.endswith('/count_tokens'):return httpx.Response(200,json={'input_tokens':100})
        return httpx.Response(200,json={'content':[{'type':'text','text':'Respuesta [LI-01-M006-K02]'}],
            'usage':{'input_tokens':100,'output_tokens':20},'stop_reason':'end_turn'})
    monkeypatch.setattr('httpx.post',fake)
    result=providers.claude('instrucciones','pregunta')
    assert len(calls)==2 and result['estimated_usd']==pytest.approx(0.0006)
    with db.connect() as c:
        r=c.execute('SELECT * FROM usage_ledger').fetchone()
        assert r['status']=='complete' and r['actual_usd']<=r['reserved_usd']

def test_preview_idempotency():
    rid=str(uuid.uuid4())
    a=agents.run('perfil','Titular palabras clave',request_id=rid)
    b=agents.run('perfil','Titular palabras clave',request_id=rid)
    assert a['id']==str(b['id']) and a['status']=='preview'
    assert db.status()['runs']==1 and not db.status()['usage']
    with pytest.raises(ValueError):agents.run('perfil','Otra tarea',request_id=rid)

def test_execution_disabled():
    with pytest.raises(ValueError,match='Proveedores desactivados'):agents.run('perfil','Titular palabras clave',execute=True)

def test_agent_rejects_unknown_citations(monkeypatch):
    monkeypatch.setattr(agents,'claude',lambda *a,**k:{'text':'Respuesta [LI-07-V001-K01]','stop_reason':'end_turn'})
    result=agents.run('perfil','titular',execute=True)
    assert result['status']=='validation_failed'
    assert result['citation_check']['unknown']==['LI-07-V001-K01']

def test_grouped_citations_are_all_checked(monkeypatch):
    def response(system,message):
        uid=json.loads(message)['context']['units'][0]['unit_id']
        return {'text':f'Respuesta [{uid}, LI-07-V001-K01]','stop_reason':'end_turn'}
    monkeypatch.setattr(agents,'claude',response)
    result=agents.run('perfil','titular',execute=True)
    assert result['status']=='validation_failed'
    assert len(result['citation_check']['cited'])==2
    assert result['citation_check']['unknown']==['LI-07-V001-K01']
