"""«Preguntas del equipo» and «Lo que el equipo sabe de ti» (oficina/PLAN-REDISENO.md, Tu turno).

An agent asks Gustavo only for what nobody else knows, and the question arrives complete: who asks, what it needs
and what for. The answer becomes confirmed user memory, the only source of facts the voice may tell in public
(`uso_publico`). «No quiero compartir esto» closes that key for good. Pending memory proposals arrive as
confirmation questions. Answering, correcting and withdrawing need a human session (permission confirm_memory)."""
import re
from django.db import IntegrityError, transaction
from django.utils import timezone
from knowledge import memory
from .exceptions import Conflict
from .jobs import audit
from .models import TeamQuestion
from .permissions import require

KEY=re.compile(r'[a-z0-9][a-z0-9_.\-]{1,119}')
MAX_ANSWER=2000
CONFIRM_QUESTION='¿Es correcto este dato sobre ti?'
CONFIRM_PURPOSE=('El equipo solo usa lo que confirmas. Si marcas que se puede usar en público, los posts y comentarios '
                 'pueden contarlo con tu voz; si no, solo orienta sus decisiones.')

def _normal_key(value):
    key=(value or '').strip().lower().replace(' ','_')
    if not KEY.fullmatch(key):raise ValueError('Clave de memoria inválida')
    return key

def known_keys():
    """Keys already confirmed (and not withdrawn): nothing to ask."""
    return {row['key'] for row in memory.latest(True) if not memory.retired(row['value'])}

def closed_keys():
    return set(TeamQuestion.objects.filter(state__in=['declined','open']).values_list('memory_key',flat=True))

def ask(agent,question,purpose,memory_key,suggested_public=False,origin=''):
    """An agent asks Gustavo for a fact. Idempotent per key; never re-asks a declined, open or known key."""
    from .alerts import notify
    try:key=_normal_key(memory_key)
    except ValueError:return None
    question=(question or '').strip();purpose=(purpose or '').strip()
    withdrawn={r['key'] for r in memory.latest(True) if memory.retired(r['value'])}
    if not question or key in closed_keys() or key in known_keys() or key in withdrawn:return None
    try:
        with transaction.atomic():
            item=TeamQuestion.objects.create(kind=TeamQuestion.Kind.ASK,agent=agent[:60],question=question[:1000],purpose=purpose[:1000],
                                             memory_key=key,suggested_public=bool(suggested_public),origin=origin[:120])
    except IntegrityError:return None
    audit(None,'team.question_asked',item.id,agent=agent,key=key)
    notify('Barrio AI: una pregunta para ti',question[:160],url='/tu-turno',tag='barrio-pregunta')
    return item

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

def answer(user,question_id,text='',public_use=None,accept=False):
    """Save Gustavo's answer as confirmed memory. A confirmation question may be accepted as proposed."""
    require(user,'confirm_memory')
    text=(text or '').strip()
    if len(text)>MAX_ANSWER:raise ValueError(f'La respuesta supera {MAX_ANSWER} caracteres')
    with transaction.atomic():
        item=TeamQuestion.objects.select_for_update().get(id=question_id)
        if item.state!=TeamQuestion.State.OPEN:raise Conflict('La pregunta ya no está abierta.')
        public=item.suggested_public if public_use is None else bool(public_use)
        if item.kind==TeamQuestion.Kind.CONFIRM and accept and not text:
            value=dict(item.proposed_value,uso_publico=public)
        elif text:value={'texto':text,'uso_publico':public}
        else:raise ValueError('Escribe la respuesta o confirma el dato propuesto')
        memory.set_fact(item.memory_key,value,f'user:{user.pk}',f'Respuesta de Gustavo en Tu turno a «{item.question[:200]}» ({item.id})')
        item.state=TeamQuestion.State.ANSWERED;item.answer=text or '(confirmado tal como estaba)';item.public_use=public
        item.answered_by=user;item.answered_at=timezone.now();item.save()
    audit(user,'team.question_answered',item.id,key=item.memory_key,public=public)
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
    out=[]
    for row in sorted(rows,key=lambda r:r['key']):
        value=row['value']
        text=value.get('texto') if isinstance(value,dict) and isinstance(value.get('texto'),str) else value
        out.append({'key':row['key'],'text':text,'public_use':memory.publishable(value),'version':row['version'],'updated_at':row['created_at']})
    return out

def correct(user,key,text,public_use):
    require(user,'confirm_memory')
    text=(text or '').strip()
    if not text or len(text)>MAX_ANSWER:raise ValueError(f'Escribe el dato corregido (máximo {MAX_ANSWER} caracteres)')
    key=_normal_key(key)
    if key not in known_keys():raise Conflict('Ese dato no está en la memoria confirmada.')
    memory.set_fact(key,{'texto':text,'uso_publico':bool(public_use)},f'user:{user.pk}','Corrección de Gustavo en Tu turno')
    audit(user,'memory.corrected',key,public=bool(public_use))

def retire(user,key,reason=''):
    """Withdraw a fact: a confirmed tombstone; the agents stop using it and its history stays."""
    require(user,'confirm_memory')
    key=_normal_key(key)
    if key not in known_keys():raise Conflict('Ese dato no está en la memoria confirmada.')
    memory.set_fact(key,{'retirado':True,'motivo':(reason or '').strip()[:500]},f'user:{user.pk}','Gustavo retiró el dato en Tu turno')
    audit(user,'memory.retired',key)
