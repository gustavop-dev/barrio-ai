"""Phase 4 of docs/plan-outbound.md «El sistema del comprador» (BAR-21): messages 2 to 4 after the first one, the course's
sequence (methodology «secuencia_mensajes»: LI-09-M003-K05, LI-09-V014-K01/K02/K03; when it stops, LI-10-V013-K02 and
LI-10-M001-K08). Everything is behind BUYER_SEQUENCE_ENABLED (default false): off, nothing here runs and the journey ends
at the first message, as in phase 3. It needs phase 3 (BUYER_FIRST_MESSAGE_ENABLED), the lead (LEAD_ENABLED) and the
inbox (INBOX_ENABLED): without a recent read of the inbox it never assumes «she did not answer», so nothing is prepared.

Gustavo's decision (17/11/2026): the follow-up is the course's four-message sequence, always as drafts he copies and
sends himself (INB-08: the app never sends a private message; linkedin_directo/permitidas.py is untouched). Each one is
the same Tu turno card as the first message, labelled «Seguimiento 2 de 4»…, with «Hecho, le escribí» and «No
escribirle» (mensajes_comprador.close).

- When: message n is due BUYER_SEQUENCE_DAYS (4,5,7) after Gustavo's «Hecho, le escribí» on message n−1: the course's
  slide (+4/+5/+7; the spoken class says «máximo 4 días» for message 2 and is ambiguous for message 3). It runs from
  «Hecho», never from the draft; if he did not send n−1, n is never prepared. Drafted Monday to Friday, inside
  READ_WINDOW (LI-10-M001-K08: «lunes a viernes, en horario laboral»).
- What: M2 tells the same pain another way, with a short story (not M1 again, no apology); M3 asks whether she is the
  right person and who handles it, for a referral (phase 6 links that person: referral_asked, link_referral); M4 closes
  with grace, asks for nothing and leaves the door open. Fixed rules (text_issues: RSP-07's plus one per number), one
  redraft, the lead with its questions per number (lider.review_buyer_draft); a draft that fails is discarded and
  audited, never shown. The drafting and the review are mensajes_comprador's, with this methodology.
- Stop: «si responde, se detiene todo». Before preparing a follow-up and before showing its card, her reply is looked
  for in what the inbox read: her message after his first one in the conversation's snapshot (the fold), or the chat
  list showing her message last. A reply cancels the pending follow-ups, moves the journey to «respondio» (her message
  as an inbound touch) and calls REPLY_HANDLERS (phase 6). conversaciones.read_inbox reads the threads of these buyers
  first (prioritize), within its caps.
- End: BUYER_SEQUENCE_REST_AFTER_DAYS (7) after message 4 without a reply she rests BUYER_SEQUENCE_REST_DAYS (90; a
  year from the third attempt) with reason secuencia_sin_respuesta. She stays a connection; a signal of hers during the
  rest wakes her with a new angle (calentamiento.wake, the warm-up's rule), and the first message of that attempt is
  phase 3's. A follow-up stopped by the rules or the lead also ends her sequence that way; so does one overdue by more
  than BUYER_SEQUENCE_MAX_LATE_DAYS (a first message sent long before the switch). «No escribirle» at any point is a
  definitive exit.
"""
import difflib
import logging
import os
import re
from datetime import timedelta
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from . import comprador, operador
from .models import AuditEvent, BuyerDraft, BuyerJourney, BuyerTouch, Contact, Conversation

log=logging.getLogger(__name__)
Kind=BuyerTouch.Kind;Step=BuyerJourney.Step;State=BuyerDraft.State;StoppedBy=BuyerDraft.StoppedBy
RestReason=BuyerJourney.RestReason
MESSAGE=BuyerDraft.Kind.MESSAGE
SEQUENCE_UNITS=operador.SEQUENCE_UNITS
METHODOLOGY='secuencia_mensajes'
PURPOSE='buyer-sequence'
NUMBERS=(2,3,4)
LAST=4
STEPS=comprador.MESSAGE_STEPS  # mensaje_1…mensaje_4: the journey is at mensaje_{n-1} while message n is due
WAITING='buyer.sequence_waiting'   # once a local day: due follow-ups wait for an inbox read
REPLIED='buyer.sequence_replied'   # once per reply: the sequence stopped
RESTED='buyer.sequence_rested'
CARD_INBOX_MAX_AGE=timedelta(hours=24)  # a card shows only while the inbox was read this recently (it covers a night)
REPLY_LOOKBACK=timedelta(days=14)       # replies older than this are not reported again (the switch turned on late)
# Phase 6 registers here what to do when a buyer replies: handler(journey, at, after) with `after` the messages sent
# before her reply. Each one runs once per reply, in its own savepoint; a failure is logged and audited, never raised.
REPLY_HANDLERS=[]

def _int(name,default,low,high):
    try:value=int(os.environ.get(name,str(default)).strip())
    except ValueError:return default
    return min(max(value,low),high)

def enabled():
    """BUYER_SEQUENCE_ENABLED=true turns phase 4 on; off (the default) nothing here runs."""
    return os.environ.get('BUYER_SEQUENCE_ENABLED','false').strip().lower()=='true'

def active():
    """Follow-ups are prepared only with this switch, phase 3's and the lead on: nothing reaches Gustavo unreviewed."""
    from . import lider, mensajes_comprador
    return enabled() and mensajes_comprador.enabled() and lider.enabled()

def days():
    """BUYER_SEQUENCE_DAYS='4,5,7': days from the «Hecho» of message n−1 to message n, for n = 2, 3, 4 (each 1–30)."""
    try:values=[int(v) for v in os.environ.get('BUYER_SEQUENCE_DAYS','4,5,7').split(',')]
    except ValueError:values=[]
    if len(values)!=3:values=[4,5,7]
    return {n:timedelta(days=min(max(v,1),30)) for n,v in zip(NUMBERS,values)}

def rest_after():
    """BUYER_SEQUENCE_REST_AFTER_DAYS (7): days after the «Hecho» of message 4 without a reply until she rests."""
    return timedelta(days=_int('BUYER_SEQUENCE_REST_AFTER_DAYS',7,1,60))

def rest_days():
    """BUYER_SEQUENCE_REST_DAYS (90): how long she rests after a sequence without a reply."""
    return timedelta(days=_int('BUYER_SEQUENCE_REST_DAYS',90,7,365))

def inbox_fresh():
    """BUYER_SEQUENCE_INBOX_FRESH_HOURS (3): a follow-up is prepared only after an inbox read this recent."""
    return timedelta(hours=_int('BUYER_SEQUENCE_INBOX_FRESH_HOURS',3,1,24))

def max_late():
    """BUYER_SEQUENCE_MAX_LATE_DAYS (14): a follow-up overdue by more than this is not written; she rests instead."""
    return timedelta(days=_int('BUYER_SEQUENCE_MAX_LATE_DAYS',14,1,90))

def _audit(action,target,**metadata):
    operador._audit(None,action,target,**metadata)

# --------------------------------------------------------------------------- where she is

def sent(state):
    """Gustavo's «Hecho, le escribí» of this attempt (the journey's drafts and RSP-07's first message), oldest first."""
    return sorted(state.sent,key=lambda t:t.at)

def due(state,messages=None):
    """When the next thing of the sequence is due: message n BUYER_SEQUENCE_DAYS after the «Hecho» of n−1, or her rest
    BUYER_SEQUENCE_REST_AFTER_DAYS after message 4. None before the first «Hecho» and once she replied."""
    messages=sent(state) if messages is None else messages
    if not messages or state.replied or state.interested or state.meeting:return None
    last=messages[-1].at
    if len(messages)>=LAST:return last+rest_after()
    return last+days()[len(messages)+1]

def replied_at(journey,state,messages=None):
    """When she replied to this attempt's messages, from what the inbox read: a message of hers after his first one in
    her conversation's snapshot (the fold), or the chat list showing her message last after his first «Hecho» (its
    thread not read yet). None when nothing shows a reply."""
    if state.replied_at:return state.replied_at
    messages=sent(state) if messages is None else messages
    if not messages:return None
    row=_her_last(journey,messages[0].at)
    return row.last_message_at if row else None

def _her_last(journey,since):
    return (Conversation.objects.filter(contact_id=journey.contact_id,last_from_me=False,last_message_at__gt=since)
            .order_by('-last_message_at').first())

def _last_read(account,now):
    return (AuditEvent.objects.filter(action='inbox.read_run',target=str(account.id),created_at__lte=now)
            .order_by('-created_at').values_list('created_at',flat=True).first())

def inbox_ready(account,now=None):
    """(ready, reason): her reply can only be known from the inbox. Off, or no read of the chat list in the last
    BUYER_SEQUENCE_INBOX_FRESH_HOURS: the sequence waits, it never assumes «she did not answer»."""
    from . import conversaciones
    now=now or timezone.now()
    if not conversaciones.enabled():return False,'el inbox está apagado (INBOX_ENABLED=false)'
    last=_last_read(account,now)
    if last is None or last<now-inbox_fresh():
        hours=int(inbox_fresh().total_seconds()//3600)
        return False,f'no se leyó el inbox en las últimas {hours} h (cuenta en pausa, tope de lecturas o fuera de la ventana)'
    return True,''

def _card_inbox(account,now):
    from . import conversaciones
    if not conversaciones.enabled():return False
    last=_last_read(account,now)
    return bool(last and last>=now-CARD_INBOX_MAX_AGE)

def previous(journey,state,messages=None):
    """What Gustavo already sent her in this attempt: [{numero, texto, enviado}], oldest first. The journey's messages from
    their drafts; a first message of RSP-07 from its comment (dm_opener)."""
    messages=sent(state) if messages is None else messages
    drafts={d.number:d for d in BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=MESSAGE,attempt=journey.attempt,state=State.SENT)}
    out=[]
    for i,touch in enumerate(messages,1):
        detail=touch.detail or {};text=''
        if detail.get('fuente')=='recorrido' and detail.get('numero') in drafts:text=drafts[detail['numero']].text
        elif touch.comment_id:text=((touch.comment.decision or {}).get('dm_opener') or '')
        out.append({'numero':i,'texto':text,'enviado':touch.at.isoformat()})
    return out

def ready(journey,number,now=None):
    """(ready, reason) for message `number` right before it is paid for (mensajes_comprador.prepare): the switches, her
    step, no reply, a recent inbox read and its due date."""
    now=now or timezone.now()
    if not active():return False,'Fase 4, fase 3 o líder apagados.'
    state=comprador._fold(comprador._touches(journey));messages=sent(state)
    if journey.step not in STEPS or len(messages)!=number-1:
        return False,f'El mensaje {number-1} no se envió o ya hubo otro: sin mensaje {number}.'
    if replied_at(journey,state,messages):return False,'Respondió: se detiene la secuencia.'
    fresh,why=inbox_ready(journey.contact.account,now)
    if not fresh:return False,'Sin leer el inbox no se prepara: '+why+'.'
    if now<due(state,messages):return False,'Todavía no toca.'
    return True,''

# --------------------------------------------------------------------------- fixed rules per number

APOLOGY=re.compile(r"\b(?:sorry|apologi[sz]e|apologies|pardon\s+me)\b|\bperd[oó]n\b|\bperdona(?:me)?\b|"
                   r"\bdisculp(?:a|as|e|en|ame|eme)\b|\blamento\s+(?:molestar|insistir|escribir)",re.I)
RIGHT_PERSON=re.compile(r"\bright\s+person\b|\bperson\s+(?:who|that)\s+(?:owns|handles|runs|leads|decides)\b|"
                        r"\bwho\s+(?:else\s+)?(?:on\s+\w+\s+\w+\s+)?(?:owns|handles|is\s+in\s+charge|takes\s+care|looks\s+after|runs|leads|decides)\b|"
                        r"\bpersona\s+(?:indicada|correcta|adecuada)\b|"
                        r"\bqui[eé]n\s+(?:m[aá]s\s+)?(?:se\s+encarga|lleva|maneja|decide|est[aá]\s+a\s+cargo|ve\s+esto)\b",re.I)
ASKS=re.compile(r"\b(?:let\s+me\s+know|could\s+you|can\s+you|would\s+you|please|reply|respond|get\s+back\s+to\s+me|"
                r"av[ií]same|me\s+(?:dices|cuentas|respondes|confirmas)|podr[ií]as|puedes|por\s+favor|resp[oó]nde(?:me)?)\b",re.I)
BEGS=re.compile(r"\b(?:one\s+last\s+chance|last\s+chance|i\s+really\s+need|begging|i\s+beg|te\s+lo\s+ruego|te\s+ruego|"
                r"[uú]ltima\s+oportunidad|necesito\s+que)\b",re.I)
WORD=re.compile(r"[a-z0-9áéíóúñü]+")
REPEAT_RATIO=0.6  # a follow-up this similar to an earlier message is that message again
REPEAT_RUN=8      # or eight words in a row in common

def _words(text):
    return WORD.findall((text or '').lower())

def repeats(text,earlier):
    """`text` says an earlier message again: a SequenceMatcher ratio of REPEAT_RATIO or more, or REPEAT_RUN words in a
    row in common."""
    words=_words(text)
    for other in earlier or ():
        theirs=_words(other)
        if not words or not theirs:continue
        if difflib.SequenceMatcher(None,words,theirs,autojunk=False).ratio()>=REPEAT_RATIO:return True
        runs={' '.join(theirs[i:i+REPEAT_RUN]) for i in range(len(theirs)-REPEAT_RUN+1)}
        if any(' '.join(words[i:i+REPEAT_RUN]) in runs for i in range(len(words)-REPEAT_RUN+1)):return True
    return False

def text_issues(number,text,previous=(),reference=''):
    """The fixed rules of follow-up `number` (BIB-09-secuencia-mensajes), checked in code before the lead: the first
    message's (respuestas.dm_text_issues: three lines and 500 characters, no links, no selling, no asking for minutes or
    a meeting, no formulas, her language, no private leaks, no invented experience) and, per number: M2 does not say an
    earlier message again and does not apologise; M3 asks whether she is the right person or who handles it; M4 asks
    for nothing and does not beg. `previous`: the texts already sent to her. Reads only Gustavo's public and private
    blocks (guardas.blocks, through the first message's rules)."""
    text=(text or '').strip()
    if not text:return []
    from .respuestas import dm_text_issues
    label=f'Mensaje {number}'
    issues=[i.replace('Primer mensaje',label) for i in dm_text_issues(text,reference)]
    earlier=[previous] if isinstance(previous,str) else list(previous or ())
    if repeats(text,earlier):issues.append(f'{label} que repite un mensaje anterior (el mismo dolor va contado de otra forma)')
    if number==2 and APOLOGY.search(text):issues.append('Mensaje 2 que se disculpa por escribir de nuevo')
    if number==3 and not (RIGHT_PERSON.search(text) and '?' in text):
        issues.append('Mensaje 3 sin la pregunta de si es la persona indicada o quién se encarga de esto')
    if number==4 and ('?' in text or '¿' in text or ASKS.search(text) or BEGS.search(text)):
        issues.append('Mensaje 4 que pregunta, pide o ruega: cierra con elegancia y no pide nada')
    return issues

# --------------------------------------------------------------------------- the drafter's part

JOBS={2:'Mensaje 2 de 4: nombra el mismo dolor del primero, contado de otra forma, con una historia corta (un caso típico, '
        'sin atribuirle a Gustavo experiencias que no estén en public_facts). No repitas el primer mensaje ni te disculpes por '
        'escribir de nuevo; puedes reconocer, sin reproche, que quizá no pudo responder.',
      3:'Mensaje 3 de 4: ya no repitas el dolor. Pregunta si quizá no es la persona indicada y quién se encarga de esto en su '
        'empresa (no «quién me puede ayudar»), para llegar a esa persona. Una sola pregunta.',
      4:'Mensaje 4 de 4, el último: cierra con elegancia. Agradece su tiempo, asume que quizá no es el momento o que ya lo '
        'tienen resuelto y deja la puerta abierta. No preguntes, no pidas nada y no ruegues.'}

SYSTEM='''Eres el agente de Relaciones y comunidad de Barrio AI. Redactas un SEGUIMIENTO privado que Gustavo le enviaría a un
posible cliente (un founder) que aceptó su invitación en LinkedIn y no respondió a sus mensajes anteriores. El equipo nunca
lo envía: Gustavo lo copia y lo envía él mismo desde LinkedIn. Cada mensaje de la secuencia tiene un trabajo distinto; el
de este está en `seguimiento.trabajo`. `seguimiento.anteriores` son los mensajes que Gustavo ya le envió: no los repitas.

Como mucho tres líneas y 500 caracteres. Sin enlaces, correos, teléfonos ni hashtags; sin pedir minutos, llamadas ni
reuniones; sin fórmulas como «gracias por conectar», «quedo atento» o «espero que estés bien»; sin vender ni decir a quién
ayuda Gustavo.'''

def system(number):
    from .mensajes_comprador import COMMON_RULES
    return SYSTEM+'\n'+JOBS[number]+COMMON_RULES

def units():
    """(units, missing): the activated methodology's units, loaded whole with its name."""
    loaded,missing,omitted=operador.course_context(SEQUENCE_UNITS,metodologia=METHODOLOGY)
    return loaded,missing+omitted

def inputs(contact,journey,facts,at,number):
    """What the drafter reads for message `number`: the person, her facts, what Gustavo already sent her and the job."""
    from .mensajes_comprador import inputs_for
    data=inputs_for(contact,journey,MESSAGE,facts,at)
    state=comprador._fold(comprador._touches(journey));messages=sent(state)
    earlier=previous(journey,state,messages)
    last=messages[-1].at if messages else None
    data['momento']={'que_es':f'Mensaje {number} de 4. No respondió a los anteriores; Gustavo lo envía a mano.',
                     'dias_desde_el_anterior':round((at-last).total_seconds()/86400,1) if last else None}
    data['seguimiento']={'numero':number,'de':LAST,'trabajo':JOBS[number],'anteriores':earlier}
    # BAR-25: message 2 tells the pain with a short story; with the ProjectApp buyer on, the case of her segment (only
    # its confirmed facts) may be that story (projectapp.case_for: None for any other buyer).
    from . import projectapp
    case=projectapp.case_for(contact) if number==2 else None
    if case:data['caso_projectapp']=case
    return data

# --------------------------------------------------------------------------- the autopilot's step

def _cancel(journey,now,reason):
    rows=list(BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=MESSAGE,number__gt=1,state__in=[State.READY,State.REVIEWING]))
    for row in rows:
        row.state=State.CANCELLED;row.closed_at=now;row.closed_note=reason[:1000]
        row.save(update_fields=['state','closed_at','closed_note'])
        _audit('buyer.draft_cancelled',row.contact_id,tipo=MESSAGE,numero=row.number,borrador=str(row.pk),motivo=reason[:300])
    return [row.number for row in rows]

def _stop(journey,state,at,now,messages):
    """She replied: everything stops. Her pending follow-ups are cancelled; the journey moves to «respondio» (her message
    as an inbound touch: the thread's once the inbox read it, else the chat list's row) and REPLY_HANDLERS run, once per
    reply. Returns 1 when something changed."""
    cancelled=_cancel(journey,now,'Respondió: se detiene la secuencia.')
    if not state.replied:
        row=_her_last(journey,messages[0].at)
        if row is not None:
            comprador.record(journey,Kind.REPLIED_MESSAGE,at=row.last_message_at,key=f'lista:{row.pk}:{row.last_message_at.isoformat()}',
                             detail={'origen':'lista_de_chats'},conversation=row)
    if at<now-REPLY_LOOKBACK or AuditEvent.objects.filter(action=REPLIED,target=str(journey.contact_id),metadata__intento=journey.attempt).exists():
        return int(bool(cancelled))
    after=sum(1 for t in messages if t.at<=at) or len(messages)
    _audit(REPLIED,journey.contact_id,intento=journey.attempt,numero=after,cancelados=cancelled,at=at.isoformat())
    for handler in REPLY_HANDLERS:
        try:
            with transaction.atomic():handler(journey,at,after)
        except Exception as exc:  # noqa: BLE001 - a phase 6 handler never stops the sequence
            log.exception('Secuencia: fallo en un manejador de respuesta (%s)',journey.pk)
            _audit('buyer.sequence_failed',journey.contact_id,donde='respuesta',error=type(exc).__name__,detalle=str(exc)[:300])
    return 1

def _rest(journey,now,why,messages):
    """No reply: she rests (secuencia_sin_respuesta), a year from the third attempt. She stays a connection."""
    from . import calentamiento
    until=now+(calentamiento.LONG_REST if journey.attempt>=calentamiento.MAX_ATTEMPTS else rest_days())
    try:comprador.rest(journey,RestReason.SEQUENCE_NO_REPLY,until,at=now,note=why)
    except ValueError as exc:
        _audit('buyer.sequence_failed',journey.contact_id,donde='descanso',error='ValueError',detalle=str(exc)[:300]);return 0
    _audit(RESTED,journey.contact_id,intento=journey.attempt,mensajes=len(messages),hasta=until.isoformat(),motivo=why[:300])
    return 1

def _wake(account,now):
    """A sequence's rest: a signal of hers during it wakes her (a new attempt with that signal as the angle); its end, a
    new attempt with another angle. The warm-up's rule (calentamiento.wake)."""
    from . import calentamiento
    woken=0
    for journey in BuyerJourney.objects.select_related('contact').filter(contact__account=account,step=Step.RESTING,
                                                                         rest_reason=RestReason.SEQUENCE_NO_REPLY):
        try:
            with transaction.atomic():woken+=bool(calentamiento.wake(journey,now))
        except Exception as exc:  # noqa: BLE001 - one person never stops the step
            log.exception('Secuencia: fallo al despertar %s',journey.pk)
            _audit('buyer.sequence_failed',journey.contact_id,donde='despertar',error=type(exc).__name__,detalle=str(exc)[:300])
    return woken

def _waiting(account,now,why,count):
    """Once a local day: due follow-ups wait because her reply cannot be read (alertas_slack.secuencia_sin_inbox)."""
    day,_=operador.period_starts(now)
    if AuditEvent.objects.filter(action=WAITING,target=str(account.id),created_at__gte=day).exists():return
    _audit(WAITING,account.id,motivo=why,personas=count)

def step(account,now=None):
    """The autopilot's sequence step (autopiloto._buyer_drafts, with phase 3's): (decisions taken without a paid call, the
    next (contact, kind, attempt, number) to draft or None). Wakes the sequence's rests; then, for each buyer who got a
    message by «Hecho» in this attempt (and the ones who replied lately): her reply stops everything; without a recent
    inbox read nothing else happens and it says so once a day; message 4 sent and BUYER_SEQUENCE_REST_AFTER_DAYS without
    a reply, or a follow-up stopped or too late: she rests; else the next follow-up once due, on a weekday."""
    from .mensajes_comprador import MAX_TRIES, decision, tries
    now=now or timezone.now()
    if not active():return 0,None
    decided=_wake(account,now)
    fresh,why=inbox_ready(account,now)
    weekday=not operador.is_weekend(now)
    blocked=0;item=None
    rows=(BuyerJourney.objects.select_related('contact','contact__account').filter(contact__account=account)
          .filter(Q(step__in=STEPS)|Q(step=Step.REPLIED,last_inbound_at__gte=now-REPLY_LOOKBACK)).order_by('last_message_at'))
    for journey in rows:
        state=comprador._fold(comprador._touches(journey));messages=sent(state)
        if not messages:continue
        at=replied_at(journey,state,messages)
        if at is not None:
            decided+=_stop(journey,state,at,now,messages);continue
        if journey.step not in STEPS:continue
        when=due(state,messages)
        if when is None or when>now:continue
        if not fresh:blocked+=1;continue
        number=len(messages)+1
        if number>LAST:
            decided+=_rest(journey,now,f'Sin respuesta {rest_after().days} días después del mensaje 4.',messages);continue
        row=decision(journey.contact,MESSAGE,journey.attempt,number)
        if row is not None:
            if row.stopped_by and now>=messages[-1].at+rest_after():
                decided+=_rest(journey,now,f'El mensaje {number} no pasó las reglas o el líder; sin respuesta a los anteriores.',messages)
            continue
        if now>when+max_late():
            decided+=_rest(journey,now,f'Seguimiento {number} vencido hace más de {max_late().days} días: no se escribe tarde.',messages)
            continue
        if weekday and item is None and tries(journey.contact,MESSAGE,journey.attempt,number)<MAX_TRIES:
            item=(journey.contact,MESSAGE,journey.attempt,number)
    if blocked:_waiting(account,now,why,blocked)
    return decided,item

# --------------------------------------------------------------------------- the inbox reads these threads first

def prioritize(conversations,now=None):
    """conversaciones.read_inbox, within its caps: the threads of buyers in the sequence go first, hers when her message
    is the last one (a reply that stops it), then the ones with a follow-up due within a day. Same order otherwise. Phase
    6 (BUYER_REPLY_ENABLED): a buyer who replied or is interested writing again goes first too."""
    if not active() or not conversations:return conversations
    now=now or timezone.now()
    ids=[c.contact_id for c in conversations if c.contact_id]
    from . import respuesta_comprador
    steps=[*STEPS,*respuesta_comprador.STEPS] if respuesta_comprador.enabled() else STEPS
    journeys={j.contact_id:j for j in BuyerJourney.objects.filter(contact_id__in=ids,step__in=steps)}
    def rank(item):
        index,conversation=item;journey=journeys.get(conversation.contact_id)
        if journey is None:return (2,index)
        if not conversation.last_from_me:return (0,index)
        if journey.next_at and journey.next_at<=now+timedelta(days=1):return (1,index)
        return (2,index)
    return [c for _,c in sorted(enumerate(conversations),key=rank)]

# --------------------------------------------------------------------------- Tu turno

BODIES={2:'No ha respondido a tu primer mensaje. El equipo te dejó el mensaje 2: el mismo dolor contado de otra forma.',
        3:'Sigue sin responder. El equipo te dejó el mensaje 3: si no es la persona indicada, que te diga quién se encarga.',
        4:'Sin respuesta a tres mensajes. El equipo te dejó el mensaje 4, el último: cierra con elegancia. Sin respuesta, '
          'descansa {dias} días.'}

def label(number):
    return f'Seguimiento {number} de {LAST}'

def cards(card,now=None):
    """Tu turno: the follow-ups ready for Gustavo, the same card as the first message's («Hecho, le escribí», «No
    escribirle», same endpoint) with its label «Seguimiento n de 4» and what he sent last. Never when she replied, when
    her journey moved on, or without an inbox read in the last CARD_INBOX_MAX_AGE (her reply could be there)."""
    if not enabled():return []
    now=now or timezone.now()
    rows=(BuyerDraft.objects.select_related('contact__buyer_journey','contact__account')
          .filter(kind=MESSAGE,number__gt=1,state=State.READY).filter(Q(show_at__isnull=True)|Q(show_at__lte=now))
          .order_by('show_at','created_at'))
    out=[];inbox={}
    for row in rows:
        contact=row.contact;journey=getattr(contact,'buyer_journey',None)
        if journey is None or journey.attempt!=row.attempt or journey.step!=STEPS[row.number-2]:continue
        if contact.account_id not in inbox:inbox[contact.account_id]=_card_inbox(contact.account,now)
        if not inbox[contact.account_id]:continue
        state=comprador._fold(comprador._touches(journey));messages=sent(state)
        if len(messages)!=row.number-1 or replied_at(journey,state,messages):continue
        earlier=previous(journey,state,messages);last=earlier[-1] if earlier else {}
        ago=(now-messages[-1].at).days if messages else None
        name=contact.display_name or 'Alguien'
        close=f'/api/v1/respuestas/{row.id}/mensaje'
        actions=[{'label':'Abrir su perfil','href':contact.profile_url,'primary':True},
                 {'label':'Hecho, le escribí','endpoint':close,'body':{'how':'enviado'}},
                 {'label':'No escribirle','endpoint':close,'body':{'how':'no'},'note_optional':True}]
        body=BODIES[row.number].format(dias=rest_days().days)+' Lo envías tú desde LinkedIn. «No escribirle» la saca del recorrido.'
        sent_label=f'Tu mensaje {last.get("numero",row.number-1)}'+(f' (hace {ago} días)' if ago is not None else '')
        out.append(card(f'dm:{row.id}','mensaje',f'{label(row.number)} para {name}',body,actions,agent='relaciones_comunidad',
                        priority='importante',created_at=row.show_at or row.decided_at,
                        message={'text':row.text,'text_label':label(row.number),'comment':(last.get('texto') or '')[:600],
                                 'comment_label':sent_label,'reply':'','reply_label':'','piece_id':'','topic':'','origin':'recorrido',
                                 'person':{'id':str(contact.id),'display_name':name,'headline':contact.headline,
                                           'profile_url':contact.profile_url,'role':(contact.classification or {}).get('role')}}))
    return out

# --------------------------------------------------------------------------- phase 6: the referral of message 3

def referral_asked(journey):
    """Whether message 3 («¿no eres la persona indicada?») went to her in this attempt: {'enviado', 'texto', 'borrador'}
    or None. Phase 6 reads it when her reply names someone else."""
    row=(BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=MESSAGE,number=3,attempt=journey.attempt,state=State.SENT)
         .order_by('-closed_at').first())
    if row is None:return None
    return {'enviado':row.closed_at.isoformat() if row.closed_at else None,'texto':row.text,'borrador':str(row.pk)}

@transaction.atomic
def link_referral(journey,referrer,at=None,note='',reply=None):
    """Phase 6: `journey` is the person `referrer` pointed to after her message 3 («tal persona me dijo que viniera
    contigo»), or in any reply of hers classified «otra persona» (`reply`, her BuyerDraft «respuesta»: respuesta_comprador).
    Records it once on the new person's log (a «referido» touch) and in BuyerJourney.referred_by. Raises ValueError when
    the referrer neither got message 3 nor answered «otra persona», or for the same person."""
    if journey.pk==referrer.pk:raise ValueError('Una persona no se refiere a sí misma.')
    asked=referral_asked(referrer)
    if asked is None and reply is None:raise ValueError('Quien refiere no recibió el mensaje 3 de su secuencia.')
    asked=asked or {'borrador':''}
    at=at or timezone.now()
    BuyerJourney.objects.filter(pk=journey.pk).update(referred_by=referrer)
    referrer_name=Contact.objects.filter(pk=referrer.contact_id).values_list('display_name',flat=True).first() or ''
    touch=comprador.record(journey,Kind.REFERRED,at=at,key=f'referido:{referrer.pk}',
                           detail={'de':str(referrer.contact_id),'nombre':referrer_name[:200],'mensaje_3':asked['borrador'],
                                   'respuesta':str(reply.pk) if reply is not None else '','nota':(note or '')[:300]})
    _audit('buyer.referral_linked',journey.contact_id,de=str(referrer.contact_id),mensaje_3=asked['borrador'],
           respuesta=str(reply.pk) if reply is not None else '')
    return touch

# --------------------------------------------------------------------------- what Slack and the funnel read

def due_today(now=None):
    """The follow-ups that wait for Gustavo today, as [(name, number, at)], soonest first: the ones ready in Tu turno and
    the ones due before the local day ends (prepared when they are due). Read only."""
    now=now or timezone.now()
    if not enabled():return []
    day,_=operador.period_starts(now);end=day+timedelta(days=1)
    out=[];seen=set()
    for row in BuyerDraft.objects.select_related('contact__buyer_journey').filter(kind=MESSAGE,number__gt=1,state=State.READY):
        journey=getattr(row.contact,'buyer_journey',None)
        if journey and journey.attempt==row.attempt and journey.step==STEPS[row.number-2]:
            out.append((row.contact.display_name or 'Alguien',row.number,row.show_at or row.decided_at or now));seen.add(row.contact_id)
    for journey in BuyerJourney.objects.select_related('contact').filter(step__in=STEPS[:-1],next_at__lt=end).exclude(contact_id__in=seen):
        number=journey.messages_sent+1
        if 2<=number<=LAST and not BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=MESSAGE,number=number,attempt=journey.attempt).exists():
            out.append((journey.contact.display_name or 'Alguien',number,journey.next_at))
    return sorted(out,key=lambda item:item[2])

def funnel(journeys):
    """The sequence in the buyer's funnel (comprador.funnel → secuencia): how many got messages 1–4 (in some attempt),
    after how many messages the ones who replied did (the course says most reply to the 2nd or 3rd: measured here, not
    assumed) and her follow-ups resting after it."""
    received={str(n):0 for n in range(1,LAST+1)};after={str(n):0 for n in range(1,LAST+1)}
    ids=[j.pk for j in journeys]
    logs={}
    for t in (BuyerTouch.objects.filter(journey_id__in=ids,kind__in=[Kind.MESSAGE,Kind.REPLIED_MESSAGE,Kind.RETRY])
              .only('journey_id','kind','at','key').order_by('at','created_at')):
        logs.setdefault(t.journey_id,[]).append(t)
    for entries in logs.values():
        most=0;attempt_sent=0;replied=False
        for t in comprador.current(entries):
            if t.kind==Kind.RETRY:attempt_sent=0;replied=False;continue
            if t.kind==Kind.MESSAGE:attempt_sent+=1;most=max(most,attempt_sent)
            elif t.kind==Kind.REPLIED_MESSAGE and attempt_sent and not replied:
                replied=True;after[str(min(attempt_sent,LAST))]+=1
        for n in range(1,min(most,LAST)+1):received[str(n)]+=1
    total=sum(after.values());middle=after['2']+after['3']
    return {'recibieron':received,'respondieron_tras':after,
            'comprobacion':{'curso':'La mayoría responde al 2.º o 3.º mensaje (LI-09-M003-K05).','respuestas':total,
                            'tras_2_o_3':middle,'tras_2_o_3_pct':round(middle/total*100,2) if total else None,
                            'muestra_chica':total<comprador.SMALL_SAMPLE},
            'descansan':sum(1 for j in journeys if j.rest_reason==RestReason.SEQUENCE_NO_REPLY and j.step==Step.RESTING),
            'activa':enabled()}
