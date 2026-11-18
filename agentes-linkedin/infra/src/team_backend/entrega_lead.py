"""Phase 6 of docs/plan-outbound.md (BAR-23): the lead handed over once the meeting is booked. The LinkedIn machine ends
here (Gustavo, 17/11/2026); qualifying the lead belongs to a future sales machine, so the handoff carries NO
qualification: only what happened and what the team knows, each business fact with its source.

LeadHandoff (models.py) is source-neutral: `fuente` is «linkedin» today and the shape is the one any other source (email,
an event…) would fill, so the sales machine reads every source the same way (GET /api/v1/comprador/entregas; contract in
oficina/CONTRATO-API.md). A model and not a JSON on the journey: the sales machine reads it by state, and the
opportunity, the conversation and the journey hang from it.

Only Gustavo creates the opportunity (PRS-09): the handoff's Tu turno card «Crear la oportunidad» does it with one tap
(stage «reunion», channel LinkedIn, the meeting as its next action), or links the open opportunity he already has with
that person. An opportunity he creates by hand from Personas links the handoff too (on_opportunity)."""
from django.db import transaction
from django.utils import timezone
from . import alcance, comprador, identidad, operador
from .exceptions import Conflict
from .models import BuyerDraft, BuyerTouch, Contact, LeadHandoff, Opportunity
from .permissions import require

Kind=BuyerTouch.Kind;State=LeadHandoff.State
CLOSED=('acuerdo','sin_acuerdo')
LINE=200  # each of the conversation's three lines, at most

def _iso(at):
    return at.isoformat() if at else None

def _day(at):
    return at.astimezone(operador.local_tz()).strftime('%d/%m/%Y') if at else 'sin fecha'

def _short(text,limit=LINE):
    text=' '.join((text or '').split())
    return text if len(text)<=limit else text[:limit-1].rstrip()+'…'

# --------------------------------------------------------------------------- what the handoff says

def _sent(journey,state):
    """What Gustavo sent her in this attempt (the journey's messages and his replies), oldest first."""
    from . import secuencia_comprador
    out=[{'numero':m['numero'],'texto':m['texto'],'enviado':m['enviado'],'tipo':'mensaje'}
         for m in secuencia_comprador.previous(journey,state)]
    for d in BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=BuyerDraft.Kind.REPLY,attempt=journey.attempt,
                                       state=BuyerDraft.State.SENT).order_by('closed_at'):
        out.append({'numero':d.number,'texto':d.text,'enviado':_iso(d.closed_at),'tipo':'respuesta'})
    return sorted(out,key=lambda m:m['enviado'] or '')

def _her_reply(journey):
    """Her first reply of the attempt the team classified: {tipo, texto, fecha}."""
    row=(BuyerDraft.objects.filter(contact_id=journey.contact_id,kind=BuyerDraft.Kind.REPLY,attempt=journey.attempt)
         .order_by('number').first())
    if row is None:return None
    message=(row.inputs or {}).get('mensaje') or {}
    return {'tipo':((row.inputs or {}).get('clasificacion') or {}).get('tipo',''),'texto':message.get('texto',''),'fecha':message.get('at')}

def _entry(journey,state):
    contact=journey.contact;signals=sorted(state.inbound,key=lambda t:t.at)
    first=signals[0] if signals else None
    return {'entrada':journey.entry,'ruta':journey.route,'elegida':_iso(journey.chosen_at),
            'motivo':_short((contact.classification or {}).get('reason',''),300),
            'senal':{'tipo':first.kind,'nombre':comprador.signal_name(first.kind,contact.account),'fecha':_iso(first.at)} if first else None}

def _touches(state,touches):
    counts={}
    for t in touches:
        if t.direction==BuyerTouch.Direction.OUT:counts[t.kind]=counts.get(t.kind,0)+1
    return {'total':sum(counts.values()),'por_tipo':counts,'comentarios':len(state.comments),'visitas':state.visits}

def _bridge(journey):
    """Phase 5: the colleague of her company the team went through (sin_posts), if any."""
    return [{'contacto':str(c.pk),'nombre':c.display_name,'titular':_short(c.headline,200)} for c in Contact.objects.filter(bridge_for=journey)]

def _business(contact,journey):
    """What the team knows of her business, each fact with its source: her company (headline), the buying signals the
    web check cited, and her posts the team read."""
    from . import calentamiento, sin_posts
    from .mensajes_comprador import anchors
    out=[];company=sin_posts.company_of(contact.headline)
    if company:out.append({'hecho':f'Trabaja en {company}: {_short(contact.headline,160)}','fuente':'titular de LinkedIn'})
    for s in calentamiento.buying_signals(contact):
        out.append({'hecho':_short(s.get('evidencia') or s.get('tipo',''),300),'fuente':s.get('fuente') or ''})
    for fact in anchors(contact,journey):
        if fact.get('tipo') in ('respondio_comentario','comentario_en_su_post','comento_post','nos_invito'):
            out.append({'hecho':_short(fact.get('texto',''),300),'fuente':fact.get('fuente') or fact.get('tipo')})
    seen=set();unique=[]
    for f in out:
        if f['hecho'] and f['hecho'] not in seen:seen.add(f['hecho']);unique.append(f)
    return unique[:8]

def _lines(sent,reply,booking,owner):
    """The conversation in three lines, from what happened (no model): the member's first message (`owner`: her name,
    identidad.owner_name), her reply, the booking."""
    first=sent[0] if sent else None
    one=(f'{owner} le escribió el {_day(comprador._when(first["enviado"]))}: «{_short(first["texto"],140)}»' if first and first['texto']
         else f'{owner} le escribió por LinkedIn.')
    two=(f'Ella respondió el {_day(comprador._when(reply["fecha"]))} ({reply["tipo"] or "sin clasificar"}): «{_short(reply["texto"],140)}»'
         if reply and reply.get('texto') else 'Ella respondió en LinkedIn.')
    how='la reunión por Cal.com' if booking.provider=='calcom' else f'la reunión ({owner} marcó «Agendó»)'
    three=f'Agendó {how} para el {_day(booking.start_at)}.' if booking.start_at else f'Agendó {how}.'
    return [_short(one),_short(two),_short(three)]

def data(journey,booking):
    """The handoff's content: who and her company, the journey, the conversation in three lines, the meeting and the
    business facts with their sources. No qualification (the sales machine's)."""
    contact=journey.contact
    touches=comprador.current(comprador._touches(journey));state=comprador._fold(touches)
    sent=_sent(journey,state);reply=_her_reply(journey)
    replied=comprador._when((reply or {}).get('fecha'))
    answered=[m for m in sent if replied and comprador._when(m['enviado']) and comprador._when(m['enviado'])<=replied]
    referrer=journey.referred_by
    from . import sin_posts
    company=sin_posts.company_of(contact.headline)
    return {'persona':{'contacto':str(contact.pk),'nombre':contact.display_name,'titular':contact.headline,'perfil':contact.profile_url,
                       'ubicacion':contact.location},
            'empresa':{'nombre':company,'fuente':'titular de LinkedIn' if company else ''},
            'recorrido':{'senal_de_entrada':_entry(journey,state),'toques':_touches(state,touches),
                         'mensajes_enviados':sent,'respondio_a':answered[-1] if answered else None,'respuesta':reply,
                         'puente':_bridge(journey),
                         'referido_por':{'contacto':str(referrer.contact_id),'nombre':referrer.contact.display_name} if referrer else None,
                         'intento':journey.attempt},
            'conversacion':_lines(sent,reply,booking,identidad.owner_name(contact.account)),
            'reunion':{'inicio':_iso(booking.start_at),'fin':_iso(booking.end_at),'proveedor':booking.provider,'reserva':booking.uid,
                       'emparejada_por':booking.matched_by,'correo':booking.attendee_email,'nombre':booking.attendee_name},
            'negocio':_business(contact,journey)}

def build(journey,booking,now=None):
    """The handoff of this journey's attempt, created once and refreshed with each booking (a reschedule moves its
    date; a new booking after a cancellation makes it ready again)."""
    from . import conversaciones
    now=now or timezone.now()
    content=data(journey,booking)
    chat=conversaciones.for_contact(journey.contact)
    with transaction.atomic():
        handoff,created=LeadHandoff.objects.select_for_update().get_or_create(key=f'linkedin:{journey.pk}:{journey.attempt}',defaults={
            'contact':journey.contact,'journey':journey,'booking':booking,'conversation':chat,'meeting_at':booking.start_at,'data':content,
            'created_at':now,'updated_at':now})
        if not created:
            handoff.booking=booking;handoff.conversation=chat or handoff.conversation;handoff.meeting_at=booking.start_at
            handoff.data=content;handoff.updated_at=now
            if handoff.state==State.CANCELLED:handoff.state=State.CONFIRMED if handoff.opportunity_id else State.READY
            handoff.save()
    if created:operador._audit(None,'lead.handoff_ready',str(handoff.pk),contacto=str(journey.contact_id),fuente=handoff.source)
    return handoff

def cancelled(booking,now=None):
    """The meeting was cancelled: its handoff too (the opportunity, if Gustavo created it, stays his to move)."""
    now=now or timezone.now()
    for handoff in LeadHandoff.objects.select_for_update().filter(booking=booking).exclude(state=State.CANCELLED):
        handoff.state=State.CANCELLED;handoff.updated_at=now
        handoff.data={**handoff.data,'reunion':{**(handoff.data.get('reunion') or {}),'cancelada':_iso(now)}}
        handoff.save(update_fields=['state','updated_at','data'])
        operador._audit(None,'lead.handoff_cancelled',str(handoff.pk),contacto=str(handoff.contact_id))

# --------------------------------------------------------------------------- the opportunity: only Gustavo

def _open(contact):
    return Opportunity.objects.filter(contact=contact).exclude(stage__in=CLOSED).order_by('-created_at').first() if contact else None

def _modality(handoff):
    judged=(handoff.conversation.assessment or {}) if handoff.conversation_id else {}
    value=judged.get('modality')
    return value if value in (Opportunity.Modality.PERSONAL,Opportunity.Modality.PROJECTAPP) else Opportunity.Modality.UNKNOWN

def _link(handoff,item,now):
    handoff.opportunity=item;handoff.state=State.CONFIRMED;handoff.confirmed_at=now;handoff.updated_at=now
    handoff.save(update_fields=['opportunity','state','confirmed_at','updated_at'])

def confirm(user,handoff_id):
    """«Crear la oportunidad»: Gustavo's one tap (PRS-09). Links the open opportunity he already has with her, or creates
    one at stage «reunion» (channel LinkedIn, the meeting as its next action, modality from the inbox's read or «por
    clasificar»). Idempotent."""
    require(user,'approve_actions')
    from . import oportunidades
    now=timezone.now()
    with transaction.atomic():
        handoff=LeadHandoff.objects.select_for_update(of=('self',)).select_related('contact','conversation').filter(pk=handoff_id).first()
        if handoff is None:raise Conflict('La entrega no existe.')
        if handoff.state==State.CANCELLED:raise Conflict('La reunión se canceló: no hay entrega que confirmar.')
        if handoff.opportunity_id:return handoff
        item=_open(handoff.contact)
        if item is None:
            company=(handoff.data.get('empresa') or {}).get('nombre','')
            item=oportunidades.create(user,{'contact':str(handoff.contact_id),'modality':_modality(handoff),'channel':'linkedin',
                                            'stage':Opportunity.Stage.MEETING,'company':company,'next_action':'Reunión agendada (Cal.com)',
                                            'next_action_at':handoff.meeting_at,
                                            'notes':'Entrega de la máquina de LinkedIn: '+' / '.join(handoff.data.get('conversacion') or [])})
            handoff.refresh_from_db()
        if not handoff.opportunity_id:_link(handoff,item,now)
        if handoff.contact_id:comprador.on_contact(handoff.contact,'oportunidad')
    operador._audit(user,'lead.handoff_confirmed',str(handoff.pk),oportunidad=str(item.pk),contacto=str(handoff.contact_id))
    return handoff

def on_opportunity(item):
    """oportunidades.create: an opportunity Gustavo created for a person whose lead is waiting links that handoff."""
    if not item.contact_id:return
    now=timezone.now()
    with transaction.atomic():
        for handoff in LeadHandoff.objects.select_for_update().filter(contact_id=item.contact_id,state=State.READY,opportunity__isnull=True):
            _link(handoff,item,now)
            operador._audit(None,'lead.handoff_linked',str(handoff.pk),oportunidad=str(item.pk))

# --------------------------------------------------------------------------- read

def payload(handoff):
    """The handoff as the sales machine reads it (GET /api/v1/comprador/entregas): source-neutral."""
    item=handoff.opportunity
    return {'id':str(handoff.pk),'fuente':handoff.source,'estado':handoff.state,**{k:handoff.data.get(k) for k in
            ('persona','empresa','recorrido','conversacion','reunion','negocio')},
            'oportunidad':{'id':str(item.pk),'etapa':item.stage} if item else None,
            'recorrido_id':str(handoff.journey_id) if handoff.journey_id else None,
            'conversacion_id':str(handoff.conversation_id) if handoff.conversation_id else None,
            'creada':_iso(handoff.created_at),'actualizada':_iso(handoff.updated_at),'confirmada':_iso(handoff.confirmed_at)}

def listing(state=None,source=None,limit=100,member=None):
    """Her handoffs (alcance.de: those of her buyers; a handoff without a person is the first member's)."""
    rows=alcance.de(LeadHandoff.objects.all(),member).select_related('opportunity').order_by('-created_at')
    if state:
        if state not in State.values:raise ValueError('estado debe ser lista, confirmada o cancelada')
        rows=rows.filter(state=state)
    if source:
        if source not in LeadHandoff.Source.values:raise ValueError('fuente desconocida')
        rows=rows.filter(source=source)
    return [payload(h) for h in rows[:limit]]

def cards(card,now=None,member=None):
    """Tu turno: each lead of hers ready to hand over, with «Crear la oportunidad» (or «Vincular la oportunidad») first."""
    from . import respuesta_comprador
    if not respuesta_comprador.enabled():return []
    out=[]
    for handoff in alcance.de(LeadHandoff.objects.all(),member).select_related('contact').filter(state=State.READY).order_by('created_at'):
        contact=handoff.contact
        if contact is None:continue
        name=contact.display_name or 'Alguien';existing=_open(contact)
        endpoint=f'/api/v1/comprador/entregas/{handoff.pk}/oportunidad'
        actions=[{'label':'Vincular su oportunidad' if existing else 'Crear la oportunidad','endpoint':endpoint,'body':{},'primary':True},
                 {'label':'Ver la persona','href':f'/personas/{contact.pk}'}]
        lines=handoff.data.get('conversacion') or []
        body=(f'Reunión agendada para el {_day(handoff.meeting_at)}. La máquina de LinkedIn terminó aquí: el lead queda listo para '
              'ventas, sin calificar. '+' '.join(lines[:2])+(' Ya tienes una oportunidad abierta con ella: vincúlala con un toque.' if existing
              else ' Crea la oportunidad con un toque: solo tú la creas.'))
        out.append(card(f'entrega:{handoff.pk}','aviso',f'Reunión agendada con {name}',body,actions,agent='relaciones_comunidad',
                        priority='importante',created_at=handoff.created_at,handoff={'id':str(handoff.pk),'contacto':str(contact.pk)}))
    return out
