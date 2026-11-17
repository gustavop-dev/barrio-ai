"""Phase 6 of docs/plan-outbound.md (BAR-23): the meeting a buyer books through Gustavo's Cal.com link, the end of the
LinkedIn machine (Gustavo, 17/11/2026: «la máquina de LinkedIn termina en la REUNIÓN AGENDADA»).

Cal.com posts a webhook (POST /api/v1/comprador/calcom/webhook) on BOOKING_CREATED, BOOKING_RESCHEDULED and
BOOKING_CANCELLED. Source: cal.com/docs/developing/guides/automation/webhooks and Cal.com's sendPayload.ts
(packages/features/webhooks/lib/sendPayload.ts): the body is JSON {triggerEvent, createdAt, payload}; with a secret the
header X-Cal-Signature-256 is HMAC-SHA256(secret, raw body) in hex. Without CALCOM_WEBHOOK_SECRET every call is rejected.
The body is trusted ONLY to match the booking with a buyer:

1. the identifier her link carries: link_for() appends ?metadata[barrio]=<booking_ref> to CALCOM_BOOKING_URL and Cal.com
   keeps a booking link's `metadata[key]` query parameters in the booking, sent back as payload.metadata.key (Cal.com
   docs, «Webhooks» → metadata, and «Prefill booking form»);
2. a reschedule: the booking it replaces (payload.rescheduleUid, or fromReschedule);
3. the attendee's email, when she wrote it in her LinkedIn conversation with Gustavo;
4. the attendee's exact name (accents and case aside), when exactly one buyer who got the link has it.

Nothing matched stays «sin_emparejar»: a Tu turno card and a Slack alert for Gustavo to associate it (match) or discard
it. Gustavo can also mark it by hand: «Agendó» on her reply card (manual). Each delivery is processed once (the sha256
of the raw body, under an advisory lock); a booking is one row per Cal.com uid.

On a match: the journey moves to «reunion» with its date (a MEETING touch; interesado first when it was not), her drafts
still pending are cancelled, and the lead is handed over (entrega_lead.build). A cancellation takes her back to
«interesado» (a reunion_cancelada touch) and cancels the handoff; a reschedule moves the date."""
import hashlib
import hmac
import json
import logging
import os
import re
import unicodedata
from datetime import datetime, time
from django.db import connection, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from . import comprador, operador
from .exceptions import Conflict
from .models import AuditEvent, BuyerDraft, BuyerJourney, BuyerTouch, Conversation, MeetingBooking
from .permissions import require

log=logging.getLogger(__name__)
Kind=BuyerTouch.Kind;Step=BuyerJourney.Step;State=MeetingBooking.State;By=MeetingBooking.MatchedBy
CREATED='BOOKING_CREATED';RESCHEDULED='BOOKING_RESCHEDULED';CANCELLED='BOOKING_CANCELLED'
TRIGGERS=(CREATED,RESCHEDULED,CANCELLED)
MAX_BODY=64*1024
EVENT='calcom.event'          # one per delivery processed (target: the sha256 of its raw body)
UNMATCHED='calcom.unmatched'
REJECTED='calcom.rejected'
LOCK=0x63616c63               # pg_advisory_xact_lock: one delivery at a time
REF=re.compile(r'^[A-Za-z0-9_-]{8,40}$')
EMAIL=re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}$')

def secret():
    """CALCOM_WEBHOOK_SECRET: the secret set on the Cal.com webhook. Empty: every call is rejected."""
    return os.environ.get('CALCOM_WEBHOOK_SECRET','').strip()

def signed(raw,signature):
    """X-Cal-Signature-256 is HMAC-SHA256(CALCOM_WEBHOOK_SECRET, raw body) in hex; compared in constant time."""
    key=secret()
    if not key or not signature:return False
    expected=hmac.new(key.encode(),raw,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,str(signature).strip().lower())

def _audit(action,target,**metadata):
    operador._audit(None,action,target,**metadata)

def _rejected(why,now):
    """At most one audit row per local hour and reason: a flood of bad calls does not flood the table."""
    since=now.replace(minute=0,second=0,microsecond=0)
    if not AuditEvent.objects.filter(action=REJECTED,target=why,created_at__gte=since).exists():_audit(REJECTED,why)

def _text(value,limit):
    return value.strip()[:limit] if isinstance(value,str) else ''

def _at(value):
    if not isinstance(value,str):return None
    try:at=parse_datetime(value.strip())
    except ValueError:return None
    return at if at and at.tzinfo else None

def _fields(payload):
    """What the body may say, each value checked: the booking, its dates, the attendee and the link's identifier."""
    attendees=payload.get('attendees') if isinstance(payload.get('attendees'),list) else []
    first=attendees[0] if attendees and isinstance(attendees[0],dict) else {}
    metadata=payload.get('metadata') if isinstance(payload.get('metadata'),dict) else {}
    ref=_text(metadata.get('barrio'),40)
    email=_text(first.get('email'),254).lower()
    return {'uid':_text(payload.get('uid'),200),'previous':_text(payload.get('rescheduleUid') or payload.get('fromReschedule'),200),
            'start':_at(payload.get('startTime')),'end':_at(payload.get('endTime')),'name':_text(first.get('name'),200),
            'email':email if EMAIL.match(email) else '','ref':ref if REF.match(ref) else ''}

def receive(raw,signature,now=None):
    """The webhook: (HTTP status, body). 413 too large; 403 without a secret or with a bad signature; 202 with phase 6
    off (nothing stored); 400 not JSON or without a booking uid; 200 for anything else, processed once."""
    from . import respuesta_comprador
    now=now or timezone.now()
    if len(raw)>MAX_BODY:return 413,{'detail':'Cuerpo demasiado grande.'}
    if not secret():
        _rejected('sin_secreto',now);return 403,{'detail':'Webhook sin configurar.'}
    if not signed(raw,signature):
        _rejected('firma',now);return 403,{'detail':'Firma inválida.'}
    if not respuesta_comprador.enabled():return 202,{'ignorado':'BUYER_REPLY_ENABLED apagado'}
    try:body=json.loads(raw)
    except (ValueError,UnicodeDecodeError):return 400,{'detail':'JSON inválido.'}
    if not isinstance(body,dict):return 400,{'detail':'JSON inválido.'}
    trigger=body.get('triggerEvent')
    if trigger not in TRIGGERS:return 200,{'ignorado':str(trigger)[:60]}
    payload=body.get('payload') if isinstance(body.get('payload'),dict) else {}
    data=_fields(payload)
    if not data['uid']:return 400,{'detail':'La reserva no trae uid.'}
    digest=hashlib.sha256(raw).hexdigest()
    with transaction.atomic():
        with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_xact_lock(%s)',[LOCK])
        if AuditEvent.objects.filter(action=EVENT,target=digest).exists():return 200,{'repetido':True}
        event={'evento':trigger,'at':now.isoformat(),'cuerpo_sha256':digest}
        if trigger==CANCELLED:booking=_cancel(data,event,now)
        else:booking=_book(data,event,now,rescheduled=trigger==RESCHEDULED)
        _audit(EVENT,digest,evento=trigger,reserva=str(booking.pk),emparejada=booking.matched_by)
    return 200,{'reserva':str(booking.pk),'estado':booking.state,'emparejada_por':booking.matched_by}

# --------------------------------------------------------------------------- matching

def _norm(name):
    plain=unicodedata.normalize('NFKD',name or '').encode('ascii','ignore').decode()
    return ' '.join(re.findall(r'[a-z0-9]+',plain.lower()))

def _with_link():
    """The buyers who got her booking link (a booking_ref) and are still in the journey."""
    return BuyerJourney.objects.select_related('contact').filter(booking_ref__isnull=False).exclude(step=Step.LEFT,exit_reason__in=comprador.DEFINITIVE)

def _by_email(email):
    if not email:return None
    found=set()
    journeys={j.contact_id:j for j in _with_link()}
    for chat in Conversation.objects.filter(contact_id__in=list(journeys)):
        for message in chat.messages or []:
            if not message.get('from_me') and email in (message.get('text') or '').lower():found.add(chat.contact_id)
    return journeys[found.pop()] if len(found)==1 else None

def _by_name(name):
    key=_norm(name)
    if len(key.split())<2:return None  # a first name alone is never enough
    found=[j for j in _with_link() if _norm(j.contact.display_name)==key]
    return found[0] if len(found)==1 else None

def match(data,previous=None):
    """(journey, how) for a booking, or (None, sin_emparejar): the link's identifier, the booking it reschedules, her
    email in the conversation, her exact name with exactly one candidate."""
    if data['ref']:
        journey=BuyerJourney.objects.select_related('contact').filter(booking_ref=data['ref']).first()
        if journey:return journey,By.LINK
    if previous is not None and previous.journey_id:
        return BuyerJourney.objects.select_related('contact').get(pk=previous.journey_id),By.PREVIOUS
    journey=_by_email(data['email'])
    if journey:return journey,By.EMAIL
    journey=_by_name(data['name'])
    if journey:return journey,By.NAME
    return None,By.NONE

# --------------------------------------------------------------------------- what a booking changes

def _cancel_drafts(contact_id,now):
    """She booked: the drafts still waiting for her (Tu turno or the lead) no longer apply."""
    rows=list(BuyerDraft.objects.filter(contact_id=contact_id,state__in=[BuyerDraft.State.READY,BuyerDraft.State.REVIEWING]))
    for row in rows:
        row.state=BuyerDraft.State.CANCELLED;row.closed_at=now;row.closed_note='Agendó la reunión.'
        row.save(update_fields=['state','closed_at','closed_note'])
        _audit('buyer.draft_cancelled',row.contact_id,tipo=row.kind,numero=row.number,borrador=str(row.pk),motivo='Agendó la reunión.')
    return len(rows)

def booked(booking,journey,by,now,replaces=''):
    """The booking is hers: the journey moves to «reunion» with its date, her pending drafts are cancelled and the lead
    is handed over. Idempotent (the touches' keys are the booking's uid)."""
    from . import entrega_lead
    booking.journey=journey;booking.contact_id=journey.contact_id;booking.matched_by=by;booking.matched_at=now;booking.updated_at=now
    booking.save(update_fields=['journey','contact','matched_by','matched_at','updated_at'])
    journey=BuyerJourney.objects.select_related('contact').get(pk=journey.pk)
    if journey.interested_at is None:
        comprador.record(journey,Kind.INTERESTED,at=now,key=f'interesado:reserva:{booking.uid}',detail={'origen':'reserva','reserva':booking.uid})
    comprador.record(journey,Kind.MEETING,at=now,key=f'reunion:{booking.uid}',
                     detail={'reserva':booking.uid,'inicio':booking.start_at.isoformat() if booking.start_at else None,
                             'reemplaza':replaces,'origen':by})
    cancelled=_cancel_drafts(journey.contact_id,now)
    journey=BuyerJourney.objects.select_related('contact').get(pk=journey.pk)
    handoff=entrega_lead.build(journey,booking,now)
    _audit('buyer.meeting_booked',journey.contact_id,reserva=str(booking.pk),inicio=booking.start_at.isoformat() if booking.start_at else None,
           por=by,reprograma=replaces,borradores_cancelados=cancelled,entrega=str(handoff.pk) if handoff else '')
    comprador.on_contact(journey.contact,'reunion')
    return journey

def _book(data,event,now,rescheduled=False):
    previous=MeetingBooking.objects.select_for_update().filter(uid=data['previous']).first() if data['previous'] else None
    booking,created=MeetingBooking.objects.select_for_update().get_or_create(uid=data['uid'],defaults={
        'previous_uid':data['previous'],'start_at':data['start'],'end_at':data['end'],'attendee_name':data['name'],
        'attendee_email':data['email'],'ref':data['ref'],'created_at':now,'updated_at':now})
    booking.events=(list(booking.events)+[event])[-20:]
    if not created and booking.state==State.CANCELLED:
        booking.save(update_fields=['events']);return booking  # a late «created» never revives a cancelled booking
    if not created:
        booking.start_at=data['start'] or booking.start_at;booking.end_at=data['end'] or booking.end_at
    booking.updated_at=now;booking.save()
    if previous is not None and previous.pk!=booking.pk and previous.state==State.BOOKED:
        previous.state=State.RESCHEDULED;previous.updated_at=now;previous.events=(list(previous.events)+[dict(event,reemplazada_por=booking.uid)])[-20:]
        previous.save(update_fields=['state','updated_at','events'])
    if booking.journey_id:
        journey=BuyerJourney.objects.select_related('contact').get(pk=booking.journey_id)
        booked(booking,journey,booking.matched_by,now,replaces=previous.uid if previous else '')
        return booking
    journey,by=match(data,previous)
    if journey is None:
        _audit(UNMATCHED,str(booking.pk),nombre=data['name'][:80],inicio=data['start'].isoformat() if data['start'] else None,
               reprogramada=rescheduled)
        return booking
    booked(booking,journey,by,now,replaces=previous.uid if previous and previous.journey_id==journey.pk else '')
    return booking

def _cancel(data,event,now):
    from . import entrega_lead
    booking,_=MeetingBooking.objects.select_for_update().get_or_create(uid=data['uid'],defaults={
        'state':State.CANCELLED,'start_at':data['start'],'end_at':data['end'],'attendee_name':data['name'],'attendee_email':data['email'],
        'ref':data['ref'],'created_at':now,'updated_at':now})
    booking.events=(list(booking.events)+[event])[-20:];booking.updated_at=now
    if booking.state==State.RESCHEDULED:  # the reschedule already replaced it: nothing to cancel
        booking.save(update_fields=['events','updated_at']);return booking
    booking.state=State.CANCELLED;booking.save(update_fields=['state','events','updated_at'])
    if booking.journey_id:
        journey=BuyerJourney.objects.select_related('contact').get(pk=booking.journey_id)
        comprador.record(journey,Kind.MEETING_CANCELLED,at=now,key=f'reunion_cancelada:{booking.uid}',detail={'reserva':booking.uid})
        entrega_lead.cancelled(booking,now)
        _audit('buyer.meeting_cancelled',journey.contact_id,reserva=str(booking.pk))
        comprador.on_contact(journey.contact,'reunion')
    return booking

# --------------------------------------------------------------------------- Gustavo, by hand

DATE=re.compile(r'(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>20\d\d)(?:\s+(?P<h>\d{1,2})[:.](?P<mi>\d{2}))?')

def note_date(text):
    """A date in Gustavo's note («20/11/2026 10:30», «2026-11-20T10:30»), local time; None when there is none."""
    text=(text or '').strip()
    at=_at(text)
    if at:return at
    found=DATE.search(text)
    if not found:return None
    try:
        return datetime.combine(datetime(int(found['y']),int(found['m']),int(found['d'])).date(),
                                time(int(found['h'] or 9),int(found['mi'] or 0)),tzinfo=operador.local_tz())
    except ValueError:return None

def manual(user,draft_id,note_text=''):
    """«Agendó» on her reply card: Gustavo says she booked (by LinkedIn, by email…), with the date in the note if he
    knows it. The same as a matched booking (uid «manual:<reply>»); a second tap changes nothing."""
    require(user,'approve_actions')
    now=timezone.now()
    with transaction.atomic():
        row=BuyerDraft.objects.select_for_update().select_related('contact').filter(id=draft_id,kind=BuyerDraft.Kind.REPLY).first()
        if row is None:raise Conflict('Esta respuesta no existe.')
        journey=comprador.journey(row.contact)
        if journey is None or journey.attempt!=row.attempt:raise Conflict('Esta respuesta es de un intento anterior.')
        if journey.step==Step.LEFT and journey.exit_reason in comprador.DEFINITIVE:raise Conflict('Salió del recorrido de forma definitiva.')
        start=note_date(note_text)
        booking,created=MeetingBooking.objects.get_or_create(uid=f'manual:{row.pk}',defaults={
            'provider':'manual','start_at':start,'attendee_name':row.contact.display_name[:200],'created_at':now,'updated_at':now,
            'events':[{'evento':'manual','at':now.isoformat(),'nota':(note_text or '')[:300]}]})
        if created or booking.state!=State.BOOKED or not booking.journey_id:
            if booking.state!=State.BOOKED:booking.state=State.BOOKED;booking.save(update_fields=['state'])
            booked(booking,journey,By.MANUAL,now)
    operador._audit(user,'buyer.meeting_manual',row.contact_id,reserva=str(booking.pk),inicio=start.isoformat() if start else None)
    return booking

def associate(user,booking_id,journey_id=None,discard=False):
    """Gustavo associates a booking nobody matched with a buyer, or discards it (not a buyer's)."""
    require(user,'approve_actions')
    now=timezone.now()
    with transaction.atomic():
        booking=MeetingBooking.objects.select_for_update().filter(pk=booking_id).first()
        if booking is None:raise Conflict('La reserva no existe.')
        if booking.journey_id or booking.state!=State.BOOKED:raise Conflict('La reserva ya está emparejada, cancelada o descartada.')
        if discard:
            booking.state=State.DISCARDED;booking.matched_at=now;booking.updated_at=now
            booking.save(update_fields=['state','matched_at','updated_at'])
        else:
            journey=BuyerJourney.objects.select_related('contact').filter(pk=journey_id).first() if journey_id else None
            if journey is None:raise ValueError('recorrido debe ser el recorrido de un comprador')
            booked(booking,journey,By.GUSTAVO,now)
    operador._audit(user,'buyer.booking_associated',str(booking.pk),recorrido=str(journey_id or ''),descartada=bool(discard))
    return booking

# --------------------------------------------------------------------------- Tu turno and Slack

def unmatched():
    return MeetingBooking.objects.filter(state=State.BOOKED,journey__isnull=True).order_by('created_at')

def candidates(limit=5):
    """The buyers a booking may be from: who got the link and has not booked, latest reply first."""
    return list(_with_link().filter(step__in=[Step.REPLIED,Step.INTERESTED,Step.RESTING]).order_by('-last_inbound_at')[:limit])

def cards(card,now=None):
    """Tu turno: each booking nobody matched, with the buyers who got the link as buttons and «No es de un comprador»."""
    from . import respuesta_comprador
    if not respuesta_comprador.enabled():return []
    out=[];people=None
    for booking in unmatched():
        people=candidates() if people is None else people
        when=booking.start_at.astimezone(operador.local_tz()).strftime('%d/%m %H:%M') if booking.start_at else 'sin fecha'
        who=' · '.join(x for x in (booking.attendee_name,booking.attendee_email) if x) or 'sin nombre'
        endpoint=f'/api/v1/comprador/reservas/{booking.pk}/emparejar'
        actions=[{'label':f'Es {j.contact.display_name}','endpoint':endpoint,'body':{'recorrido':str(j.pk)}} for j in people]
        actions.append({'label':'No es de un comprador','endpoint':endpoint,'body':{'descartar':True}})
        out.append(card(f'reserva:{booking.pk}','aviso','Reserva de Cal.com sin emparejar',
                        f'{who} agendó para el {when} y el equipo no sabe de quién es: no trae el identificador de su enlace y ni '
                        'su correo ni su nombre coinciden con un comprador. Dile de quién es.',actions,agent='relaciones_comunidad',
                        priority='importante',created_at=booking.created_at,booking={'id':str(booking.pk),'inicio':booking.start_at}))
    return out
