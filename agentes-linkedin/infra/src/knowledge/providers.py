import json
import math
import os
import uuid
import time
from decimal import Decimal
import httpx
from psycopg.types.json import Jsonb
from .config import live
from .db import connect
from .ingest import ENC, digest

EMBEDDING_PRICES={'text-embedding-3-small':Decimal('0.02'),'text-embedding-3-large':Decimal('0.13')}
MODEL_PRICES={'claude-sonnet-4-6':(Decimal('3'),Decimal('15'))}
DIMENSIONS=1536
REQUEST_SIZE=128

def embedding_model():
    model=os.environ.get('EMBEDDING_MODEL','text-embedding-3-small')
    if model not in EMBEDDING_PRICES:raise ValueError('Modelo de embeddings sin tarifa verificada')
    return model

def reserve(provider,purpose,amount,request_hash=None):
    amount=Decimal(str(amount));limit=Decimal(os.environ.get(provider.upper()+'_LIMIT_USD','1'))
    if not amount.is_finite() or amount<0 or not limit.is_finite() or limit<0:raise ValueError('Presupuesto inválido')
    rid=str(uuid.uuid4())
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103502)')
        if request_hash and c.execute("SELECT id FROM usage_ledger WHERE provider=%s AND request_hash=%s AND (status='reserved' OR (status='uncertain' AND coalesce(usage->>'retry_authorized','false')!='true')) LIMIT 1",(provider,request_hash)).fetchone():
            raise ValueError('Existe una solicitud idéntica pendiente o incierta; conciliarla antes de repetir.')
        spent=c.execute("SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE provider=%s",(provider,)).fetchone()['spent']
        if spent+amount>limit:raise ValueError(f'Límite local de {provider} alcanzado; incluye reservas pendientes.')
        c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,status,request_hash) VALUES(%s,%s,%s,%s,%s,%s)',(rid,provider,purpose,amount,'reserved',request_hash))
    return rid

def validate_token_count(value):
    # Provider usage is untrusted input to the persistent monetary ledger.
    if type(value) is not int or value<0:raise ValueError('Conteo de tokens inválido')
    return value

def settle(rid,status,usage=None,cost=None):
    if status=='complete':
        if cost is None:raise ValueError('Falta el coste de la solicitud completada')
        cost=Decimal(cost)
        if not cost.is_finite() or cost<0:raise ValueError('Coste inválido')
    with connect() as c:c.execute('UPDATE usage_ledger SET status=%s,usage=%s,actual_usd=%s WHERE id=%s',(status,Jsonb(usage or {}),cost,rid))

def authorize_uncertain_retry(rid,reason):
    """Local operator review only. Possible original spend remains reserved forever
    until separately reconciled. A second ambiguous attempt blocks again."""
    if not reason.strip():raise ValueError('Documentar la revisión del reintento')
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103502)')
        row=c.execute('SELECT * FROM usage_ledger WHERE id=%s FOR UPDATE',(rid,)).fetchone()
        if not row or row['status']!='uncertain' or not row['request_hash']:
            raise ValueError('Solo solicitudes inciertas identificadas pueden revisarse')
        if (row['usage'] or {}).get('retry_authorized'):raise ValueError('Este reintento ya fue autorizado')
        metadata=dict(row['usage'] or {},retry_authorized=True,retry_reason=reason,reviewer='local_operator')
        c.execute('UPDATE usage_ledger SET usage=%s WHERE id=%s',(Jsonb(metadata),rid))
    return {'id':str(rid),'retry_authorized':True,'original_reservation_retained_usd':str(row['reserved_usd'])}

def post(url,**kwargs):
    # Connection establishment failures occur before the HTTP request is sent.
    # Never automatically retry a read/write timeout or an HTTP response.
    for attempt in range(3):
        try:return httpx.post(url,**kwargs)
        except (httpx.ConnectError,httpx.ConnectTimeout):
            if attempt==2:raise
            time.sleep(0.5*(attempt+1))

def request(provider,url,payload,reservation,headers):
    try:
        response=post(url,headers=headers,json=payload,timeout=120)
        if response.status_code>=400:
            # Do not expose provider bodies (may contain inputs); do not retry paid calls.
            settle(reservation,'rejected' if response.status_code in (400,401,403,404,413,422,429) else 'uncertain',{'http_status':response.status_code})
            raise ValueError(f'{provider}: HTTP {response.status_code}. Sin reintento automático.')
        return response.json()
    except (httpx.ConnectError,httpx.ConnectTimeout) as exc:
        settle(reservation,'rejected',{'error_type':type(exc).__name__,'request_not_sent':True})
        raise ValueError(f'{provider}: no fue posible conectar; no se envió la solicitud.') from None
    except (httpx.HTTPError,json.JSONDecodeError) as exc:
        settle(reservation,'uncertain',{'error_type':type(exc).__name__})
        raise ValueError(f'{provider}: respuesta incierta. Reserva retenida; revisar antes de repetir.') from None

def embeddings(texts,purpose='query'):
    model=embedding_model();results={}
    # Session lock serializes cache misses, so simultaneous identical queries pay once.
    with connect() as lock:
        lock.execute('SELECT pg_advisory_lock(103503)')
        try:
            for text in dict.fromkeys(texts):
                sha=digest(text)
                row=lock.execute('SELECT embedding::text AS value FROM embedding_cache WHERE content_hash=%s AND model=%s AND dimensions=%s',(sha,model,DIMENSIONS)).fetchone()
                if row:results[text]=json.loads(row['value'])
            missing=[t for t in dict.fromkeys(texts) if t not in results]
            for start in range(0,len(missing),REQUEST_SIZE):
                part=missing[start:start+REQUEST_SIZE];key=live('openai')
                token_count=sum(len(ENC.encode(t)) for t in part)
                if any(not t or len(ENC.encode(t))>8192 for t in part):raise ValueError('Entrada de embedding vacía o demasiado extensa')
                if token_count>300000:raise ValueError('La solicitud supera 300000 tokens; dividir las entradas.')
                rid=reserve('openai',purpose,Decimal(token_count+len(part))*EMBEDDING_PRICES[model]/1000000,
                            digest(json.dumps([model,DIMENSIONS,part],ensure_ascii=False)))
                data=request('openai','https://api.openai.com/v1/embeddings',{'model':model,'input':part,'dimensions':DIMENSIONS,'encoding_format':'float'},rid,{'Authorization':'Bearer '+key})
                try:
                    rows=sorted(data['data'],key=lambda r:r['index'])
                    if [r['index'] for r in rows]!=list(range(len(part))):raise ValueError('Índices inválidos')
                    for row in rows:
                        v=row['embedding']
                        if len(v)!=DIMENSIONS or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in v) or sum(x*x for x in v)==0:raise ValueError('Vector inválido')
                    usage=data['usage'];cost=Decimal(validate_token_count(usage['total_tokens']))*EMBEDDING_PRICES[model]/1000000
                    for text,row in zip(part,rows):
                        results[text]=row['embedding']
                        lock.execute('INSERT INTO embedding_cache(content_hash,model,dimensions,embedding) VALUES(%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING',(digest(text),model,DIMENSIONS,json.dumps(row['embedding'])))
                    lock.commit()
                    settle(rid,'complete',usage,cost)
                except (KeyError,TypeError,ValueError):
                    settle(rid,'uncertain');raise ValueError('Respuesta de embeddings inválida; reserva retenida.') from None
            return [results[t] for t in texts]
        finally:
            lock.execute('SELECT pg_advisory_unlock(103503)')

def index_plan():
    model=embedding_model()
    with connect() as c:
        rows=c.execute('''SELECT DISTINCT ch.sha256,ch.text,ch.tokens FROM chunks ch
            LEFT JOIN embedding_cache e ON ch.sha256=e.content_hash AND e.model=%s AND e.dimensions=%s
            WHERE ch.active AND e.content_hash IS NULL ORDER BY ch.sha256''',(model,DIMENSIONS)).fetchall()
    tokens=sum(r['tokens'] for r in rows)
    return rows,{'model':model,'dimensions':DIMENSIONS,'missing_chunks':len(rows),'tokens':tokens,'estimated_usd':float(Decimal(tokens)*EMBEDDING_PRICES[model]/1000000)}

def index(execute=False):
    rows,plan=index_plan()
    if execute:
        for start in range(0,len(rows),REQUEST_SIZE):embeddings([r['text'] for r in rows[start:start+REQUEST_SIZE]],'index-course-01-06')
        plan['remaining']=index_plan()[1]['missing_chunks']
    return plan

def claude(system,message,max_tokens=1800):
    key=live('anthropic');model=os.environ.get('ANTHROPIC_MODEL','claude-sonnet-4-6')
    if model not in MODEL_PRICES:raise ValueError('Modelo Claude sin tarifa verificada: añadir tarifa y pruebas antes de activarlo')
    headers={'x-api-key':key,'anthropic-version':'2023-06-01'}
    payload={'model':model,'system':system,'messages':[{'role':'user','content':message}]}
    # Use the provider tokenizer before reserving; counting doesn't generate an answer.
    try:
        response=post('https://api.anthropic.com/v1/messages/count_tokens',headers=headers,json=payload,timeout=30)
        if response.status_code!=200:raise ValueError('No se pudo contar tokens de Claude; no se envió la generación.')
        input_tokens=validate_token_count(response.json()['input_tokens'])
    except (httpx.HTTPError,KeyError,TypeError,ValueError):
        raise ValueError('Conteo de Claude no disponible; no se envió la generación.') from None
    ip,op=MODEL_PRICES[model]
    rid=reserve('anthropic','agent-run',(Decimal(input_tokens+256)*ip+Decimal(max_tokens)*op)/1000000)
    data=request('anthropic','https://api.anthropic.com/v1/messages',dict(payload,max_tokens=max_tokens),rid,headers)
    try:
        usage=data['usage'];cost=(Decimal(validate_token_count(usage['input_tokens']))*ip+Decimal(validate_token_count(usage['output_tokens']))*op)/1000000
        answer='\n'.join(b['text'] for b in data['content'] if b['type']=='text')
        if not answer:raise ValueError('Respuesta vacía')
        settle(rid,'complete',usage,cost)
        return {'text':answer,'usage':usage,'estimated_usd':float(cost),'model':model,'stop_reason':data['stop_reason']}
    except (KeyError,TypeError,ValueError):
        settle(rid,'uncertain');raise ValueError('Respuesta Claude inválida; reserva retenida.') from None
