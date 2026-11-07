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
# USD per million input/output tokens (Anthropic first-party API, verified 2026-11-06).
# Cache writes cost 1.25x input and cache reads 0.1x input.
MODEL_PRICES={'claude-opus-5-5':(Decimal('4'),Decimal('20')),'claude-sonnet-5-5':(Decimal('2'),Decimal('10')),
              'claude-haiku-5-5':(Decimal('0.10'),Decimal('0.50')),'claude-sonnet-4-6':(Decimal('3'),Decimal('15'))}
DEFAULT_CLAUDE_MODEL='claude-opus-5-5'
CACHE_WRITE=Decimal('1.25');CACHE_READ=Decimal('0.1')
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

def claude_model(override=None):
    model=override or os.environ.get('ANTHROPIC_MODEL',DEFAULT_CLAUDE_MODEL)
    if model not in MODEL_PRICES:raise ValueError('Modelo Claude sin tarifa verificada: añadir tarifa y pruebas antes de activarlo')
    return model

def anthropic_client(key):
    """Official SDK client. Paid generations are never retried automatically, and
    streaming keeps the read timeout per event instead of for the whole answer."""
    import anthropic
    return anthropic.Anthropic(api_key=key,max_retries=0,
        timeout=anthropic.Timeout(600.0,connect=10.0,read=90.0,write=30.0))

def claude(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None):
    """`model` overrides ANTHROPIC_MODEL for one call (e.g. a cheaper classifier); it must have a verified price."""
    import anthropic
    key=live('anthropic');model=claude_model(model)
    max_tokens=max_tokens or int(os.environ.get('ANTHROPIC_MAX_TOKENS','8000'))
    if not 1<=max_tokens<=64000:raise ValueError('max_tokens fuera de rango')
    client=anthropic_client(key)
    # Stable instructions first so they can be cached; the variable task goes in messages.
    params={'model':model,'system':[{'type':'text','text':system,'cache_control':{'type':'ephemeral'}}],
            'messages':[{'role':'user','content':message}]}
    output_config={}
    if effort:output_config['effort']=effort
    if output_schema:output_config['format']={'type':'json_schema','schema':output_schema}
    if output_config:params['output_config']=output_config
    # Use the provider tokenizer before reserving; counting doesn't generate an answer.
    try:input_tokens=validate_token_count(client.messages.count_tokens(**params).input_tokens)
    except (anthropic.APIError,AttributeError,TypeError,ValueError):
        raise ValueError('Conteo de Claude no disponible; no se envió la generación.') from None
    ip,op=MODEL_PRICES[model]
    # Worst case: every input token is a cache write.
    rid=reserve('anthropic',purpose,(Decimal(input_tokens+256)*ip*CACHE_WRITE+Decimal(max_tokens)*op)/1000000)
    request_id=None
    try:
        with client.messages.stream(max_tokens=max_tokens,**params) as stream:
            request_id=stream.request_id
            message=stream.get_final_message()
    except anthropic.APIStatusError as exc:
        # Do not expose provider bodies (may contain inputs); do not retry paid calls.
        definite=exc.status_code in (400,401,403,404,413,422,429)
        settle(rid,'rejected' if definite else 'uncertain',{'http_status':exc.status_code,'request_id':getattr(exc,'request_id',None)})
        raise ValueError(f'anthropic: HTTP {exc.status_code}. Sin reintento automático.') from None
    except (anthropic.APIError,httpx.HTTPError) as exc:
        # Includes timeouts: the request may have been processed and billed.
        settle(rid,'uncertain',{'error_type':type(exc).__name__,'request_id':request_id})
        raise ValueError('anthropic: respuesta incierta. Reserva retenida; revisar antes de repetir.') from None
    try:
        usage=message.usage
        tokens={'input_tokens':validate_token_count(usage.input_tokens),'output_tokens':validate_token_count(usage.output_tokens),
                'cache_creation_input_tokens':validate_token_count(getattr(usage,'cache_creation_input_tokens',None) or 0),
                'cache_read_input_tokens':validate_token_count(getattr(usage,'cache_read_input_tokens',None) or 0)}
        cost=(Decimal(tokens['input_tokens'])*ip+Decimal(tokens['cache_creation_input_tokens'])*ip*CACHE_WRITE
              +Decimal(tokens['cache_read_input_tokens'])*ip*CACHE_READ+Decimal(tokens['output_tokens'])*op)/1000000
        answer='\n'.join(b.text for b in message.content if b.type=='text')
        stop_reason=message.stop_reason
    except (AttributeError,TypeError,ValueError):
        settle(rid,'uncertain',{'request_id':request_id});raise ValueError('Respuesta Claude inválida; reserva retenida.') from None
    record=dict(tokens,request_id=request_id,stop_reason=stop_reason)
    settle(rid,'complete',record,cost)
    if stop_reason=='refusal':raise ValueError('Claude declinó la solicitud; no se generó contenido.')
    if not answer:raise ValueError('Respuesta Claude vacía.')
    return {'text':answer,'usage':record,'estimated_usd':float(cost),'model':model,'stop_reason':stop_reason,'request_id':request_id}

# --------------------------------------------------------------------------- TypeSafe (Jev)
# System One model: typed judgments with calibrated probabilities; it does not generate text.
# Contract: https://docs.typesafe.ai/api/system-one.md and /models.md (consulted 2026-11-07): POST /v1/systemone
# with {model, state, questions}; answers by question name; billed per input token, output free.
TYPESAFE_URL='https://api.typesafe.ai/v1/systemone'
TYPESAFE_PRICES={'jev-1.14.0':Decimal('0.042'),'jev-1.13.0':Decimal('0.042')}  # USD per million input tokens
DEFAULT_TYPESAFE_MODEL='jev-1.14.0'
TYPESAFE_TRANSPORT=None  # tests inject an httpx.MockTransport

def typesafe(state,questions,purpose='lead-review'):
    """One Jev request, never retried automatically; reserved and settled in the usage ledger like any paid call."""
    key=live('typesafe')
    model=os.environ.get('TYPESAFE_MODEL',DEFAULT_TYPESAFE_MODEL)
    if model not in TYPESAFE_PRICES:raise ValueError('Modelo TypeSafe sin tarifa verificada: añadir tarifa y pruebas antes de activarlo')
    raw=json.dumps({'model':model,'state':state,'questions':questions},ensure_ascii=False)
    price=TYPESAFE_PRICES[model]
    # No tokenizer endpoint: a token is never longer than one character, so characters bound the input.
    rid=reserve('typesafe',purpose,Decimal(len(raw))*price/1000000)
    try:
        with httpx.Client(transport=TYPESAFE_TRANSPORT,timeout=httpx.Timeout(60.0,connect=10.0)) as http:
            response=http.post(TYPESAFE_URL,content=raw.encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    except (httpx.ConnectError,httpx.ConnectTimeout):
        settle(rid,'rejected',{'error_type':'connect'});raise ValueError('TypeSafe: no fue posible conectar; no se envió.') from None
    except httpx.HTTPError as exc:
        settle(rid,'uncertain',{'error_type':type(exc).__name__});raise ValueError('TypeSafe: respuesta incierta.') from None
    if response.status_code>=400:
        settle(rid,'uncertain' if response.status_code>=500 else 'rejected',{'http_status':response.status_code})
        raise ValueError(f'TypeSafe: HTTP {response.status_code}. Sin reintento automático.')
    try:
        data=response.json();answers=data['answers']
        tokens={'input_tokens':validate_token_count(data['usage']['input_tokens']),
                'output_tokens':validate_token_count(data['usage'].get('output_tokens',0))}
        if not isinstance(answers,dict):raise TypeError
    except (ValueError,KeyError,TypeError):
        settle(rid,'uncertain',{});raise ValueError('TypeSafe: respuesta ilegible; reserva retenida.') from None
    cost=Decimal(tokens['input_tokens'])*price/1000000
    settle(rid,'complete',dict(tokens,model=data.get('model')),cost)
    return {'answers':answers,'model':data.get('model') or model,'usage':tokens,'estimated_usd':float(cost)}
