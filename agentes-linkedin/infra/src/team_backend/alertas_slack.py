"""Avisos a Slack para Gustavo (16/11/2026: «prefiero Slack a la app»).

Channel: Slack incoming webhooks. SLACK_WEBHOOK_URL takes the alerts; SLACK_WEBHOOK_RESUMEN the summaries (empty: they
go to the alerts one). Both empty: everything is off, without errors. Each alert has a key and goes out once per local
day, or once ever for what happens once (a comment, a pause), recorded as AuditEvent `slack.alert` (the key as target,
the text in metadata, never the URL). A Slack failure never stops the work that raised the alert: it is logged and
audited (`slack.alert_failed`) and the work goes on; the alert is not sent again that day.

Most alerts are watchers (@vigilante): functions that READ the state (caps, pauses, comments, reads…) and return what to
send. vigilar() runs them all from the autopilot tick, at most every WATCH_EVERY; adding one is writing one function.
Only what no table records is sent where it happens: a paid provider refusing its credentials
(knowledge.providers.CREDENTIAL_LISTENERS, registered in apps.ready). The push alerts of alerts.py and notificaciones.py
are another channel and stay as they are.

Limit: the watchers run inside the autopilot. If the autopilot itself stops, nothing here notices; that needs a watcher
outside it (the container healthcheck already sees the heartbeat file; an external uptime check would have to alert)."""
import logging
import math
import os
import re
from datetime import datetime, timedelta
from typing import Callable, NamedTuple, Union
import httpx
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent

logger=logging.getLogger('team_backend.alertas_slack')
ACTION='slack.alert'
FAILED='slack.alert_failed'
TIMEOUT=httpx.Timeout(5.0,connect=3.0)
TRANSPORT=None  # tests inject an httpx.MockTransport; nothing in the tests reaches Slack
WATCH_EVERY=timedelta(minutes=5)

class Aviso(NamedTuple):
    key:str  # deduplication key (at most 120 characters: AuditEvent.target)
    text:Union[str,Callable[[],str]]  # a callable is only built when the alert will go out
    once:str='day'  # 'day': once per local day; 'ever': once
    channel:str='alertas'  # 'alertas' | 'resumen'

WATCHERS=[]

def vigilante(function):
    """Register a watcher: function(now) -> iterable of Aviso. A watcher only reads; vigilar sends."""
    WATCHERS.append(function)
    return function

# --------------------------------------------------------------------------- settings

def setting(name,default):
    return os.environ.get(name,default)

def webhook(channel='alertas'):
    alerts=setting('SLACK_WEBHOOK_URL','').strip()
    if channel=='resumen':return setting('SLACK_WEBHOOK_RESUMEN','').strip() or alerts
    return alerts

def enabled():
    return bool(webhook('alertas') or webhook('resumen'))

def _number(name,default,low,high):
    try:value=float(setting(name,str(default)))
    except ValueError:return default
    return min(max(value,low),high) if math.isfinite(value) else default

def cap_threshold():
    """ALERT_CAP_THRESHOLD (0.8): the share of a daily read cap that warns before it runs out."""
    return _number('ALERT_CAP_THRESHOLD',0.8,0.1,0.99)

def reply_pending_hours():
    """ALERT_REPLY_PENDING_HOURS (4): window hours a comment that deserves an answer may wait."""
    return timedelta(hours=_number('ALERT_REPLY_PENDING_HOURS',4,0.5,72))

def reads_gap_hours():
    """ALERT_READS_GAP_HOURS (3): window hours without reading the comments of his posts while one was due."""
    return timedelta(hours=_number('ALERT_READS_GAP_HOURS',3,1,24))

def summary_enabled():
    return setting('SLACK_DAILY_SUMMARY','true').strip().lower()=='true'

# --------------------------------------------------------------------------- sending

def _local(moment):
    from .operador import local_tz
    return moment.astimezone(local_tz())

def hhmm(moment):
    return f'{_local(moment):%H:%M}'

def since_text(moment,now):
    """«las 14:05», or «el 15/11 a las 20:40» when it was another day."""
    local,today=_local(moment),_local(now).date()
    return f'las {local:%H:%M}' if local.date()==today else f'el {local:%d/%m} a las {local:%H:%M}'

def duration(delta):
    minutes=max(0,int(delta.total_seconds()//60));hours,minutes=divmod(minutes,60)
    return f'{hours} h {minutes:02d} min' if hours else f'{minutes} min'

def send(key,text,now=None,once='day',channel='alertas',immediate=False):
    """Send `text` for `key` once per local day (once='ever': once). True when it went (or will go, after the current
    transaction commits; immediate=True posts now, for an alert raised inside work that may roll back); False when Slack
    is off or the key already went. Never raises."""
    url=webhook(channel)
    if not url:return False
    key=str(key)[:120];now=now or timezone.now()
    try:
        with transaction.atomic():  # a savepoint: a failure here never spoils the caller's transaction
            sent=AuditEvent.objects.filter(action=ACTION,target=key)
            if once=='day':
                from .operador import period_starts
                day,_=period_starts(now);sent=sent.filter(created_at__gte=day,created_at__lt=day+timedelta(days=1))
            if sent.exists():return False
            text=text() if callable(text) else text
            event=AuditEvent.objects.create(action=ACTION,target=key,created_at=now,metadata={'text':text[:3000],'channel':channel})
    except Exception as exc:
        logger.warning('slack_alert_not_recorded key=%s error=%s',key,type(exc).__name__)
        return False
    if immediate:_post(event.pk,key,url,text)
    else:transaction.on_commit(lambda:_post(event.pk,key,url,text))
    return True

def _post(event_id,key,url,text):
    """One POST {"text": ...}. Failures are logged and audited without the URL; nothing is raised."""
    try:
        with httpx.Client(transport=TRANSPORT,timeout=TIMEOUT) as client:
            response=client.post(url,json={'text':text})
        if response.status_code<400:return True
        failure={'http_status':response.status_code}
    except Exception as exc:
        failure={'error_type':type(exc).__name__}
    logger.warning('slack_alert_failed key=%s %s',key,failure)
    try:AuditEvent.objects.create(action=FAILED,target=key,metadata=dict(failure,alert=event_id))
    except Exception:pass
    return False

_watched_at=None  # in-process throttle; every alert is deduplicated durably by its key

def vigilar(now=None,force=False):
    """Run every watcher and send what they return. Called by the autopilot tick; at most every WATCH_EVERY."""
    global _watched_at
    now=now or timezone.now()
    if not enabled():return 0
    if not force and _watched_at is not None and abs(now-_watched_at)<WATCH_EVERY:return 0
    _watched_at=now;sent=0
    for watcher in WATCHERS:
        try:
            for alert in watcher(now) or ():
                sent+=int(send(alert.key,alert.text,now,alert.once,alert.channel))
        except Exception as exc:  # one broken watcher never silences the others nor stops the tick
            logger.warning('slack_watcher_failed watcher=%s error=%s',watcher.__name__,type(exc).__name__)
    return sent

# --------------------------------------------------------------------------- windows

def _hours_window():
    """(start, end) in minutes of the hours that count: READ_WINDOW, or OPERATOR_WINDOW without it."""
    from . import operador
    window=operador.read_window()
    if window:return window
    start,_,end=setting('OPERATOR_WINDOW','07:00-21:00').partition('-')
    return operador._minutes(start),operador._minutes(end)

def window_time(since,now,window=None):
    """How much of [since, now] falls inside the daily window (READ_WINDOW, or OPERATOR_WINDOW without it)."""
    if since>=now:return timedelta(0)
    start,end=window or _hours_window();total=timedelta(0)
    day=_local(since).replace(hour=0,minute=0,second=0,microsecond=0)
    while day<now:
        low,high=max(since,day+timedelta(minutes=start)),min(now,day+timedelta(minutes=end))
        if high>low:total+=high-low
        day=(day+timedelta(days=1)).replace(hour=0,minute=0)
    return total

def close_of_day(now):
    """The day's summary hour: the close of READ_WINDOW (or of OPERATOR_WINDOW), at the latest 23:59."""
    from .operador import period_starts
    day,_=period_starts(now)
    return day+timedelta(minutes=min(_hours_window()[1],23*60+59))

# --------------------------------------------------------------------------- daily caps

# scope: (variable that raises it, {kind: (what it reads, what stops while it is spent)})
READS={
    'respuestas':('REPLIES_READ_CAPS',{
        'comments':('los comentarios de tus posts','no se leen comentarios nuevos en tus posts y nadie los responde'),
        'threads':('los hilos de tus posts','no se leen las respuestas nuevas dentro de los hilos de tus posts'),
        'posts':('la lista de tus posts','no se encuentra un post tuyo nuevo para leer sus comentarios'),
        'people_posts':('los posts de quien te comenta','las respuestas se redactan sin los posts recientes de la persona')}),
    'red':('NETWORK_READ_CAPS',{
        'comments':('los comentarios en posts de referentes','no se descubren personas nuevas en esos comentarios'),
        'search':('las búsquedas de personas','no se descubren personas por búsqueda'),
        'profile':('los perfiles de la red','las personas nuevas esperan para clasificarse'),
        'sync':('la sincronización de invitaciones','no se concilian las invitaciones enviadas y recibidas')}),
    'perfiles':('OPERATOR_PROFILE_READ_DAILY_LIMIT',{
        'profile':('los perfiles (tope compartido)','seguir, invitar y aceptar esperan: cada una lee el perfil antes de escribir')}),
    'metricas':('METRICS_READ_CAPS',{kind:(f'las métricas ({kind})','las métricas de tus posts y de la audiencia quedan pendientes')
                                     for kind in ('posts','post','comments','profile','views')}),
    'desenlaces':('OUTCOMES_READ_CAPS',{kind:(f'los desenlaces ({kind})','los desenlaces de tus comentarios y conexiones quedan pendientes')
                                        for kind in ('comments','threads')}),
    'bandeja':('INBOX_READ_CAPS',{
        'chats':('la lista de chats de la bandeja','no se leen los mensajes nuevos de la bandeja'),
        'messages':('los mensajes de la bandeja','no se leen los hilos con mensajes nuevos')}),
}

def _reader():
    from .models import ConnectorAccount
    return ConnectorAccount.objects.filter(provider__in=['fake','directo']).order_by('created_at').first()

def profile_cap():
    return max(0,min(100,int(setting('OPERATOR_PROFILE_READ_DAILY_LIMIT','80'))))

def profile_reads_today(now):
    """The shared profile reads of the day as operador.reserve_profile_read counts them (read only)."""
    from .operador import period_starts
    day,_=period_starts(now);period={'created_at__gte':day,'created_at__lt':day+timedelta(days=1)}
    baseline=AuditEvent.objects.filter(action='operator.profile_baseline',target='member',
                                       metadata__day=day.date().isoformat()).order_by('created_at','id').first()
    return int((baseline.metadata or {}).get('used',0) if baseline else 0)+AuditEvent.objects.filter(action='operator.profile_read',**period).count()

def read_caps(account,now):
    """[(scope, kind, used, cap)] of every daily read cap, for the account that reads LinkedIn."""
    from . import conversaciones, desenlaces_captura, metricas, red, respuestas
    rows=[]
    for scope,module in (('respuestas',respuestas),('red',red),('metricas',metricas),('desenlaces',desenlaces_captura),
                         ('bandeja',conversaciones)):
        for kind,cap in module.read_caps().items():rows.append((scope,kind,module.reads_today(account,kind,now),cap))
    rows.append(('perfiles','profile',profile_reads_today(now),profile_cap()))
    return rows

def _knob(scope,kind):
    variable=READS.get(scope,('',{}))[0]
    if scope=='perfiles':return f'{variable} (hasta 100)'
    return f'{variable}={kind}=N' if variable else 'su variable de topes'

def _what(scope,kind):
    return READS.get(scope,('',{}))[1].get(kind,(f'{scope}.{kind}','esas lecturas esperan'))

@vigilante
def cupos_de_lectura(now):
    """A daily read cap at ALERT_CAP_THRESHOLD and spent: once a day each."""
    account=_reader()
    if account is None:return []
    threshold=cap_threshold();pct=round(threshold*100);alerts=[]
    for scope,kind,used,cap in read_caps(account,now):
        if cap<=0:continue
        label,stops=_what(scope,kind)
        if used>=cap:
            alerts.append(Aviso(f'cupo:{scope}.{kind}:agotado',
                f'Barrio · Cupo de lecturas agotado: {label} ({scope}.{kind}) llegó a {used}/{cap} a las {hhmm(now)}. '
                f'Hasta mañana {stops}. Si hace falta más, súbelo con {_knob(scope,kind)}.'))
        elif used>=math.ceil(cap*threshold):
            alerts.append(Aviso(f'cupo:{scope}.{kind}:{pct}',
                f'Barrio · Cupo de lecturas al {pct} %: {label} ({scope}.{kind}) va en {used}/{cap} a las {hhmm(now)}. '
                f'Si se agota, hasta mañana {stops}. Se sube con {_knob(scope,kind)}.'))
    return alerts

def write_caps(now):
    """[(capability, used, daily)] of the daily write caps that are not zero today (operador.limits, the ramp)."""
    from . import operador
    from .red import ramp_limits
    day,_=operador.period_starts(now);rows=[]
    for capability,(daily,_) in operador.limits(now).items():
        if capability=='RED-02':daily=min(daily,ramp_limits(None,now)[0])
        if daily<=0:continue
        done=operador.writes(None,capability).filter(started_at__gte=day)
        if capability=='CONT-09':done=done.exclude(proposal__piece__second_of_day=True)
        rows.append((capability,done.count(),daily))
    return rows

def capability_label(capability):
    from .models import ActionProposal
    return ActionProposal.Capability(capability).label if capability in ActionProposal.Capability.values else capability

@vigilante
def cupos_de_escritura(now):
    """A daily write cap spent: once a day each. Not CONT-09: one post a day is the plan, and filling it is the good news."""
    return [Aviso(f'cupo:escritura.{capability}:agotado',
                  f'Barrio · Cupo diario de escrituras agotado: {capability_label(capability)} ({capability}) llegó a '
                  f'{used}/{daily} a las {hhmm(now)}. Lo aprobado espera a mañana. Se sube con OPERATOR_DAILY_LIMITS={capability}=N.')
            for capability,used,daily in write_caps(now) if used>=daily and capability!='CONT-09']

# --------------------------------------------------------------------------- pauses

SESSION=re.compile(r'sesi[oó]n|login',re.I)

@vigilante
def cuenta_en_pausa(now):
    """A paused account: once per pause (the first pause after its last resume)."""
    from .models import ConnectorAccount
    alerts=[]
    for account in ConnectorAccount.objects.filter(paused=True):
        events=AuditEvent.objects.filter(target=str(account.id))
        resumed=events.filter(action='operator.account_resumed').order_by('-created_at').values_list('created_at',flat=True).first()
        paused=events.filter(action='operator.account_paused')
        if resumed:paused=paused.filter(created_at__gt=resumed)
        first=paused.order_by('created_at','id').first()
        reason=(account.paused_reason or 'sin motivo registrado').strip()
        title='Sesión de LinkedIn cerrada' if SESSION.search(reason) else 'Cuenta de LinkedIn en pausa'
        since=f' desde {since_text(first.created_at,now)}' if first else ''
        alerts.append(Aviso(f'pausa:cuenta:{account.id}:{first.pk if first else "sin-registro"}',
            f'Barrio · {title}: «{account.label}» está en pausa{since}. Motivo: {reason[:500]} Mientras siga en pausa no se lee '
            'ni se escribe con ella; reanúdala desde la app cuando esté resuelto.',once='ever'))
    return alerts

@vigilante
def rampa_en_pausa(now):
    """The invitation ramp paused (low acceptance or a provider limit): once per pause."""
    from .red import ramp_state
    state=ramp_state(now);until=state.get('pause_until')
    if not until or datetime.fromisoformat(until)<=now:return []
    return [Aviso(f'pausa:rampa:{until}',
                  f'Barrio · Invitaciones en pausa hasta {since_text(datetime.fromisoformat(until),now)}. Hasta entonces no se '
                  'envía ninguna invitación; seguir y aceptar siguen. Revisa en Personas por qué (aceptación baja o un límite de LinkedIn).',
                  once='ever')]

# --------------------------------------------------------------------------- paid providers (sent where it happens)

PROVIDERS={'openai':('OpenAI','OPENAI_API_KEY','fallan los embeddings de la búsqueda y el respaldo de Claude'),
           'anthropic':('Anthropic (Claude)','ANTHROPIC_API_KEY','los agentes no redactan con Claude (con LLM_FALLBACK=openai responde OpenAI)'),
           'typesafe':('TypeSafe (Jev, el líder)','TYPESAFE_API_KEY','el líder no revisa y lo que necesita su revisión queda pendiente')}

def provider_refused(provider,status):
    """knowledge.providers listener: a paid provider refused its credentials (HTTP 401/403). Once a day per provider."""
    name,variable,stops=PROVIDERS.get(provider,(provider,'su clave','fallan sus llamadas'))
    now=timezone.now()
    send(f'proveedor:{provider}:credenciales',
         f'Barrio · {name} rechazó la credencial (HTTP {status}) a las {hhmm(now)}. Mientras no se renueve {variable} en el '
         f'.env del servidor, {stops}.',now,immediate=True)

# --------------------------------------------------------------------------- the comments on his own posts

def _stuck(row):
    """Where a comment that deserves an answer is held, or None when it was answered or decided."""
    from .models import ActionProposal, PostComment
    from . import respuestas
    decision=row.decision or {}
    if row.state==PostComment.State.ASKED:return 'espera a que respondas la pregunta del equipo en Tu turno'
    proposal=row.proposals.filter(capability=ActionProposal.Capability.REPLY).order_by('-created_at').first()
    if proposal is None:
        if 'turn' not in decision:return 'leído, sin decidir todavía qué hacer'
        attempts=int(decision.get('attempts',0))
        if attempts>=respuestas.MAX_DRAFTS:return f'el borrador falló {attempts} veces; no se reintenta'
        return 'sin borrador todavía (espera su turno de redacción)'
    state=proposal.state
    if state in ('confirmed','rejected'):return None  # answered, or Gustavo vetoed it
    review=proposal.review or {}
    return {'proposed':'el borrador espera la revisión del líder',
            'discarded':'descartado por el líder' if review.get('decision')=='discard' else 'descartado por las reglas fijas',
            'approved':'aprobado, sin publicar todavía (espera turno de escritura)',
            'executing':'publicándose ahora','sent':'enviado, sin confirmar en LinkedIn',
            'uncertain':'resultado incierto: resuélvelo en la Bandeja','expired':'caducó sin publicar',
            'failed':'no salió al publicar','superseded':'reemplazado por otra versión'}.get(state,state)

def _words(text,count=8):
    words=' '.join((text or '').split()).split(' ')
    return ' '.join(words[:count])+('…' if len(words)>count else '')

@vigilante
def comentario_sin_responder(now):
    """A comment on his post that deserves an answer (not a short congratulation, spam or a thread already answered),
    waiting more than ALERT_REPLY_PENDING_HOURS of window hours without a published reply or a decision not to answer:
    once per comment."""
    from .models import PostComment
    from . import respuestas
    limit=reply_pending_hours();alerts=[]
    rows=(PostComment.objects.select_related('piece').filter(own=False,state__in=[PostComment.State.NEW,PostComment.State.ASKED,
          PostComment.State.REPLY],commented_at__gte=now-respuestas.window()).order_by('commented_at'))
    for row in rows:
        if window_time(row.commented_at,now)<limit:continue
        # Still unjudged: a short congratulation only gets a reaction, an answered thread is closed (respuestas.triage).
        if row.state==PostComment.State.NEW and 'turn' not in (row.decision or {}) and (
                not respuestas.plain(row.text) or respuestas.congratulation(row.text) or respuestas.closed_reason(row,now)):continue
        stage=_stuck(row)
        if stage is None:continue
        late=row.observed_at-row.commented_at if row.observed_at and row.commented_at else timedelta(0)
        read=f' Se leyó {duration(late)} después de escrito.' if late>timedelta(hours=1) else ''
        post=_words(row.piece.final_text)
        alerts.append(Aviso(f'respuesta:pendiente:{row.id}',
            f'Barrio · Comentario sin responder: {row.author_name or "alguien"} comentó hace {duration(now-row.commented_at)} '
            f'en tu post «{post}»: «{_words(row.text,14)}». Atascado en: {stage}.{read}',once='ever'))
    return alerts

def _why_not_reading(reader,now):
    from . import operador, respuestas
    from .models import Job
    if operador.globally_paused():return 'la máquina está detenida (OPERATOR_PAUSED o el interruptor de la oficina)'
    if not respuestas.enabled():return 'las respuestas están apagadas (REPLIES_ENABLED=false u OPERATOR_AUTONOMY con INT-04=off)'
    if reader is None:return 'no hay una cuenta de LinkedIn directo que lea tus posts'
    if reader.paused:return f'la cuenta está en pausa ({(reader.paused_reason or "sin motivo")[:200]})'
    used,cap=respuestas.reads_today(reader,'comments',now),respuestas.read_caps()['comments']
    if used>=cap:return f'se agotó el cupo diario de lecturas ({used}/{cap}; REPLIES_READ_CAPS)'
    job=Job.objects.filter(kind='read_own_comments').order_by('-created_at').first()
    if job and job.state in (Job.State.QUEUED,Job.State.RUNNING):
        return f'la lectura está en cola desde {since_text(job.created_at,now)} sin terminar: revisa que el worker esté corriendo'
    if job and job.state==Job.State.FAILED:return f'la última lectura falló ({(job.error or "sin detalle")[:200]})'
    if job and job.error:return f'la última lectura se detuvo: {job.error[:200]}'
    return 'no se encontró la causa; revisa el registro del autopiloto'

@vigilante
def lecturas_detenidas(now):
    """Inside READ_WINDOW, more than ALERT_READS_GAP_HOURS of window hours without reading the comments of his posts
    while a post's read was due more than an hour ago: once a day, with the likely reason. (With the adaptive cadence a
    quiet day may go 4 h without reads and nothing is wrong: hence the due post.)"""
    from . import operador, respuestas
    if not operador.within_read_window(now):return []
    rows=respuestas.plan(now)
    if not rows:return []
    reader=respuestas.reader_account()
    reads=AuditEvent.objects.filter(action='replies.read',metadata__kind='comments')
    if reader:reads=reads.filter(target=str(reader.id))
    last=reads.order_by('-created_at').values_list('created_at',flat=True).first()
    since=max(last or now-timedelta(days=7),now-timedelta(days=7))
    if window_time(since,now)<=reads_gap_hours():return []
    when=f'desde {since_text(since,now)}' if last and since==last else 'desde hace más de 7 días'

    overdue=[r for r in rows if r.due and window_time(r.last+r.every if r.last else r.execution.started_at,now)>=timedelta(hours=1)]
    if not overdue:return []
    return [Aviso('lecturas:detenidas',
        f'Barrio · No se están leyendo los comentarios de tus posts {when}: {_why_not_reading(reader,now)}. '
        f'{len(overdue)} {"post espera" if len(overdue)==1 else "posts esperan"} su lectura; mientras tanto nadie responde '
        'los comentarios nuevos.')]

# --------------------------------------------------------------------------- the daily summary

def summary_lines(now):
    """One line per cap with used/cap, then the hours the comments of his posts were read."""
    account=_reader();lines=[]
    if account is not None:
        for scope,kind,used,cap in read_caps(account,now):lines.append(f'• Lecturas {scope}.{kind}: {used}/{cap}')
    for capability,used,daily in write_caps(now):lines.append(f'• Escrituras {capability} ({capability_label(capability)}): {used}/{daily}')
    if account is not None:
        from .operador import period_starts
        day,_=period_starts(now);hours={}
        for at in AuditEvent.objects.filter(action='replies.read',target=str(account.id),metadata__kind='comments',
                                            created_at__gte=day,created_at__lt=day+timedelta(days=1)).values_list('created_at',flat=True):
            hours[_local(at).hour]=hours.get(_local(at).hour,0)+1
        lines.append('• Lecturas de comentarios de tus posts por hora: '+
                     (' · '.join(f'{h:02d} h {n}' for h,n in sorted(hours.items())) or 'ninguna'))
    return lines

def summary_text(now):
    return '\n'.join([f'Barrio · Resumen del {_local(now):%d/%m} al cierre de la ventana ({hhmm(close_of_day(now))}), usado/tope:',
                      *summary_lines(now)])

@vigilante
def resumen_diario(now):
    """At the close of the read window (SLACK_DAILY_SUMMARY, on with a webhook): once a day, on the summaries channel."""
    if not summary_enabled() or now<close_of_day(now):return []
    return [Aviso('resumen:diario',lambda:summary_text(now),channel='resumen')]
