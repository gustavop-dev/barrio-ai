import json
import math
import os
import uuid
import time
import re
from dataclasses import dataclass
from functools import lru_cache
from decimal import Decimal, ROUND_UP
import httpx
from psycopg.types.json import Jsonb
from .config import live
from .cycle_context import timeout as cycle_timeout, CycleStopped
from .db import connect
from .ingest import ENC, digest

EMBEDDING_PRICES={'text-embedding-3-small':Decimal('0.02'),'text-embedding-3-large':Decimal('0.13')}
# USD per million input/output tokens (Anthropic first-party API, verified 2026-11-06).
# Cache writes cost 1.25x input. Cache reads cost 0.1x input, except where the model lists its own price
# (Opus 5.5 reads at $0.20/M, 0.05x its $4 input; verified 2026-11-07).
MODEL_PRICES={'claude-opus-5-5':(Decimal('4'),Decimal('20')),'claude-sonnet-5-5':(Decimal('2'),Decimal('10')),
              'claude-haiku-5-5':(Decimal('0.10'),Decimal('0.50')),'claude-sonnet-4-6':(Decimal('3'),Decimal('15'))}
DEFAULT_CLAUDE_MODEL='claude-opus-5-5'
CACHE_WRITE=Decimal('1.25');CACHE_READ=Decimal('0.1')
CACHE_READ_BY_MODEL={'claude-opus-5-5':Decimal('0.05')}

def cache_read_multiplier(model):
    return CACHE_READ_BY_MODEL.get(model,CACHE_READ)
DIMENSIONS=1536
REQUEST_SIZE=128

RESEARCH_PURPOSES=('web-research-capture','editorial-web-research','web-research-tool')


@dataclass(frozen=True)
class WebTools:
    search_type:str
    fetch_type:str
    searches:int
    fetches:int
    content_tokens:int
    search_tokens:int
    search_price:Decimal

    def definitions(self):
        if not re.fullmatch(r'web_search_\d{8}',self.search_type) or not re.fullmatch(r'web_fetch_\d{8}',self.fetch_type):
            raise ValueError('Tipo de herramienta web inválido')
        if any(type(n) is not int or not 0<=n<=5 for n in (self.searches,self.fetches)):
            raise ValueError('Límites de herramientas web inválidos')
        if not 1<=self.content_tokens<=20000 or not 1<=self.search_tokens<=100000:
            raise ValueError('Reserva de tokens web inválida')
        if not self.search_price.is_finite() or self.search_price<0:raise ValueError('Tarifa web inválida')
        tools=[]
        if self.searches:tools.append({'type':self.search_type,'name':'web_search','max_uses':self.searches})
        if self.fetches:tools.append({'type':self.fetch_type,'name':'web_fetch','max_uses':self.fetches,
                                     'max_content_tokens':self.content_tokens,'citations':{'enabled':True}})
        if not tools:raise ValueError('Herramientas web desactivadas')
        return tools

    def reserved_input(self,input_tokens):
        # Every tool turn can replay all accumulated result/input tokens. Reserve before generating.
        return (input_tokens+256+self.searches*self.search_tokens+self.fetches*self.content_tokens)*(1+self.searches+self.fetches)

def embedding_model():
    model=os.environ.get('EMBEDDING_MODEL','text-embedding-3-small')
    if model not in EMBEDDING_PRICES:raise ValueError('Modelo de embeddings sin tarifa verificada')
    return model

def limit_window_start(provider,now=None):
    """B5: a provider limit (<PROVIDER>_LIMIT_USD) is monthly: the calendar month in OPERATOR_TIMEZONE, the same month
    the office shows. <PROVIDER>_LIMIT_WINDOW=total keeps the old lifetime sum (returns None)."""
    if os.environ.get(provider.upper()+'_LIMIT_WINDOW','month').strip().lower()=='total':return None
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    local=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(os.environ.get('OPERATOR_TIMEZONE','America/Bogota')))
    return local.replace(day=1,hour=0,minute=0,second=0,microsecond=0)

def reserve(provider,purpose,amount,request_hash=None,metadata=None):
    amount=Decimal(str(amount));limit=Decimal(os.environ.get(provider.upper()+'_LIMIT_USD','1'))
    if not amount.is_finite() or amount<0 or not limit.is_finite() or limit<0:raise ValueError('Presupuesto inválido')
    rid=str(uuid.uuid4())
    with connect() as c:
        c.execute('SELECT pg_advisory_xact_lock(103502)')
        # An ambiguous request must be reconciled even when its reservation also
        # exhausted a budget. Keep that diagnostic ahead of all monetary caps.
        if request_hash and c.execute("SELECT id FROM usage_ledger WHERE provider=%s AND request_hash=%s AND (status='reserved' OR (status='uncertain' AND coalesce(usage->>'retry_authorized','false')!='true')) LIMIT 1",(provider,request_hash)).fetchone():
            raise ValueError('Existe una solicitud idéntica pendiente o incierta; conciliarla antes de repetir.')
        from .cycle_context import provider_metadata
        metadata=dict(metadata or {},**provider_metadata(provider,purpose,amount,c))
        if purpose in RESEARCH_PURPOSES:
            from django.conf import settings
            from team_backend.operador import period_starts
            day,_=period_starts()
            research_limit=Decimal(settings.WEB_RESEARCH_DAILY_USD)
            if not research_limit.is_finite() or research_limit<0:raise ValueError('Presupuesto web inválido')
            research_spent=c.execute("SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE purpose=ANY(%s) AND created_at>=%s",(list(RESEARCH_PURPOSES),day)).fetchone()['spent']
            if research_spent+amount>research_limit:raise ValueError('Presupuesto web diario agotado; incluye reservas pendientes')
        if purpose.startswith(('editorial-','image-')):
            from team_backend.operador import period_starts
            day,_=period_starts()
            editorial_limit=min(Decimal('2'),Decimal(os.environ.get('EDITORIAL_DAILY_LLM_USD','2')))
            if not editorial_limit.is_finite() or editorial_limit<0:raise ValueError('Presupuesto editorial inválido')
            editorial_spent=c.execute("SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE (purpose LIKE 'editorial-%%' OR purpose LIKE 'image-%%') AND created_at>=%s",(day,)).fetchone()['spent']
            if editorial_spent+amount>editorial_limit:raise ValueError('Presupuesto editorial diario agotado; incluye herramientas y reservas')
        if purpose.startswith('image-'):
            from team_backend.operador import period_starts
            day,_=period_starts()
            image_limit=Decimal(os.environ.get('IMAGE_DAILY_USD','1'))
            if not image_limit.is_finite() or image_limit<0:raise ValueError('Presupuesto de imágenes inválido')
            image_spent=c.execute("SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE purpose LIKE 'image-%%' AND created_at>=%s",(day,)).fetchone()['spent']
            if image_spent+amount>image_limit:raise ValueError('Presupuesto de imágenes agotado; incluye reservas pendientes')
        since=limit_window_start(provider)
        spent=c.execute("SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE provider=%s AND (%s::timestamptz IS NULL OR created_at>=%s)",(provider,since,since)).fetchone()['spent']
        if spent+amount>limit:
            missing=(spent+amount-limit).quantize(Decimal('0.000001'),rounding=ROUND_UP)
            raise ValueError(f'Límite local de {provider} alcanzado'+(' este mes' if since else '')+
                f'; faltan {missing} USD; límite {limit}, gastado {spent} (incluye reservas pendientes); reserva {amount} USD.')
        c.execute('INSERT INTO usage_ledger(id,provider,purpose,reserved_usd,status,request_hash,usage) VALUES(%s,%s,%s,%s,%s,%s,%s)',(rid,provider,purpose,amount,'reserved',request_hash,Jsonb(metadata or {})))
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
    with connect() as c:c.execute("UPDATE usage_ledger SET status=%s,usage=coalesce(usage,'{}'::jsonb)||%s,actual_usd=%s WHERE id=%s",(status,Jsonb(usage or {}),cost,rid))
    from .cycle_context import after_settle
    after_settle()

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
    from .cycle_context import timeout
    request_timeout=kwargs.get('timeout',120)
    # Connection establishment failures occur before the HTTP request is sent.
    # Never automatically retry a read/write timeout or an HTTP response.
    for attempt in range(3):
        kwargs['timeout']=timeout(request_timeout)
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

@lru_cache(maxsize=4)
def _anthropic_client(key):
    import anthropic
    return anthropic.Anthropic(api_key=key,max_retries=0,
        timeout=anthropic.Timeout(600.0,connect=10.0,read=90.0,write=30.0))

def anthropic_client(key):
    """Official SDK client, built once per key and reused (it keeps its connection pool). Paid generations are
    never retried automatically, and streaming keeps the read timeout per event instead of for the whole answer."""
    return _anthropic_client(key)

def system_blocks(system,context=None):
    """System prompt as cacheable blocks: the instructions, then any stable context (str or list of str, e.g. course
    units). The instructions and the end of the context each carry a breakpoint (2 of the 4 allowed), so calls that
    repeat them read them at the cache price."""
    extra=[context] if isinstance(context,str) else list(context or [])
    blocks=[{'type':'text','text':system}]+[{'type':'text','text':text} for text in extra if text]
    for block in (blocks[0],blocks[-1]):block['cache_control']={'type':'ephemeral'}
    return blocks

def claude(system,message,max_tokens=None,output_schema=None,effort=None,purpose='agent-run',model=None,context=None,
           web_tools=None,request_hash=None):
    """`model` overrides ANTHROPIC_MODEL for one call (e.g. a cheaper classifier); it must have a verified price.
    `context` is stable text (str or list of str) sent after the instructions and cached with them."""
    import anthropic
    key=live('anthropic');model=claude_model(model)
    max_tokens=max_tokens or int(os.environ.get('ANTHROPIC_MAX_TOKENS','8000'))
    if not 1<=max_tokens<=64000:raise ValueError('max_tokens fuera de rango')
    client=anthropic_client(key)
    from .cycle_context import current, timeout
    if current():client=client.with_options(timeout=timeout(120))
    # Stable instructions and context first so they can be cached; the variable task goes in messages.
    params={'model':model,'system':system_blocks(system,context),'messages':[{'role':'user','content':message}]}
    if web_tools is not None:
        if not isinstance(web_tools,WebTools) or purpose not in RESEARCH_PURPOSES:
            raise ValueError('Herramientas web fuera del contrato de investigación')
        # Native citations and JSON schema output are not combined. Parse native citation blocks instead.
        if output_schema:raise ValueError('La investigación usa citas nativas, no JSON generado con fuentes inventadas')
        params['tools']=web_tools.definitions()
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
    reserved_input=web_tools.reserved_input(input_tokens) if web_tools else input_tokens+256
    tool_cost=web_tools.search_price*web_tools.searches if web_tools else Decimal(0)
    metadata={'research':True,'reserved_web_search_requests':web_tools.searches,'reserved_web_fetch_requests':web_tools.fetches,
              'reserved_input_tokens':reserved_input,'model':model} if web_tools else None
    metadata=dict(metadata or {},model=model,effort=effort)
    rid=reserve('anthropic',purpose,(Decimal(reserved_input)*ip*CACHE_WRITE+Decimal(max_tokens)*op)/1000000+tool_cost,
                request_hash,metadata=metadata)
    request_id=None
    try:
        if current():client=client.with_options(timeout=timeout(120))
        with client.messages.stream(max_tokens=max_tokens,**params) as stream:
            request_id=stream.request_id
            if current():
                for event in stream:timeout(120)  # Bound total streaming time, even with continuous events.
            message=stream.get_final_message()
    except CycleStopped:
        settle(rid,'uncertain',{'request_id':request_id,'cycle_timeout':True})
        raise
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
              +Decimal(tokens['cache_read_input_tokens'])*ip*cache_read_multiplier(model)+Decimal(tokens['output_tokens'])*op)/1000000
        content=None
        if web_tools:
            content=[block.model_dump(mode='json') for block in message.content]
            server_usage=getattr(usage,'server_tool_use',None)
            used_search=any(b.get('type')=='server_tool_use' and b.get('name')=='web_search' for b in content)
            used_fetch=sum(b.get('type')=='server_tool_use' and b.get('name')=='web_fetch' for b in content)
            reported_searches=getattr(server_usage,'web_search_requests',None)
            searches=validate_token_count(0 if reported_searches is None and not used_search else reported_searches)
            reported_fetches=getattr(server_usage,'web_fetch_requests',None)
            fetches=validate_token_count(used_fetch if reported_fetches is None else reported_fetches)
            tokens.update(web_search_requests=searches,web_fetch_requests=fetches)
            cost+=web_tools.search_price*searches
            # The SDK retains native server results and citations; callers never reconstruct URLs from prose.
        answer='\n'.join(b.text for b in message.content if b.type=='text')
        stop_reason=message.stop_reason
    except (AttributeError,TypeError,ValueError):
        settle(rid,'uncertain',{'request_id':request_id});raise ValueError('Respuesta Claude inválida; reserva retenida.') from None
    record=dict(tokens,request_id=request_id,stop_reason=stop_reason)
    if web_tools:record.update(research=True,search_usd=str(web_tools.search_price*tokens['web_search_requests']))
    settle(rid,'complete',record,cost)
    if stop_reason=='refusal':raise ValueError('Claude declinó la solicitud; no se generó contenido.')
    # Thinking counts against max_tokens: a structured answer cut there is incomplete JSON. Say so instead of
    # letting the caller report «invalid JSON» (the spend is already settled above).
    if stop_reason=='max_tokens' and output_schema:
        raise ValueError(f'Claude agotó max_tokens ({max_tokens}) antes de terminar la respuesta; subir el tope de {purpose}.')
    if not answer and not web_tools:raise ValueError('Respuesta Claude vacía.')
    result={'text':answer,'usage':record,'estimated_usd':float(cost),'model':model,'stop_reason':stop_reason,'request_id':request_id}
    if web_tools:result.update(content=content,ledger_id=rid)
    return result

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
        with httpx.Client(transport=TYPESAFE_TRANSPORT,timeout=httpx.Timeout(cycle_timeout(60.0),connect=10.0)) as http:
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

# --------------------------------------------------------------------------- AssemblyAI (voice notes of the capture button)
# Contract (consulted 2026-11-07): https://www.assemblyai.com/docs/llms.txt, «Upload a media file»
# (POST /v2/upload, raw bytes as application/octet-stream -> {upload_url}), «Create transcript» (POST /v2/transcript
# with {audio_url, speech_models, language_detection}), «Get transcript» (GET /v2/transcript/{id}: status
# queued|processing|completed|error, text, language_code, audio_duration in seconds, speech_model_used, error),
# «Model selection» (the first model of speech_models that supports the language is used) and «Billing and pricing»
# (pro-rated to the second of audio processed; errored transcripts are not charged). Universal-3.5 Pro costs
# $0.21/h and Universal-2 $0.15/h. Header `authorization: <key>`.
ASSEMBLYAI_URL='https://api.assemblyai.com/v2'
ASSEMBLYAI_MODELS=['universal-3-5-pro','universal-2']
ASSEMBLYAI_MAX_SECONDS=1800  # worst case reserved when the client does not say how long the audio is
ASSEMBLYAI_POLL_SECONDS=3
ASSEMBLYAI_TRANSPORT=None  # tests inject an httpx.MockTransport

def assemblyai_prices():
    """USD per hour by model; ASSEMBLYAI_USD_PER_HOUR prices the preferred model (and the reservation)."""
    return {'universal-3-5-pro':Decimal(os.environ.get('ASSEMBLYAI_USD_PER_HOUR','0.21')),'universal-2':Decimal('0.15')}

def _assemblyai_seconds(value):
    try:seconds=float(value)
    except (TypeError,ValueError):return ASSEMBLYAI_MAX_SECONDS
    if not math.isfinite(seconds) or seconds<=0:return ASSEMBLYAI_MAX_SECONDS
    return min(seconds,ASSEMBLYAI_MAX_SECONDS)

def assemblyai_transcribe(path,duration_s=None,purpose='capture-transcribe'):
    """Transcribe one local audio file: upload, create, poll. One paid request, never retried automatically.
    Reserves the worst case from the client's duration (capped at 30 min) and settles with the real audio_duration;
    an errored transcript is not charged (rejected). A timeout keeps the reservation (uncertain): AssemblyAI may
    still finish and bill it."""
    key=live('assemblyai')
    prices=assemblyai_prices();rate=prices[ASSEMBLYAI_MODELS[0]]
    if not rate.is_finite() or rate<0:raise ValueError('ASSEMBLYAI_USD_PER_HOUR inválido')
    try:timeout_s=float(os.environ.get('ASSEMBLYAI_TIMEOUT_S','300'))
    except ValueError:raise ValueError('ASSEMBLYAI_TIMEOUT_S inválido') from None
    with open(path,'rb') as handle:audio=handle.read()
    if not audio:raise ValueError('El audio está vacío; no se envió a transcribir.')
    reserved=Decimal(str(_assemblyai_seconds(duration_s)))*rate/3600
    # The same bytes cannot be sent again while an earlier attempt is pending or uncertain.
    rid=reserve('assemblyai',purpose,reserved,digest(audio))
    headers={'authorization':key}
    with httpx.Client(transport=ASSEMBLYAI_TRANSPORT,timeout=httpx.Timeout(120.0,connect=10.0)) as http:
        # 1. Upload: not billed by itself; nothing can be transcribed (or charged) if it fails.
        try:response=http.post(ASSEMBLYAI_URL+'/upload',content=audio,headers=dict(headers,**{'content-type':'application/octet-stream'}))
        except httpx.HTTPError as exc:
            settle(rid,'rejected',{'step':'upload','error_type':type(exc).__name__})
            raise ValueError('AssemblyAI: no se pudo subir el audio; no se transcribió nada.') from None
        if response.status_code>=400:
            settle(rid,'rejected',{'step':'upload','http_status':response.status_code})
            raise ValueError(f'AssemblyAI: HTTP {response.status_code} al subir el audio. Sin reintento automático.')
        try:upload_url=response.json()['upload_url']
        except (ValueError,KeyError,TypeError):
            settle(rid,'rejected',{'step':'upload'});raise ValueError('AssemblyAI: respuesta de subida ilegible; no se transcribió.') from None
        # 2. Create the transcript: the paid request.
        body={'audio_url':upload_url,'speech_models':ASSEMBLYAI_MODELS,'language_detection':True}
        try:response=http.post(ASSEMBLYAI_URL+'/transcript',json=body,headers=headers)
        except (httpx.ConnectError,httpx.ConnectTimeout):
            settle(rid,'rejected',{'step':'create','error_type':'connect','request_not_sent':True})
            raise ValueError('AssemblyAI: no fue posible conectar; no se envió la transcripción.') from None
        except httpx.HTTPError as exc:
            settle(rid,'uncertain',{'step':'create','error_type':type(exc).__name__})
            raise ValueError('AssemblyAI: respuesta incierta al crear la transcripción. Reserva retenida; no se repite.') from None
        if response.status_code>=400:
            settle(rid,'uncertain' if response.status_code>=500 else 'rejected',{'step':'create','http_status':response.status_code})
            raise ValueError(f'AssemblyAI: HTTP {response.status_code} al crear la transcripción. Sin reintento automático.')
        try:transcript_id=str(response.json()['id'])
        except (ValueError,KeyError,TypeError):
            settle(rid,'uncertain',{'step':'create'})
            raise ValueError('AssemblyAI: respuesta ilegible al crear la transcripción; reserva retenida.') from None
        # 3. Poll until completed or error. Reads are free: a transient read failure only waits for the next poll.
        deadline=time.monotonic()+timeout_s
        while True:
            data,status=_assemblyai_read(http,transcript_id,headers)
            if data is not None and data.get('status') in ('completed','error'):break
            if status is not None:
                settle(rid,'uncertain',{'step':'poll','transcript_id':transcript_id,'http_status':status})
                raise ValueError(f'AssemblyAI: HTTP {status} al leer la transcripción; reserva retenida, no se repite.')
            if time.monotonic()>=deadline:
                settle(rid,'uncertain',{'step':'poll','transcript_id':transcript_id,'timeout_s':timeout_s})
                raise ValueError(f'AssemblyAI: la transcripción no terminó en {int(timeout_s)} s. No se reintenta; '
                                 'si AssemblyAI la termina, se cobra igual (reserva retenida).')
            time.sleep(ASSEMBLYAI_POLL_SECONDS)
    if data['status']=='error':
        # «If a request errors, you aren't charged for it.»
        settle(rid,'rejected',{'transcript_id':transcript_id,'status':'error'})
        raise ValueError('AssemblyAI no pudo transcribir el audio: '+str(data.get('error') or 'sin detalle')[:200])
    model=data.get('speech_model_used') or ASSEMBLYAI_MODELS[0]
    seconds=data.get('audio_duration')
    usage={'transcript_id':transcript_id,'speech_model_used':model,'audio_duration':seconds,'language_code':data.get('language_code')}
    if isinstance(seconds,(int,float)) and not isinstance(seconds,bool) and math.isfinite(seconds) and seconds>=0:
        cost=Decimal(str(seconds))*prices.get(model,rate)/3600
    else:
        cost=reserved;usage['duration_missing']=True
    settle(rid,'complete',usage,cost)
    return {'text':(data.get('text') or '').strip(),'language':data.get('language_code') or '','id':transcript_id,
            'audio_duration':seconds if 'duration_missing' not in usage else None,'model':model,'estimated_usd':float(cost)}

def _assemblyai_read(http,transcript_id,headers):
    """(transcript, None) on a readable answer; (None, None) on a transient failure; (None, status) on a definite one."""
    try:response=http.get(f'{ASSEMBLYAI_URL}/transcript/{transcript_id}',headers=headers)
    except httpx.HTTPError:return None,None
    if response.status_code in (429,500,502,503,504):return None,None
    if response.status_code>=400:return None,response.status_code
    try:data=response.json()
    except ValueError:return None,None
    return (data,None) if isinstance(data,dict) else (None,None)
