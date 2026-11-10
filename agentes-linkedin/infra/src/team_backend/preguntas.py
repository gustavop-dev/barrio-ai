"""«Preguntas del equipo» and «Lo que el equipo sabe de ti» (oficina/PLAN-REDISENO.md and DISENO-VISTAS.md, Tu turno).

An agent asks Gustavo only for what nobody else knows, and the question arrives complete: who asks, what it needs,
what for, the kind of answer and, if it applies, until when it is useful. The answer becomes confirmed user memory,
the only source of facts the voice may tell in public (`uso_publico`). «Más tarde» postpones it 3 days and takes it
out of the counter; «No quiero compartir esto» closes the key for good; «Deshacer» restores the memory as it was
for a few minutes after answering. Pending memory proposals arrive as confirmation questions."""
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db import IntegrityError, transaction
from django.utils import timezone
from knowledge import memory
from .exceptions import Conflict
from .jobs import audit
from .models import TeamQuestion
from .permissions import require

KEY=re.compile(r'[a-z0-9][a-z0-9_.\-]{1,119}')
MAX_ANSWER=2000
POSTPONE=timedelta(days=3)
UNDO_WINDOW=timedelta(minutes=15)
CONFIRM_QUESTION='¿Es correcto este dato sobre ti?'
CONFIRM_PURPOSE=('El equipo solo usa lo que confirmas. Si marcas que se puede usar en público, los posts y comentarios '
                 'pueden contarlo con tu voz; si no, solo orienta sus decisiones.')
YES_NO={'si':'Sí','no':'No'}

def _normal_key(value):
    key=(value or '').strip().lower().replace(' ','_')
    if not KEY.fullmatch(key):raise ValueError('Clave de memoria inválida')
    return key

def known_keys():
    """Keys already confirmed (and not withdrawn): nothing to ask."""
    return {row['key'] for row in memory.latest(True) if not memory.retired(row['value'])}

def closed_keys():
    return set(TeamQuestion.objects.filter(state__in=['declined','open']).values_list('memory_key',flat=True))

def is_pending(item,now=None):
    """Counts in Tu turno: open, not postponed and, if it has a deadline, before it."""
    now=now or timezone.now()
    return (item.state==TeamQuestion.State.OPEN and not (item.postponed_until and item.postponed_until>now)
            and not (item.deadline and item.deadline<now))

def ask(agent,question,purpose,memory_key,suggested_public=False,origin='',answer_type='text',options=None,deadline=None):
    """An agent asks Gustavo for a fact. Idempotent per key; never re-asks a declined, open, withdrawn or known key."""
    try:key=_normal_key(memory_key)
    except ValueError:return None
    question=(question or '').strip();purpose=(purpose or '').strip()
    if answer_type not in TeamQuestion.AnswerType.values:answer_type='text'
    options=[str(o).strip()[:120] for o in (options or []) if str(o).strip()][:12]
    if answer_type=='choice' and len(options)<2:answer_type='text';options=[]
    withdrawn={r['key'] for r in memory.latest(True) if memory.retired(r['value'])}
    if not question or key in closed_keys() or key in known_keys() or key in withdrawn:return None
    try:
        with transaction.atomic():
            item=TeamQuestion.objects.create(kind=TeamQuestion.Kind.ASK,agent=agent[:60],question=question[:1000],purpose=purpose[:1000],
                                             memory_key=key,suggested_public=bool(suggested_public),origin=origin[:120],
                                             answer_type=answer_type,options=options,deadline=deadline)
    except IntegrityError:return None
    audit(None,'team.question_asked',item.id,agent=agent,key=key)
    from .notificaciones import avisar
    avisar('question',f'{agent_label(agent)} te pregunta',question[:200])
    return item


def withdraw_origin(origin,reason='Propuesta reemplazada',keys=None):
    """Retire pending requests, including postponed ones; preserve answers and history."""
    rows=TeamQuestion.objects.filter(origin=origin,state=TeamQuestion.State.OPEN)
    if keys is not None:rows=rows.filter(memory_key__in=keys)
    ids=list(rows.values_list('id',flat=True))
    count=rows.update(state=TeamQuestion.State.WITHDRAWN)
    for qid in ids:audit(None,'team.question_withdrawn',qid,reason=reason)
    return count


@transaction.atomic
def clean_profile_questions(owner):
    """Latest active proposal owns each section; exact keys are also unique per owner.

    Section provenance resolves legacy Spanish/English wording without guessing that
    two different facts are synonyms. Requests with unknown provenance remain intact.
    """
    from django.contrib.auth import get_user_model
    from .models import ProfileProposal
    get_user_model().objects.select_for_update().get(pk=owner.pk)
    proposals=list(ProfileProposal.objects.filter(owner=owner).order_by('-created_at','-id'))
    by_origin={f'perfil:{p.id}':p for p in proposals};latest={}
    for p in proposals:
        if p.state in ('superseded','cancelled'):continue
        for section in p.sections:
            if not section.get('superseded_by'):latest.setdefault(section['id'],p.id)
    seen=set();retired=0
    for question in TeamQuestion.objects.filter(agent='perfil',state='open',origin__in=by_origin).order_by('-created_at','-id'):
        proposal=by_origin[question.origin]
        sections=[s for s in proposal.sections if any(m['key']==question.memory_key for m in s.get('missing',[]))]
        stale=proposal.state in ('superseded','cancelled')
        if sections:stale=stale or not any(not s.get('superseded_by') and latest.get(s['id'])==proposal.id for s in sections)
        # Keys deduplicate even when a fact was requested in more than one section.
        key=question.memory_key
        if stale or key in seen:
            retired+=withdraw_origin(question.origin,reason='Perfil: sección reemplazada o pregunta duplicada',keys=[key])
        else:seen.add(key)
    return retired


@transaction.atomic
def ask_profile(proposal):
    """Serialize cleanup + asking by owner, before the global key constraint in ask()."""
    clean_profile_questions(proposal.owner)
    if proposal.state in ('superseded','cancelled'):return
    from .models import ProfileProposal
    newer=ProfileProposal.objects.filter(owner=proposal.owner,created_at__gt=proposal.created_at).exclude(state__in=['superseded','cancelled'])
    covered={s['id'] for p in newer for s in p.sections if not s.get('superseded_by')}
    for row in proposal.sections:
        if row.get('superseded_by') or row['id'] in covered:continue
        for missing in row.get('missing',[]):
            ask('perfil',missing['question'],f'{row["title"]}: {missing["purpose"]}',missing['key'],
                origin=f'perfil:{proposal.id}',suggested_public=True)

def agent_label(agent):
    return {'director_editorial':'Director editorial','posicionamiento':'Posicionamiento','perfil':'Perfil',
            'analista_barrio_resultados':'Analista del barrio','relaciones_comunidad':'Relaciones con la comunidad',
            'conversaciones_inbox':'Conversaciones e inbox'}.get(agent,agent.replace('_',' ').capitalize())

def sync_memory_proposals():
    """Every user fact whose latest version is still a proposal becomes one confirmation question."""
    closed=set(TeamQuestion.objects.filter(state__in=['open','declined']).values_list('memory_key',flat=True));created=0
    for row in memory.latest():
        if row['namespace']!='user' or row['status']!='proposed' or row['key'] in closed:continue
        value=row['value'] if isinstance(row['value'],dict) else {'texto':str(row['value'])}
        try:
            with transaction.atomic():
                TeamQuestion.objects.create(kind=TeamQuestion.Kind.CONFIRM,agent='posicionamiento',question=CONFIRM_QUESTION,
                    purpose=CONFIRM_PURPOSE,memory_key=row['key'],proposed_value=value,memory_id=row['id'],
                    suggested_public=memory.publishable(value),origin='memoria')
            created+=1
        except IntegrityError:continue
    return created

def _typed_text(item,text,value,free=False):
    """The memory text for each answer type. Every answer carries its question so the fact reads on its own
    («Se puede compartir» alone does not say what may be shared, nor that «búsquenla» is an order to the team).
    `free`: a spoken or written answer to a typed question (the capture button) is stored as free text."""
    kind=item.answer_type
    if kind=='text' or free:
        if not text:raise ValueError('Escribe la respuesta')
        return f'{item.question} {text}'
    if kind=='yes_no':
        if value not in YES_NO:raise ValueError('Responde sí o no')
        answer=YES_NO[value]+(f'. {text}' if text else '')
    elif kind=='choice':
        if value not in item.options:raise ValueError('Elige una de las opciones')
        answer=value+(f'. {text}' if text else '')
    elif kind=='number':
        try:answer=str(Decimal(str(value)).normalize())
        except (InvalidOperation,TypeError):raise ValueError('Escribe un número') from None
        answer+=f' ({text})' if text else ''
    else:
        try:answer=date.fromisoformat(str(value)).isoformat()
        except ValueError:raise ValueError('Escribe una fecha AAAA-MM-DD') from None
        answer+=f' ({text})' if text else ''
    return f'{item.question} {answer}'

def answer(user,question_id,text='',public_use=None,accept=False,value=None,free=False):
    """Save Gustavo's answer as confirmed memory. A confirmation question may be accepted as proposed."""
    require(user,'confirm_memory')
    text=(text or '').strip()
    if len(text)>MAX_ANSWER:raise ValueError(f'La respuesta supera {MAX_ANSWER} caracteres')
    with transaction.atomic():
        item=TeamQuestion.objects.select_for_update().get(id=question_id)
        if item.state!=TeamQuestion.State.OPEN:raise Conflict('La pregunta ya no está abierta.')
        public=item.suggested_public if public_use is None else bool(public_use)
        if item.kind==TeamQuestion.Kind.CONFIRM and accept and not text:
            stored=dict(item.proposed_value,uso_publico=public);shown='(confirmado tal como estaba)'
        elif item.kind==TeamQuestion.Kind.CONFIRM:
            if not text:raise ValueError('Escribe el dato corregido o confírmalo tal como está')
            stored={'texto':text,'uso_publico':public};shown=text
        else:
            stored={'texto':_typed_text(item,text,value,free),'uso_publico':public};shown=stored['texto']
        result=memory.set_fact(item.memory_key,stored,f'user:{user.pk}',f'Respuesta de Gustavo en Tu turno a «{item.question[:200]}» ({item.id})')
        item.state=TeamQuestion.State.ANSWERED;item.answer=shown;item.public_use=public;item.memory_version=result['version']
        item.answered_by=user;item.answered_at=timezone.now();item.save()
    audit(user,'team.question_answered',item.id,key=item.memory_key,public=public)
    if item.agent=='perfil':
        from .perfil import fact_answered
        transaction.on_commit(lambda:fact_answered(item.memory_key))
    return item

def undo(user,question_id):
    """«Deshacer» right after answering: the memory goes back to its previous confirmed state and the question reopens."""
    require(user,'confirm_memory')
    with transaction.atomic():
        item=TeamQuestion.objects.select_for_update().get(id=question_id)
        if item.state!=TeamQuestion.State.ANSWERED or item.answered_by_id!=user.pk or not item.answered_at \
           or item.answered_at<timezone.now()-UNDO_WINDOW:
            raise Conflict('Ya no se puede deshacer esta respuesta; corrige el dato en «Lo que el equipo sabe de ti».')
        previous=[r for r in memory.confirmed_history('user',item.memory_key) if item.memory_version and r['version']<item.memory_version]
        restored=previous[0]['value'] if previous else {'retirado':True,'motivo':'Respuesta deshecha'}
        memory.set_fact(item.memory_key,restored,f'user:{user.pk}',f'Gustavo deshizo su respuesta ({item.id})')
        item.state=TeamQuestion.State.OPEN;item.answer='';item.public_use=None;item.memory_version=None
        item.answered_by=None;item.answered_at=None;item.save()
    audit(user,'team.question_undone',item.id,key=item.memory_key)
    if item.agent=='perfil':
        clean_profile_questions(user)
        item.refresh_from_db()
    return item

def postpone(user,question_id):
    """«Más tarde»: out of the counter for 3 days."""
    require(user,'confirm_memory')
    item=TeamQuestion.objects.get(id=question_id)
    if item.state!=TeamQuestion.State.OPEN:raise Conflict('La pregunta ya no está abierta.')
    item.postponed_until=timezone.now()+POSTPONE;item.save(update_fields=['postponed_until'])
    audit(user,'team.question_postponed',item.id)
    return item

def decline(user,question_id):
    """«No quiero compartir esto»: the key is never asked again."""
    require(user,'confirm_memory')
    with transaction.atomic():
        item=TeamQuestion.objects.select_for_update().get(id=question_id)
        if item.state!=TeamQuestion.State.OPEN:raise Conflict('La pregunta ya no está abierta.')
        item.state=TeamQuestion.State.DECLINED;item.answered_by=user;item.answered_at=timezone.now();item.save()
    audit(user,'team.question_declined',item.id,key=item.memory_key)
    return item

# --------------------------------------------------------------------------- what the team knows about Gustavo

def facts():
    rows=[r for r in memory.latest(True) if not memory.retired(r['value'])]
    asked={}
    for q in TeamQuestion.objects.filter(state='answered').order_by('answered_at'):asked[q.memory_key]=q
    out=[]
    for row in sorted(rows,key=lambda r:r['key']):
        value=row['value'];key=row['key']
        text=value.get('texto') if isinstance(value,dict) and isinstance(value.get('texto'),str) else value
        q=asked.get(key)
        if q:origin={'kind':'question','agent':q.agent,'agent_label':agent_label(q.agent),'question':q.question}
        elif key.startswith('nota.'):origin={'kind':'manual'}
        else:origin={'kind':'memoria'}
        versions=len([v for v in memory.confirmed_history('user',key) if not memory.retired(v['value'])])
        out.append({'key':key,'topic':(value.get('tema') if isinstance(value,dict) else None) or (q.question if q else key),
                    'text':text,'public_use':memory.publishable(value),'version':row['version'],'edits':max(1,versions),
                    'origin':origin,'updated_at':row['created_at']})
    return out

def add_fact(user,text,public_use,topic=''):
    """«Añadir algo que quieras que sepan»: Gustavo writes it, so it is confirmed directly."""
    require(user,'confirm_memory')
    text=(text or '').strip();topic=(topic or '').strip()[:200]
    if not text or len(text)>MAX_ANSWER:raise ValueError(f'Escribe el dato (máximo {MAX_ANSWER} caracteres)')
    key=f'nota.{uuid.uuid4().hex[:10]}'
    value={'texto':text,'uso_publico':bool(public_use)}
    if topic:value['tema']=topic
    memory.set_fact(key,value,f'user:{user.pk}','Gustavo lo añadió en Tu turno')
    audit(user,'memory.added',key,public=bool(public_use))
    return key

def correct(user,key,text,public_use):
    require(user,'confirm_memory')
    text=(text or '').strip()
    if not text or len(text)>MAX_ANSWER:raise ValueError(f'Escribe el dato corregido (máximo {MAX_ANSWER} caracteres)')
    key=_normal_key(key)
    if key not in known_keys():raise Conflict('Ese dato no está en la memoria confirmada.')
    current=next(r['value'] for r in memory.latest(True) if r['key']==key)
    value={'texto':text,'uso_publico':bool(public_use)}
    if isinstance(current,dict) and current.get('tema'):value['tema']=current['tema']
    memory.set_fact(key,value,f'user:{user.pk}','Corrección de Gustavo en Tu turno')
    audit(user,'memory.corrected',key,public=bool(public_use))

def retire(user,key,reason=''):
    """Withdraw a fact: a confirmed tombstone; the agents stop using it and its history stays."""
    require(user,'confirm_memory')
    key=_normal_key(key)
    if key not in known_keys():raise Conflict('Ese dato no está en la memoria confirmada.')
    memory.set_fact(key,{'retirado':True,'motivo':(reason or '').strip()[:500]},f'user:{user.pk}','Gustavo retiró el dato en Tu turno')
    audit(user,'memory.retired',key)

def recently_resolved(days=7):
    since=timezone.now()-timedelta(days=days)
    labels={'answered':'Respondida','declined':'No quisiste compartirla'}
    return [{'kind':'question','id':str(q.id),'title':q.question,'agent':q.agent,'at':q.answered_at,'how':labels[q.state]}
            for q in TeamQuestion.objects.filter(state__in=['answered','declined'],answered_at__gte=since).order_by('-answered_at')]
