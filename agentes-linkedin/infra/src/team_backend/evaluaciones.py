"""Agent evaluation harness (AI audit, phase 3: «20–30 casos de evaluación por agente»; docs/evaluaciones-agentes.md).

Cases are built at run time from the history in the database where the command runs (production, on the server):
nothing is exported, no dataset is committed, and the report goes to stdout or to a path given on the command line.
Per agent, the case and the known outcome it is graded against:
- verificador   pieces that reached the gate with a known fate: published and not vetoed, blocked, vetoed by Gustavo
                or discarded by the policy. The selection's text goes through the production gate again (deterministic
                rules, verifier, one repair round, rules and verifier once more) and its verdict is compared with the fate.
- comentarios   posts that got an agent draft, with the fate of that draft. The new draft (with its one rules redraft,
                as in production) is graded by the deterministic rules plus the lead's questions (Jev).
- clasificador  classified contacts with a later signal: Gustavo discarded or vetoed them, or the lead discarded an
                action for riesgo (no fit); the person accepted the invitation or commented on an own post (fit).
- lectores      ablation: the selection is re-run with and without the stored panel, and the difference is
                compared with the run-to-run noise (with panel against the stored selection).
- director      descriptive only: skipped and written days, pillar and modality against the metrics that exist.
Graders are deterministic (agreement rates, schema validity, guard violations); there is no model judge. One
would need its own explicit flag.

Dry run by default: case counts, the gap to the target and an ESTIMATED cost per agent and model, without calling
the API (input tokens approximated locally with tiktoken, output from the ledger history, prices from providers).
Paid execution needs `execute` and a `max_usd` cap. Every call goes through providers.claude / providers.typesafe
under purpose eval-<agente>, inside the monthly EVAL_LIMIT_USD (default 0: no paid evaluation until it is set).
The run reads the database and only writes usage ledger rows: no proposal, job or piece is created.

The request builders mirror the production calls (editorial._stage/_check/_repair_round, operador.propose_comment,
red.classify, lider.review): keep them in step. tests/test_evaluaciones.py compares them with the real calls."""
import difflib
import json
import math
import os
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from django.utils import timezone
from knowledge import db, memory, providers
from knowledge.config import live
from knowledge.ingest import ENC
from . import autopiloto, editorial, guardas, lider, operador, orientacion, red, voz
from .models import ActionProposal, AuditEvent, Contact, EditorialPiece, PostMetric

GO_LIVE=date(2026,11,6)  # the machine went live in production
TARGET=(20,30)
AGENTS=('verificador','comentarios','clasificador','lectores','director')
JEV='jev'  # --modelo jev: the classifier judged by Jev (audit C3): the lead's risk question plus a fit question
TOKEN_FACTOR=1.2  # Claude's tokenizer counts ~15–20% more than cl100k (audit, «Costos»)
# Typical output tokens (thinking included) when the ledger has no history for the production purpose.
DEFAULT_OUTPUT={'editorial-verificador':4000,'editorial-seleccion':5000,'editorial-reparacion':5000,'propose-comment':2000,
                'network-classify':4000}
REWRITTEN='Reescrito una vez por las reglas fijas'  # risk operador.propose_comment adds after its rules redraft
FIT_CHECK=('encaja','min',0.6,'no encaja con el barrio')  # the follow threshold the lead used before R2
CLASSIFY_BATCH=10  # as red.classify
FROZEN_KEYS=('primary_reader','modality','pillar','thesis','approach','format','reader_value','evidence','success_criterion','avoid')
PASSED=('aprobado','confirmado')
NON_CONTENT=('Capacidad desactivada','Hash inconsistente')  # discards that say nothing about the text
MILLION=Decimal(1_000_000)

class BudgetStop(Exception):
    """The next call could exceed --max-usd or EVAL_LIMIT_USD: the run stops before it."""

def limit_usd():
    return Decimal(os.environ.get('EVAL_LIMIT_USD','0'))

def eval_spent(since):
    """Evaluation spend (settled cost or pending reservation) of every provider since a moment."""
    with db.connect() as c:
        row=c.execute('''SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain')
            THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE purpose LIKE 'eval-%%' AND created_at>=%s''',(since,)).fetchone()
    return Decimal(row['spent'])

def month_start(now=None):
    day,_=operador.period_starts(now)
    return day.replace(day=1)

# --------------------------------------------------------------------------- cases from the history

def _publish_proposal(piece):
    return piece.proposals.filter(capability=ActionProposal.Capability.PUBLISH).order_by('-created_at').first()

def piece_fate(piece):
    """Known fate of a piece that reached the verifier; None while pending or when it says nothing about the text."""
    if piece.state==EditorialPiece.State.BLOCKED:return 'bloqueada'
    if piece.state!=EditorialPiece.State.READY:return None
    proposal=_publish_proposal(piece)
    if proposal is None:return None
    if proposal.state=='rejected':return 'vetada'
    if proposal.state=='discarded':
        reasons=' '.join([proposal.decision_note,*map(str,proposal.risks)])
        return None if any(m in reasons for m in NON_CONTENT) else 'descartada_politica'
    if proposal.state in ('confirmed','sent'):return 'publicada'
    return None

def verifier_cases(run):
    cases=[]
    for piece in run.pieces().exclude(final_text='').exclude(verification={}):
        fate=piece_fate(piece)
        if fate is None:continue
        cases.append({'id':str(piece.id),'label':fate,'expected':'ready_for_execution' if fate=='publicada' else 'blocked',
                      'baseline':piece.verification.get('verdict'),'piece':piece})
    return cases

def comment_fate(proposal):
    review=proposal.review or {}
    if proposal.state=='rejected':return 'vetado'
    if proposal.state=='discarded':
        if review.get('decision')=='discard':return 'descartado_lider'
        return 'descartado_reglas' if proposal.decided_at else 'saltado'  # a draft created discarded is the agent's skip
    if proposal.state=='confirmed':return 'confirmado'
    if proposal.approved_hash:return 'aprobado'
    return None

def comment_cases(run):
    """The latest agent draft of each post since the start, with its fate."""
    seen=set();cases=[]
    for proposal in (ActionProposal.objects.select_related('post').filter(capability=ActionProposal.Capability.COMMENT,source='agent',
                     post__isnull=False,created_at__gte=run.since).order_by('-created_at')):
        if proposal.post_id in seen:continue
        seen.add(proposal.post_id);fate=comment_fate(proposal)
        if fate is None:continue
        expected='pasa' if fate in PASSED else 'saltado' if fate=='saltado' else 'no_pasa'
        cases.append({'id':str(proposal.post_id),'label':fate,'expected':expected,'proposal':proposal,'post':proposal.post})
    return cases

def own_post_commenters():
    """People who commented with substance on an own post (PostMetric.commenters)."""
    ids=set()
    for commenters in PostMetric.objects.exclude(commenters=None).values_list('commenters',flat=True):
        ids|={c.get('provider_user_id') for c in commenters or [] if isinstance(c,dict) and c.get('substantive')}
    return ids

def contact_signal(contact,commenters):
    """(label, fit) from what Gustavo, the lead or the person did later; None without a signal. Replies in the
    inbox are not observable until the inbox agent exists."""
    proposals=list(contact.proposals.all())
    if any(p.state=='rejected' for p in proposals) or AuditEvent.objects.filter(action='network.contact_discarded',target=str(contact.id)).exists():
        return 'descartado_por_gustavo',False
    if any((p.review or {}).get('decision')=='discard' and any('(riesgo=' in str(r) for r in p.review.get('reasons',[])) for p in proposals):
        return 'riesgo_lider',False
    if contact.stage==Contact.Stage.CONNECTED and contact.invited_at:return 'acepto_invitacion',True
    if contact.provider_user_id in commenters:return 'comento_post_propio',True
    return None

def classifier_cases(run):
    commenters=own_post_commenters();cases=[]
    for contact in Contact.objects.exclude(classification={}).filter(discovered_at__gte=run.since).order_by('-discovered_at'):
        signal=contact_signal(contact,commenters)
        if signal is None:continue
        cases.append({'id':str(contact.id),'label':signal[0],'expected':signal[1],'baseline':bool(contact.classification.get('fit')),'contact':contact})
    return cases

def panel_cases(run):
    return [{'id':str(p.id),'label':(p.selection or {}).get('decision') or 'desconocida','piece':p}
            for p in run.pieces().exclude(variants={}).exclude(panel={}).exclude(selection={})]

def director_cases(run):
    return [{'id':str(p.id),'label':'escrito' if (p.brief or {}).get('decision')=='write' else 'saltado','piece':p}
            for p in run.pieces().exclude(brief={})]

CASES={'verificador':verifier_cases,'comentarios':comment_cases,'clasificador':classifier_cases,'lectores':panel_cases,'director':director_cases}

# --------------------------------------------------------------------------- requests (mirror the production calls)

def _frozen(brief):
    return {k:(brief or {}).get(k) for k in FROZEN_KEYS}

def stage_request(run,name,payload,unit_ids=None):
    """editorial._stage without the piece: same system, voice, units, schema, caps and effort."""
    system,schema,default_units,budget,max_tokens,effort=editorial.STAGES[name][:6]
    if name in editorial.VOICED_STAGES:system=voz.with_voice(system)
    units,missing,_=run.context(unit_ids or default_units,budget)
    if missing:raise ValueError(f'Biblioteca no disponible para la etapa {name}.')
    if not units:raise ValueError(f'Sin unidades del curso para la etapa {name}.')
    message=json.dumps(dict(payload,course_units=units),ensure_ascii=False,default=str)
    return {'system':system,'message':message,'max_tokens':max_tokens,'output_schema':schema,'effort':effort}

def gate_input(piece):
    """The text and claims the gate received: the selection's, before any repair changed piece.final_text."""
    selection=piece.selection or {}
    return (selection.get('final_text') or piece.final_text or '').strip(),selection.get('claims',[])

def verifier_request(run,piece,text,claims):
    return stage_request(run,'verificador',dict(run.editorial_memory(),text=text,brief=_frozen(piece.brief),claims=claims,sources=piece.signals))

def repair_request(run,piece,text,claims,findings):
    return stage_request(run,'reparacion',dict(run.editorial_memory(),brief=_frozen(piece.brief),text=text,claims=claims,findings=findings,
                         sources=piece.signals))

def selection_request(run,piece,panel=True):
    extra={'panel':piece.panel} if panel else {}
    return stage_request(run,'seleccion',dict(run.editorial_memory(),brief=_frozen(piece.brief),variants=piece.variants,**extra,sources=piece.signals))

def comment_request(run,post,revision=None):
    """operador._draft_comment without reading LinkedIn (existing_comments stays empty): instructions, voice and course
    units in cached system blocks; `revision` makes it the redraft after a rule violation."""
    units,missing,_=run.context(operador.COMMENT_UNITS)
    if missing:raise ValueError('Biblioteca no disponible para fundamentar el comentario.')
    if not units:raise ValueError('Sin unidades del curso para fundamentar el comentario.')
    inputs={'post':{'author':post.author_name,'text':post.text,'url':post.share_url},'existing_comments':[],
            'public_facts':run.comment_facts,'private_guidance':run.comment_guidance,'orientation':run.orientation}
    from . import experimentos
    inputs['referent_evidence']=experimentos.signals(post)
    inputs['comment_language']='English; useful contribution, never an empty compliment or pitch.'
    if revision:inputs['revision']=revision
    return {'system':voz.with_voice(operador.COMMENT_SYSTEM),'message':json.dumps(inputs,ensure_ascii=False,default=str),'max_tokens':None,
            'output_schema':operador.COMMENT_SCHEMA,'effort':'medium','context':operador.course_block(units)},units

def classify_request(run,contacts):
    """red.classify for a batch, with the profile data stored today."""
    people=red.classification_people(contacts)
    message=json.dumps({'private_guidance':run.private,'orientation':run.orientation,'people':people,'note_policy':red.note_policy()},ensure_ascii=False,default=str)
    units,missing,_=run.context(red.NETWORK_UNITS)
    if missing:raise ValueError('Biblioteca no disponible para clasificar')
    return {'system':red.CLASSIFY_SYSTEM,'message':message,'max_tokens':16000,'output_schema':red.CLASSIFY_SCHEMA,'effort':'medium',
            'context':operador.course_block(units)}

def lead_request(post,text,orientation):
    """The lead's questions on a comment draft (state, questions, checks), as lider.review asks them."""
    return lider._questions(ActionProposal(capability=ActionProposal.Capability.COMMENT,post=post,payload={'text':text}),orientation)

FIT_QUESTION=('Según `persona.titular`, `persona.ubicacion` y `persona.evidencia`, ¿esta persona encaja en el barrio de Gustavo '
              'descrito en `criterios_del_barrio`?')

def jev_classify_request(contact,orientation):
    """Jev as the classifier: the lead's follow state and risk question (and orientation), plus a fit question of its
    own, since R2 left the lead judging only risk. Fit needs encaja >= 0.6 and the lead's thresholds."""
    state,questions,checks=lider._questions(ActionProposal(capability=ActionProposal.Capability.FOLLOW,contact=contact),orientation)
    return state,dict({'encaja':lider._noul(FIT_QUESTION)},**questions),[FIT_CHECK]+checks

def jev_verdict(answers,checks):
    """(passes, failed labels, probabilities) with lider.review's thresholds."""
    values={qid:round(float((a or {}).get('noul',0.5)),3) for qid,a in (answers or {}).items()}
    failed=[label for qid,bound,threshold,label in checks
            if values.get(qid) is None or (bound=='min' and values[qid]<threshold) or (bound=='max' and values[qid]>threshold)]
    return not failed,failed,values

# --------------------------------------------------------------------------- cost estimates (no API call)

def input_tokens(request):
    parts=(request['system'],request.get('context') or '',request['message'])
    return math.ceil(sum(len(ENC.encode(part,disallowed_special=())) for part in parts)*TOKEN_FACTOR)

def max_tokens(request):
    return request.get('max_tokens') or int(os.environ.get('ANTHROPIC_MAX_TOKENS','8000'))

def claude_usd(tokens,model,output):
    """Estimate: every input token a cache write (1.25x) plus the typical output."""
    ip,op=providers.MODEL_PRICES[model]
    return (Decimal(tokens)*ip*providers.CACHE_WRITE+Decimal(output)*op)/MILLION

def worst_usd(request,model):
    """What providers.claude reserves: every input token a cache write and the whole max_tokens."""
    ip,op=providers.MODEL_PRICES[model]
    return (Decimal(input_tokens(request)+256)*ip*providers.CACHE_WRITE+Decimal(max_tokens(request))*op)/MILLION

def jev_model():
    return os.environ.get('TYPESAFE_MODEL',providers.DEFAULT_TYPESAFE_MODEL)

def jev_usd(state,questions):
    """What providers.typesafe reserves: characters bound the input tokens; output is free."""
    model=jev_model();price=providers.TYPESAFE_PRICES.get(model,max(providers.TYPESAFE_PRICES.values()))
    return Decimal(len(json.dumps({'model':model,'state':state,'questions':questions},ensure_ascii=False)))*price/MILLION

def typical_outputs():
    """Mean output tokens per production purpose from the ledger, or the defaults; and how many calls measured it."""
    with db.connect() as c:
        rows=c.execute('''SELECT purpose,avg((usage->>'output_tokens')::numeric) AS tokens,count(*) AS n FROM usage_ledger
            WHERE provider='anthropic' AND status='complete' AND usage->>'output_tokens' IS NOT NULL AND purpose=ANY(%s)
            GROUP BY purpose''',(list(DEFAULT_OUTPUT),)).fetchall()
    measured={r['purpose']:(int(r['tokens']),r['n']) for r in rows}
    return {p:measured.get(p,(d,0))[0] for p,d in DEFAULT_OUTPUT.items()},{p:n for p,(_,n) in measured.items()}

def production_model(agent):
    if agent=='clasificador':return red.classifier_model()
    stage={'verificador':'verificador','lectores':'seleccion'}.get(agent)
    return (stage and editorial.stage_model(stage)) or providers.claude_model()

def repair_model():
    """The repair is the director's job: it keeps its production model whatever verifier model is evaluated."""
    return editorial.stage_model('reparacion') or providers.claude_model()

def expects_repair(run,piece,text):
    """Whether a run will likely pay a repair round: the rules stop the text, or the piece needed one before."""
    return editorial.repair_enabled() and bool(editorial.text_rules(text,run.public,run.private) or (piece.verification or {}).get('repair'))

def models_for(agent):
    if agent=='director':return []
    first=production_model(agent)
    return [first]+[m for m in providers.MODEL_PRICES if m!=first]+([JEV] if agent=='clasificador' else [])

def planned_calls(run,agent,cases):
    """Model-independent work of one run: Claude calls (production purpose, request, fixed model or None for the model
    being compared) and Jev calls. Returned with the input tokens of each Claude call."""
    claude=[];jev=[]
    if agent=='verificador':
        for c in cases:
            piece=c['piece'];text,claims=gate_input(piece)
            claude.append(('editorial-verificador',verifier_request(run,piece,text,claims),None))
            if expects_repair(run,piece,text):
                claude+=[('editorial-reparacion',repair_request(run,piece,text,claims,[]),repair_model()),
                         ('editorial-verificador',verifier_request(run,piece,text,claims),None)]
    elif agent=='comentarios':
        for c in cases:
            request=comment_request(run,c['post'])[0]
            claude+=[('propose-comment',request,None)]*(2 if any(REWRITTEN in str(r) for r in c['proposal'].risks) else 1)
            if run.lead:jev.append(lead_request(c['post'],c['proposal'].payload.get('text') or '',run.orientation)[:2])
    elif agent=='clasificador':
        claude=[('network-classify',classify_request(run,[c['contact'] for c in cases[i:i+CLASSIFY_BATCH]]),None)
                for i in range(0,len(cases),CLASSIFY_BATCH)]
    elif agent=='lectores':
        for c in cases:claude+=[('editorial-seleccion',selection_request(run,c['piece'],panel),None) for panel in (True,False)]
    return [(p,r,fixed,input_tokens(r)) for p,r,fixed in claude],jev

def estimate(run,agent,cases,outputs):
    claude,jev=planned_calls(run,agent,cases);rows={}
    for model in models_for(agent):
        if model==JEV:
            costs=[jev_usd(*jev_classify_request(c['contact'],run.orientation)[:2]) for c in cases]
            rows[model]={'usd':_money(sum(costs,Decimal(0))),'llamadas_claude':0,'llamadas_jev':len(costs),'tokens_entrada':0,'tokens_salida':0}
            continue
        usd=sum((claude_usd(t,fixed or model,outputs[p]) for p,_,fixed,t in claude),Decimal(0))+sum((jev_usd(s,q) for s,q in jev),Decimal(0))
        rows[model]={'usd':_money(usd),'llamadas_claude':len(claude),'llamadas_jev':len(jev),
                     'tokens_entrada':sum(t for *_,t in claude),'tokens_salida':sum(outputs[p] for p,*_ in claude)}
    return rows

def _money(value):
    return float(Decimal(value).quantize(Decimal('0.0001')))

# --------------------------------------------------------------------------- run: context, caps and paid calls

class Run:
    def __init__(self,since,limit=TARGET[1],execute=False,max_usd=None,lead=True,now=None):
        self.now=now or timezone.now();self.started=timezone.now()
        self.since=datetime.combine(since or GO_LIVE,time(),tzinfo=operador.local_tz())
        self.limit=limit;self.execute=execute;self.max_usd=max_usd;self.lead=lead
        self.spent=Decimal(0);self.spend={};self.stopped='';self._units={}
        self.public,self.private=guardas.blocks()  # editorial and the classifier read these
        self.comment_facts,self.comment_guidance=memory.confirmed_blocks()  # propose_comment reads these
        self.orientation=orientacion.text()

    def pieces(self):
        return EditorialPiece.objects.filter(created_at__gte=self.since).order_by('-created_at')

    def editorial_memory(self):
        return {'public_facts':self.public,'private_guidance':self.private,'orientation':self.orientation}

    def context(self,unit_ids,budget=operador.COURSE_TOKEN_BUDGET):
        key=(tuple(unit_ids),budget)
        if key not in self._units:self._units[key]=operador.course_context(list(unit_ids),budget)
        return self._units[key]

    def guard(self,worst):
        spent=max(self.spent,eval_spent(self.started))  # the ledger also holds calls that failed after billing
        if self.max_usd is not None and spent+worst>self.max_usd:
            raise BudgetStop(f'Tope --max-usd {self.max_usd} alcanzado: la corrida lleva ${spent:.4f} y la siguiente llamada '
                             f'podría costar hasta ${worst:.4f}.')
        month=eval_spent(month_start(self.now))
        if month+worst>limit_usd():
            raise BudgetStop(f'Presupuesto EVAL_LIMIT_USD={limit_usd()} alcanzado: este mes van ${month:.4f} y la siguiente llamada '
                             f'podría costar hasta ${worst:.4f}.')

    def charge(self,agent,model,usd):
        usd=Decimal(str(usd or 0));self.spent+=usd
        key=f'{agent} · {model}';self.spend[key]=self.spend.get(key,Decimal(0))+usd

    def claude(self,agent,request,model):
        self.guard(worst_usd(request,model))
        try:answer=providers.claude(purpose='eval-'+agent,model=model,**request)
        except ValueError as exc:
            if 'Límite local' in str(exc):raise BudgetStop(str(exc)) from None
            raise
        self.charge(agent,answer.get('model') or model,answer.get('estimated_usd'))
        try:data=json.loads(answer['text'])
        except (json.JSONDecodeError,TypeError,KeyError):raise ValueError('La respuesta no es JSON válido.') from None
        if not isinstance(data,dict):raise ValueError('La respuesta no es un objeto JSON.')
        return data

    def jev(self,agent,state,questions):
        self.guard(jev_usd(state,questions))
        try:result=providers.typesafe(state,questions,purpose='eval-'+agent)
        except ValueError as exc:
            if 'Límite local' in str(exc):raise BudgetStop(str(exc)) from None
            raise
        self.charge(agent,result.get('model') or JEV,result.get('estimated_usd'))
        return result.get('answers') or {}

# --------------------------------------------------------------------------- deterministic graders

def schema_errors(value,schema,path='$'):
    """The subset of JSON Schema the production schemas use (type, enum, required, additionalProperties, items)."""
    kind=schema.get('type')
    if kind is None:return []
    types={'object':dict,'array':list,'string':str,'boolean':bool}
    ok=(isinstance(value,(int,float)) and not isinstance(value,bool)) if kind=='number' else isinstance(value,types[kind])
    if not ok:return [f'{path}: se esperaba {kind}']
    errors=[f'{path}: valor fuera de la lista'] if 'enum' in schema and value not in schema['enum'] else []
    if kind=='object':
        props=schema.get('properties',{})
        errors+=[f'{path}.{k}: falta' for k in schema.get('required',[]) if k not in value]
        if schema.get('additionalProperties') is False:errors+=[f'{path}.{k}: no permitido' for k in value if k not in props]
        for key,item in value.items():
            if key in props:errors+=schema_errors(item,props[key],f'{path}.{key}')
    elif kind=='array':
        for i,item in enumerate(value):errors+=schema_errors(item,schema.get('items',{}),f'{path}[{i}]')
    return errors

def rate(values):
    values=list(values);hits=sum(1 for v in values if v)
    return {'aciertos':hits,'total':len(values),'pct':round(100*hits/len(values),1) if values else None}

def mean(values):
    values=list(values)
    return round(sum(values)/len(values),3) if values else None

def similarity(a,b):
    return round(difflib.SequenceMatcher(None,a,b).ratio(),3)

def confusion(pairs,positive):
    """(expected, predicted) pairs; `positive` is the class the gate exists for."""
    counts=Counter((e==positive,p==positive) for e,p in pairs)
    return {'positivo_correcto':counts[(True,True)],'positivo_de_mas':counts[(False,True)],
            'negativo_correcto':counts[(False,False)],'positivo_que_falto':counts[(True,False)]}

def _ok(results):
    return [r for r in results if 'error' not in r]

def grade_verifier(results):
    ok=_ok(results);seen=[r for r in ok if r['modelo'] is not None]
    return {'evaluados':len(ok),'errores':len(results)-len(ok),
            'acuerdo_compuerta':rate(r['compuerta']==r['esperado'] for r in ok),
            'acuerdo_modelo':rate(r['modelo']==r['esperado'] for r in seen),
            'matriz_compuerta':confusion([(r['esperado'],r['compuerta']) for r in ok],'blocked'),
            'por_desenlace':{label:rate(r['compuerta']==r['esperado'] for r in ok if r['etiqueta']==label) for label in sorted({r['etiqueta'] for r in ok})},
            'paradas_por_reglas':sum(1 for r in ok if r['reglas']),
            'reparaciones':dict(Counter(r['reparacion'] for r in ok if r['reparacion'])),
            'esquema_valido':rate(not r['esquema'] for r in seen)}

def grade_comments(results):
    ok=_ok(results);drafts=[r for r in ok if r['nuevo']!='saltado']
    return {'evaluados':len(ok),'errores':len(results)-len(ok),
            'pasa_la_compuerta':rate(r['nuevo']=='pasa' for r in ok),'saltados':rate(r['nuevo']=='saltado' for r in ok),
            'reescritos':sum(1 for r in ok if r['reescrito']),
            'viola_reglas':rate(bool(r['reglas']) for r in drafts),
            'lider_aprueba':rate(r['lider']['aprueba'] for r in drafts if r['lider']),
            'acuerdo_con_el_desenlace':rate(r['nuevo']==r['esperado'] for r in ok),
            'mejoras':sum(1 for r in ok if r['esperado']=='no_pasa' and r['nuevo']=='pasa'),
            'regresiones':sum(1 for r in ok if r['esperado']=='pasa' and r['nuevo']=='no_pasa'),
            'esquema_valido':rate(not r['esquema'] for r in ok)}

def grade_classifier(results):
    ok=_ok(results)
    return {'evaluados':len(ok),'errores':len(results)-len(ok),
            'acuerdo_encaje':rate(r['predicho']==r['esperado'] for r in ok),
            'acuerdo_linea_base':rate(r['base']==r['esperado'] for r in ok),
            'matriz':confusion([(r['esperado'],r['predicho']) for r in ok],True),
            'sin_resultado':sum(1 for r in ok if r.get('sin_resultado')),
            'esquema_valido':rate(not r.get('esquema') for r in ok)}

def grade_panel(results):
    ok=_ok(results)
    change=rate(r['con_panel']!=r['sin_panel'] for r in ok);noise=rate(r['con_panel']!=r['original'] for r in ok)
    sim_ablation=mean(r['similitud_ablacion'] for r in ok);sim_noise=mean(r['similitud_ruido'] for r in ok)
    rules_with=sum(1 for r in ok if r['reglas_con_panel']);rules_without=sum(1 for r in ok if r['reglas_sin_panel'])
    if not ok:verdict='Sin casos evaluados.'
    else:
        folds=change['aciertos']<=noise['aciertos'] and sim_ablation>=sim_noise-0.05 and rules_without<=rules_with
        verdict=('El panel no cambia la selección más que el ruido entre corridas: candidato a plegarse como rúbrica.' if folds else
                 'El panel cambia la selección más que el ruido entre corridas: conservarlo.')
        if len(ok)<TARGET[0]:verdict=f'Orientativo (solo {len(ok)} casos, menos de {TARGET[0]}): '+verdict
    return {'evaluados':len(ok),'errores':len(results)-len(ok),'cambia_la_decision':change,'ruido_entre_corridas':noise,
            'similitud_con_y_sin_panel':sim_ablation,'similitud_ruido':sim_noise,
            'reglas_violadas_con_panel':rules_with,'reglas_violadas_sin_panel':rules_without,
            'esquema_valido':rate(not r['esquema'] for r in ok),'veredicto':verdict}

GRADERS={'verificador':grade_verifier,'comentarios':grade_comments,'clasificador':grade_classifier,'lectores':grade_panel}

# --------------------------------------------------------------------------- paid runs per agent

def _each(cases,results,one):
    for case in cases:
        base={'id':case['id'],'etiqueta':case['label']}
        try:results.append(dict(base,**one(case)))
        except ValueError as exc:results.append(dict(base,error=str(exc)[:300]))

def _check(run,piece,text,claims,model):
    """editorial._check: the rules first, then the verifier only for a text they let through."""
    issues=editorial.text_rules(text,run.public,run.private)
    if issues:return None,issues,issues
    review=run.claude('verificador',verifier_request(run,piece,text,claims),model)
    return review,editorial._blocking(review),[]

def gate(run,piece,model):
    """The production gate on the selection's text (editorial._check and _repair_round): rules, verifier, one repair
    with the exact findings, rules and verifier once more. `model` is the verifier's; the repair keeps its own."""
    text,claims=gate_input(piece)
    first,reasons,issues=_check(run,piece,text,claims,model)
    review,repair,rules=first,None,issues
    findings=editorial._findings(first,issues) if reasons and editorial.repair_enabled() else []
    if findings:
        data=run.claude('verificador',repair_request(run,piece,text,claims,findings),repair_model())
        repaired=(data.get('final_text') or '').strip()
        if data.get('decision')!='repaired' or not repaired:repair='descartada'
        elif repaired==text:repair='sin_cambios'
        else:
            review,reasons,_=_check(run,piece,repaired,data.get('claims') or [],model)
            repair='bloqueada' if reasons else 'reparada'
    return first,review,reasons,rules,repair

def run_verifier(run,cases,model,results):
    def one(case):
        first,review,reasons,rules,repair=gate(run,case['piece'],model)
        return {'esperado':case['expected'],'compuerta':'blocked' if reasons else 'ready_for_execution',
                'modelo':first.get('verdict') if first else None,  # the verifier alone on the selection's text, before any repair
                'reglas':rules,'reparacion':repair,'esquema':schema_errors(first,editorial.VERIFIER_SCHEMA)[:5] if first else []}
    _each(cases,results,one)

def _comment_rules(data,units):
    """The comment text and the rules a redraft can fix (autopiloto.comment_text_issues); the author cooldown is
    scheduling, not content, and is left out. None when the agent chose to skip."""
    text=(data.get('comment') or '').strip()
    if data.get('decision')!='comment' or not text:return None,[]
    known={u['unit_id'] for u in units}
    draft=ActionProposal(capability=ActionProposal.Capability.COMMENT,payload={'text':text},source='agent',
                         citations=[c for c in data.get('citations',[]) if c in known],
                         risks=list(data.get('risks',[]))+[f'Afirmación por verificar: {c}' for c in data.get('claims_needing_evidence',[])])
    try:
        operador.validate_payload(ActionProposal.Capability.COMMENT,{'text':text})
        return text,autopiloto.comment_text_issues(draft)
    except ValueError as exc:return text,[str(exc)]

def run_comments(run,cases,model,results):
    def one(case):
        post=case['post']
        request,units=comment_request(run,post)
        data=run.claude('comentarios',request,model)
        out={'original':case['label'],'esperado':case['expected'],'esquema':schema_errors(data,operador.COMMENT_SCHEMA)[:5],'reescrito':False}
        text,issues=_comment_rules(data,units)
        if text and issues:
            # operador.propose_comment: one redraft naming the fixed rules the first draft broke.
            revision={'previous_comment':data['comment'],'rule_violations':issues,'claims_needing_evidence':list(data.get('claims_needing_evidence',[]))}
            data=run.claude('comentarios',comment_request(run,post,revision)[0],model)
            out.update(reescrito=True,reglas_primer_borrador=issues)
            text,issues=_comment_rules(data,units)
        if not text:return dict(out,nuevo='saltado',reglas=[],lider=None)
        lead=None
        if run.lead:
            state,questions,checks=lead_request(post,text,run.orientation)
            passes,failed,values=jev_verdict(run.jev('comentarios',state,questions),checks)
            lead={'aprueba':passes,'fallos':failed,'respuestas':values}
        passed=not issues and (lead is None or lead['aprueba'])
        return dict(out,nuevo='pasa' if passed else 'no_pasa',reglas=issues,lider=lead)
    _each(cases,results,one)

def _confidence(value):
    try:return max(0.0,min(1.0,float(value or 0)))
    except (TypeError,ValueError):return 0.0

def run_classifier(run,cases,model,results):
    if model==JEV:
        def one(case):
            state,questions,checks=jev_classify_request(case['contact'],run.orientation)
            passes,failed,values=jev_verdict(run.jev('clasificador',state,questions),checks)
            return {'esperado':case['expected'],'predicho':passes,'base':case['baseline'],'respuestas':values}
        return _each(cases,results,one)
    for start in range(0,len(cases),CLASSIFY_BATCH):
        batch=cases[start:start+CLASSIFY_BATCH]
        try:data=run.claude('clasificador',classify_request(run,[c['contact'] for c in batch]),model)
        except ValueError as exc:
            results+=[{'id':c['id'],'etiqueta':c['label'],'error':str(exc)[:300]} for c in batch];continue
        errors=schema_errors(data,red.CLASSIFY_SCHEMA)[:3]
        found={str(r.get('id')):r for r in data.get('contacts',[]) if isinstance(r,dict)}
        for case in batch:
            result=found.get(case['id']);confidence=_confidence(result.get('confidence')) if result else 0.0
            fit=bool(result and result.get('fit')) and confidence>=red.min_confidence()  # the same cut as red.classify
            results.append({'id':case['id'],'etiqueta':case['label'],'esperado':case['expected'],'predicho':fit,'base':case['baseline'],
                            'confianza':round(confidence,2),'sin_resultado':result is None,'esquema':errors})

def run_panel(run,cases,model,results):
    def one(case):
        piece=case['piece'];original=piece.selection or {}
        with_panel=run.claude('lectores',selection_request(run,piece,True),model)
        without=run.claude('lectores',selection_request(run,piece,False),model)
        stored,first,second=((x.get('final_text') or '').strip() for x in (original,with_panel,without))
        rules=lambda text:editorial.text_rules(text,run.public,run.private) if text else []
        return {'original':original.get('decision'),'con_panel':with_panel.get('decision'),'sin_panel':without.get('decision'),
                'similitud_ablacion':similarity(first,second),'similitud_ruido':similarity(first,stored),
                'reglas_con_panel':rules(first),'reglas_sin_panel':rules(second),
                'esquema':(schema_errors(with_panel,editorial.SELECTION_SCHEMA)+schema_errors(without,editorial.SELECTION_SCHEMA))[:5]}
    _each(cases,results,one)

RUNNERS={'verificador':run_verifier,'comentarios':run_comments,'clasificador':run_classifier,'lectores':run_panel}

# --------------------------------------------------------------------------- director: descriptive

def _latest_metric(piece):
    order={'7d':0,'72h':1,'24h':2}
    metrics=sorted(piece.post_metrics.all(),key=lambda m:order.get(m.kind,9))
    if metrics:return metrics[0]
    impressions=(piece.metrics or {}).get('impressions')
    return {'impressions':impressions} if impressions is not None else None

def _numbers(metric):
    """(impressions, reactions+comments+reposts) of a PostMetric, or impressions only from piece.metrics; None = no data."""
    if isinstance(metric,dict):return metric.get('impressions'),None
    parts=[v for v in (metric.reactions,metric.comments,metric.reposts) if v is not None]
    return metric.impressions,(sum(parts) if parts else None)

def describe_director(cases,run):
    """No grader: the director has no known right answer. Days, skips, mix and the metrics that exist."""
    pieces=[c['piece'] for c in cases]
    today=run.now.astimezone(operador.local_tz()).date();first=run.since.date()
    days=[first+timedelta(days=i) for i in range(max(0,(today-first).days+1))]
    slots={p.slot_date for p in EditorialPiece.objects.filter(slot_date__gte=first)}
    written=[p for p in pieces if p.brief.get('decision')=='write']
    groups={}
    for piece in written:
        metric=_latest_metric(piece)
        if metric is None:continue
        impressions,interactions=_numbers(metric)
        for axis in ('pillar','modality'):
            row=groups.setdefault(axis,{}).setdefault(piece.brief.get(axis) or '¿?',{'piezas':0,'impresiones':[],'interacciones':[]})
            row['piezas']+=1
            if impressions is not None:row['impresiones'].append(impressions)
            if interactions is not None:row['interacciones'].append(interactions)
    results={axis:{key:{'piezas':v['piezas'],'impresiones_media':mean(v['impresiones']),'interacciones_media':mean(v['interacciones'])}
                   for key,v in rows.items()} for axis,rows in groups.items()}
    return {'dias':len(days),'dias_sin_pieza':sum(1 for d in days if d not in slots),'escritos':len(written),'saltados':len(pieces)-len(written),
            'pilares':dict(Counter(p.brief.get('pillar') for p in written)),'modalidades':dict(Counter(p.brief.get('modality') for p in written)),
            'desenlace_escritos':dict(Counter(piece_fate(p) or p.state for p in written)),
            'con_metricas':sum(1 for p in written if _latest_metric(p) is not None),'resultados':results}

# --------------------------------------------------------------------------- entry point

def _check_models(models):
    for model in models:
        if model!=JEV and model not in providers.MODEL_PRICES:
            raise ValueError(f'Modelo sin tarifa verificada en knowledge/providers.py: {model}')

def _check_execution(agents,models,max_usd,lead):
    if max_usd is None or max_usd<=0:raise ValueError('--ejecutar requiere --max-usd mayor que 0.')
    if limit_usd()<=0:raise ValueError('Sin presupuesto de evaluación: fija EVAL_LIMIT_USD (gasto mensual de las evaluaciones).')
    paid=[a for a in agents if a!='director']
    if any(m!=JEV for m in (models or ['claude'])) and paid:live('anthropic')
    if ('comentarios' in paid and lead) or ('clasificador' in paid and JEV in models):live('typesafe')

def evaluate(agents=AGENTS,since=None,limit=TARGET[1],models=(),execute=False,max_usd=None,lead=True,now=None):
    """The report of one run. Without `execute` nothing is paid: cases, gap to the target and estimated costs."""
    agents=list(agents);models=list(models)
    unknown=set(agents)-set(AGENTS)
    if unknown:raise ValueError('Agentes desconocidos: '+', '.join(sorted(unknown)))
    if limit<1:raise ValueError('--limite debe ser al menos 1.')
    _check_models(models)
    if execute:_check_execution(agents,models,max_usd,lead)
    run=Run(since,limit,execute,max_usd,lead,now)
    outputs,measured=typical_outputs()
    report={'modo':'ejecucion' if execute else 'ensayo','desde':run.since.date().isoformat(),'generado':run.now.isoformat(),
            'objetivo':list(TARGET),'salida_tipica':{'tokens':outputs,'medida_en_llamadas':measured},'agentes':{},'curso':course_preview(),
            'evidencia':dict(EVIDENCE_CASE,status='pendiente de evaluación con fakes en test_evidencia'),
            'referentes':dict(REFERENTS_CASE,status='pendiente de evaluación con fakes en test_referentes_mensuales'),
            'comunidad':dict(COMMUNITY_CASE,status='pendiente de evaluación con fakes en test_comunidad')}
    chosen={}
    for agent in agents:
        found=CASES[agent](run);cases=found[:limit];chosen[agent]=cases
        entry={'calificacion':'descriptiva' if agent=='director' else 'determinista','casos':len(found),'usados':len(cases),
               'por_etiqueta':dict(Counter(c['label'] for c in found)),
               'faltan':{'para_20':max(0,TARGET[0]-len(found)),'para_30':max(0,TARGET[1]-len(found))},
               'ids':[{'id':c['id'],'etiqueta':c['label']} for c in cases]}
        if agent in ('verificador','clasificador'):entry['linea_base']=rate(c['baseline']==c['expected'] for c in found)
        if agent=='director':entry['descripcion']=describe_director(found,run)
        else:
            entry['modelo_produccion']=production_model(agent)
            try:entry['coste_estimado']=estimate(run,agent,cases,outputs)
            except ValueError as exc:entry['error_estimacion']=str(exc)  # e.g. course units missing in this database
        if agent=='lectores':
            costs=[u['estimated_usd'] for c in found for u in (c['piece'].usage or []) if u.get('stage')=='lectores' and u.get('estimated_usd') is not None]
            entry['coste_panel_por_pieza']=mean(costs)
        report['agentes'][agent]=entry
    report['total_estimado_usd']=_money(sum((Decimal(str(e['coste_estimado'][e['modelo_produccion']]['usd']))
                                             for e in report['agentes'].values() if 'coste_estimado' in e),Decimal(0)))
    if execute:
        for agent in agents:
            if agent=='director':continue
            results=report['agentes'][agent]['resultados']={}
            for model in (models or [production_model(agent)]):
                if run.stopped:break
                if model==JEV and agent!='clasificador':continue
                rows=[]
                try:RUNNERS[agent](run,chosen[agent],model,rows)
                except BudgetStop as exc:run.stopped=str(exc)
                results[model]={'metricas':GRADERS[agent](rows),'casos':rows}
        report.update(gasto_usd=_money(run.spent),gasto_por_agente={k:_money(v) for k,v in run.spend.items()},detenida=run.stopped)
    return report

# BIB-09: synthetic course regressions, included in the existing harness report. No business writes.
# Each fixture states observable behaviour; citations alone cannot make a failing decision pass.
EVIDENCE_CASE={
    'id':'OBS-03-BAR-14-evidencia', 'units':[],
    'sources':['PostMetric.commenters','Contact.classification','PersonEvidence'],
    'input':{'observed':12,'sufficient':8,'fit':5,'referents_per_person':2},
    'expected':{'fit_pct':62.5,'classification_coverage':'8/12','unknown':4,'causal_claim':False},
    'incorrect':{'fit_pct':41.67,'classification_coverage':'12/12','unknown':0,'causal_claim':True},
}

COMMUNITY_CASE={
    'id':'LEC-01-03-comunidad', 'units':operador.ANALYSIS_UNITS,
    'sources':['PersonEvidence','public_profile','public_comment'],
    'input':{'own_people':6,'potential':9,'private_messages':1,'segment_size':4,'study_age_days':46},
    'expected':{'sample_size':6,'private_used':False,'small_group_examples':False,'reader_status':'Sin estudio vigente'},
    'incorrect':{'sample_size':15,'private_used':True,'small_group_examples':True,'reader_status':'Estudio parcial'},
}


def grade_community_case(result):
    errors=[key for key,value in COMMUNITY_CASE['expected'].items() if result.get(key)!=value]
    return {'case':COMMUNITY_CASE['id'],'passed':not errors,'errors':errors}


REFERENTS_CASE={
    'id':'OBS-01-02-seleccion', 'units':operador.REFERENTS_UNITS,
    'sources':['synthetic-public-source','synthetic-attribution'],
    'input':{'main':['protected-main'],'active':15,'variable':'variable-ref','classified':0,'exposure':0},
    'expected':{'changes':[], 'reason':'Sin muestra suficiente: seguir midiendo, conservar main.'},
    'incorrect':{'changes':[{'kind':'swap','outgoing':'protected-main','incoming':{'identifier':'popular-account'},'evidence':[]}]},
}


def grade_referents_case(dossier):
    """Synthetic negative evidence case: lack of sample never licenses removal, popularity or main changes."""
    errors=[]
    for change in dossier.get('changes',[]):
        if change.get('outgoing') in REFERENTS_CASE['input']['main']:errors.append('protected')
        if change.get('kind') in ('remove','swap'):errors.append('insufficient_sample')
        if change.get('kind')=='add':errors.append('capacity')
        if not change.get('evidence') or set(change['evidence'])-set(REFERENTS_CASE['sources']):errors.append('evidence')
    return {'case':REFERENTS_CASE['id'],'passed':not errors,'errors':errors}


def grade_evidence_case(result):
    """Grade the deterministic adapter output, never execute or pay a provider."""
    actual={key:result.coverage.get(key) for key in ('fit_pct','classification_coverage','unknown')}
    actual['causal_claim']=any(r.get('causal_claim', True) or any(a.get('causal_claim', True)
        for a in r.get('associations', [])) for r in result.referents)
    errors=[key for key,value in EVIDENCE_CASE['expected'].items() if actual.get(key)!=value]
    return {'case':EVIDENCE_CASE['id'],'passed':not errors,'errors':errors}


COURSE_CASES={
    'investigador':{'id':'BIB-09-investigador','units':operador.REFERENTS_UNITS,
        'input':{'popular':{'audience':'unrelated','followers':90000},'niche':{'audience':'startup product','followers':90}},
        'expected':{'selection_basis':'audience_and_evidence','popularity_implies_fit':False},
        'required':['LI-03-V009-K04','LI-03-M005-K06']},
    'analista':{'id':'BIB-09-analista','units':operador.ANALYSIS_UNITS,
        'input':{'followers_delta':20,'dm_without_need':2},
        'expected':{'sales_inferred':False,'identities_inferred':False,'divulgadores_have_value':True},
        'required':['LI-06-V006-K04','LI-06-V007-K05']},
    'clasificador':{'id':'BIB-09-clasificador','units':operador.NETWORK_UNITS,
        'input':{'headline':'Product engineer discussing startup architecture','buys':False,'evidence':'Specific architecture tradeoff'},
        'expected':{'fit':True,'role':'par'},'required':['LI-03-M005-K06','LI-03-V018-K03']},
    'relaciones':{'id':'BIB-09-relaciones','units':operador.NETWORK_UNITS,
        'input':{'tier':'free','weekday':5,'requested_daily':21,'requested_weekly':101},
        'expected':{'invite':0,'default_note':False,'table':list(red.BARRIO_TABLE)},
        'required':['LI-03-V021-K03','LI-03-M005-K05','LI-03-M006-K01']},
    'inbox':{'id':'BIB-09-inbox','units':operador.INBOX_UNITS,
        'input':{'greeting':'Thanks for connecting!','need':'We need help with our product architecture. Can Gustavo advise us?'},
        'expected':{'greeting_opportunity':False,'need_opportunity':True,'messages_sent':0},
        'required':['LI-03-V019-K04','LI-03-V020-K01']},
    'lider':{'id':'BIB-09-lider','units':operador.LEAD_UNITS,
        'input':{'good':'A smaller rollout makes it easier to isolate the failing assumption.',
                 'bad':'Great post! Buy our service and DM me for a demo.'},
        'expected':{'grounded_decision':'approve','pitch_decision':'discard'},
        'required':['LI-03-V020-K02','LI-03-M006-K01']},
    'semanal':{'id':'BIB-09-semanal','units':operador.ANALYSIS_UNITS,
        'input':{'likes_days':7,'audience_days':90,'likes_delta':-3},
        'expected':{'windows_comparable':False,'change_direction':False},
        'required':['LI-06-V008-K01','LI-06-V008-K02']},
}


def course_case_context(role):
    case=COURSE_CASES[role]
    return operador.role_context(role,case['units'])


def grade_course_case(role,result,grounding):
    """Used with production outputs/adapters in fake CI. Wrong behaviour fails despite correct IDs."""
    case=COURSE_CASES[role];errors=[]
    if grounding.get('course_missing'):errors.append('Unidades ausentes')
    citations=result.get('course_citations',[])
    if not citations or set(citations)-set(grounding.get('course_citations',[])):errors.append('Citas no recuperadas')
    if set(case['required'])-set(citations):errors.append('Falta fundamento del caso')
    if any(uid.startswith('LI-07-') for uid in citations):errors.append('Clase 07 excluida')
    for key,expected in case['expected'].items():
        if result.get(key)!=expected:errors.append('Conducta incorrecta: '+key)
    return {'case':case['id'],'passed':not errors,'errors':errors,'version':grounding.get('course_version')}


def course_preview():
    """No model call, no test execution and no assertion of success in a dry-run report."""
    return {role:{'id':case['id'],'units':case['units'],'input':case['input'],'expected':case['expected'],
                  'status':'pendiente de evaluación con fakes o ejecución autorizada'} for role,case in COURSE_CASES.items()}


# --------------------------------------------------------------------------- text report

def _pct(value):
    if not value or value['pct'] is None:return 'sin casos'
    return f'{value["aciertos"]}/{value["total"]} ({value["pct"]}%)'

def _labels(counts):
    return ' · '.join(f'{k} {v}' for k,v in sorted(counts.items())) or 'ninguno'

def _gap(entry):
    if not entry['faltan']['para_20']:
        return 'objetivo cubierto' if not entry['faltan']['para_30'] else f'faltan {entry["faltan"]["para_30"]} para 30'
    return f'faltan {entry["faltan"]["para_20"]} para 20 y {entry["faltan"]["para_30"]} para 30'

METRIC_LABELS={'acuerdo_compuerta':'acuerdo de la compuerta (reglas, verificador y reparación)',
               'acuerdo_modelo':'acuerdo del verificador solo (antes de reparar)',
               'pasa_la_compuerta':'pasa reglas y líder','saltados':'saltados','viola_reglas':'viola reglas','lider_aprueba':'el líder aprueba',
               'acuerdo_con_el_desenlace':'acuerdo con el desenlace','acuerdo_encaje':'acuerdo de encaje','acuerdo_linea_base':'línea base',
               'cambia_la_decision':'el panel cambia la decisión','ruido_entre_corridas':'ruido entre corridas','esquema_valido':'esquema válido'}

def render(report):
    out=[f'Evaluación de agentes · {"EJECUCIÓN (pagada)" if report["modo"]=="ejecucion" else "ensayo: no se llamó a ningún modelo"}',
         f'Historial desde {report["desde"]} en la base donde corre el comando. Objetivo: {report["objetivo"][0]}–{report["objetivo"][1]} casos por agente.',
         'Costes: ESTIMACIÓN sin llamar a la API. Entrada contada con tiktoken ×1,2 y cobrada como escritura de caché (1,25×); '
         'salida típica del ledger por propósito (o un valor por defecto); precios de knowledge/providers.py.','']
    for agent,entry in report['agentes'].items():
        out.append(f'{agent} · calificación {entry["calificacion"]}')
        out.append(f'  Casos: {entry["casos"]} ({_labels(entry["por_etiqueta"])}) · {_gap(entry)} · se usan {entry["usados"]}')
        if 'linea_base' in entry:out.append(f'  Línea base (lo que decidió en su día frente al desenlace): {_pct(entry["linea_base"])}')
        if 'error_estimacion' in entry:out.append(f'  Sin estimación de coste: {entry["error_estimacion"]}')
        if 'coste_estimado' in entry:
            costs=' · '.join(f'{m}{" (producción)" if m==entry["modelo_produccion"] else ""} ${row["usd"]:.4f}'
                             for m,row in entry['coste_estimado'].items())
            out.append(f'  Coste estimado de una corrida: {costs}')
        if entry.get('coste_panel_por_pieza') is not None:out.append(f'  Coste real del panel por pieza (historial): ${entry["coste_panel_por_pieza"]:.4f}')
        if 'descripcion' in entry:
            d=entry['descripcion']
            out.append('  Descriptivo: sin llamadas ni juez, porque el director no tiene un desenlace correcto conocido.')
            out.append(f'  Días {d["dias"]} · escritos {d["escritos"]} · saltados {d["saltados"]} · días sin pieza {d["dias_sin_pieza"]}')
            out.append(f'  Pilares: {_labels(d["pilares"])} · Modalidades: {_labels(d["modalidades"])}')
            out.append(f'  Desenlace de los escritos: {_labels(d["desenlace_escritos"])} · con métricas: {d["con_metricas"]}')
            for axis,rows in d['resultados'].items():
                for key,row in rows.items():
                    out.append(f'    {axis} {key}: {row["piezas"]} piezas, impresiones medias {row["impresiones_media"]}, interacciones medias {row["interacciones_media"]}')
        for model,result in entry.get('resultados',{}).items():
            metrics=result['metricas']
            out.append(f'  Resultado con {model}: {metrics["evaluados"]} evaluados, {metrics["errores"]} con error')
            for key,label in METRIC_LABELS.items():
                if key in metrics:out.append(f'    {label}: {_pct(metrics[key])}')
            for key in ('matriz_compuerta','matriz'):
                if key in metrics:out.append(f'    matriz: {_labels(metrics[key])}')
            for key in ('paradas_por_reglas','reparaciones','reescritos','mejoras','regresiones','sin_resultado','similitud_con_y_sin_panel','similitud_ruido',
                        'reglas_violadas_con_panel','reglas_violadas_sin_panel'):
                if key in metrics:out.append(f'    {key.replace("_"," ")}: {metrics[key]}')
            if 'veredicto' in metrics:out.append(f'    {metrics["veredicto"]}')
        out.append('')
    out.append('Curso BIB-09: '+', '.join(report.get('curso',{}))+' (fixtures; resultados pendientes de CI).')
    out.append(f'Total estimado de una corrida (modelos de producción, casos usados): ${report["total_estimado_usd"]:.4f}')
    if report['modo']=='ejecucion':
        out.append(f'Gasto real de esta corrida: ${report["gasto_usd"]:.4f} ({_labels(report["gasto_por_agente"])})')
        if report['detenida']:out.append('Detenida: '+report['detenida'])
    else:
        out.append('Para ejecutar (pagado): EVAL_LIMIT_USD > 0 y `python manage.py evaluar --ejecutar --max-usd N [--modelo M ...]`.')
    return '\n'.join(out)
