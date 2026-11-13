"""API of the redesigned office (oficina/PLAN-REDISENO.md and DISENO-VISTAS.md): Tu turno, team questions, what the
team knows, orientation, opportunities, the calendar with its list view, and settings. Decisions need a human
session with CSRF; a service token can read but never decide."""
import os
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from knowledge import db
from . import autopiloto, editorial, imagenes, lider, notificaciones, operador, oportunidades, orientacion, preguntas, red
from .models import (ActionExecution, ActionProposal, AuditEvent, ConnectorAccount, Contact, EditorialPiece, Opportunity,
                     OPEN_ACTION_STATES, OperatorControl, TeamQuestion)
from .operador_views import get_or_404, human_session, valid
from .permissions import require
from . import expo
from .movil_views import devices_payload

LABELS={'INT-03':'Comentario','INT-04':'Respuesta en tu post','INT-02':'Reacción','CONT-09':'Publicación','RED-01':'Seguimiento',
        'RED-02':'Invitación sin nota','RED-04':'Invitación aceptada'}
TYPES={'publicaciones':['CONT-09'],'comentarios':['INT-03','INT-04'],'respuestas':['INT-04'],'reacciones':['INT-02'],'red':['RED-01','RED-02','RED-04'],
       'seguimientos':['RED-01'],'invitaciones':['RED-02'],'aceptaciones':['RED-04']}
ACTOR={'INT-03':'relaciones_comunidad','INT-04':'relaciones_comunidad','INT-02':'relaciones_comunidad','CONT-09':'director_editorial',
       'RED-01':'relaciones_comunidad','RED-02':'relaciones_comunidad','RED-04':'relaciones_comunidad'}
STATE_LABELS={'confirmed':None,'executing':'En curso','sent':'En curso','uncertain':'Incierta','failed':'Fallida',
              'rejected':'Vetada por ti','discarded':'Descartada por la política','expired':'Caducada','superseded':'Sustituida'}
NOT_DONE=('rejected','discarded','expired','superseded')
COUNT_KEYS={'INT-03':'comments','INT-04':'replies','INT-02':'reactions','RED-01':'follows','RED-02':'invites','RED-04':'accepts'}

def local_day(value):
    return value.astimezone(operador.local_tz()).date() if value else None

def day_bounds(day):
    tz=operador.local_tz()
    start=datetime.combine(day,time.min,tzinfo=tz)
    return start,start+timedelta(days=1)

def parse_range(params,default_days=31,max_days=93):
    today=timezone.now().astimezone(operador.local_tz()).date()
    try:
        start=date.fromisoformat(params['desde']) if params.get('desde') else today.replace(day=1)
        end=date.fromisoformat(params['hasta']) if params.get('hasta') else start+timedelta(days=default_days-1)
    except ValueError:raise ValidationError('Fechas inválidas: desde y hasta en formato AAAA-MM-DD') from None
    if end<start or (end-start).days>=max_days:raise ValidationError(f'El rango debe ir de desde a hasta y durar como mucho {max_days} días')
    return start,end,today

# --------------------------------------------------------------------------- serializers

class QuestionOutput(serializers.ModelSerializer):
    agent_label=serializers.SerializerMethodField()
    pending=serializers.SerializerMethodField()
    expired=serializers.SerializerMethodField()
    def get_agent_label(self,obj):return preguntas.agent_label(obj.agent)
    def get_pending(self,obj):return preguntas.is_pending(obj)
    def get_expired(self,obj):return bool(obj.state=='open' and obj.deadline and obj.deadline<timezone.now())
    class Meta:
        model=TeamQuestion
        fields=['id','kind','agent','agent_label','question','purpose','answer_type','options','memory_key','proposed_value','suggested_public',
                'deadline','postponed_until','pending','expired','origin','state','answer','public_use','answered_at','created_at']

class AnswerInput(serializers.Serializer):
    text=serializers.CharField(required=False,allow_blank=True,max_length=preguntas.MAX_ANSWER)
    value=serializers.CharField(required=False,allow_blank=True,max_length=200)
    public_use=serializers.BooleanField(required=False,allow_null=True,default=None)
    accept=serializers.BooleanField(required=False,default=False)

class FactInput(serializers.Serializer):
    text=serializers.CharField(max_length=preguntas.MAX_ANSWER)
    public_use=serializers.BooleanField(default=False)

class AddFactInput(FactInput):
    topic=serializers.CharField(required=False,allow_blank=True,max_length=200)

class RetireInput(serializers.Serializer):
    reason=serializers.CharField(required=False,allow_blank=True,max_length=500)

class OrientationInput(serializers.Serializer):
    text=serializers.CharField(allow_blank=True,max_length=orientacion.MAX_CHARS)

class OpportunityOutput(serializers.ModelSerializer):
    contact=serializers.SerializerMethodField()
    person=serializers.SerializerMethodField()
    days_in_stage=serializers.SerializerMethodField()
    def get_contact(self,obj):
        c=obj.contact
        return {'id':str(c.id),'display_name':c.display_name,'headline':c.headline,'profile_url':c.profile_url,'stage':c.stage,
                'role':(c.classification or {}).get('role')} if c else None
    def get_person(self,obj):return obj.contact.display_name if obj.contact else obj.person_name
    def get_days_in_stage(self,obj):return (timezone.now()-obj.stage_changed_at).days
    class Meta:
        model=Opportunity
        fields=['id','person','contact','person_name','company','modality','channel','stage','attribution','need','budget','dedication',
                'next_action','next_action_at','notes','history','days_in_stage','created_at','updated_at','stage_changed_at','closed_at']

class OpportunityInput(serializers.Serializer):
    contact=serializers.UUIDField(required=False,allow_null=True)
    person_name=serializers.CharField(required=False,allow_blank=True,max_length=200)
    company=serializers.CharField(required=False,allow_blank=True,max_length=200)
    modality=serializers.ChoiceField(choices=Opportunity.Modality.values)
    channel=serializers.ChoiceField(choices=Opportunity.Channel.values,default='linkedin')
    stage=serializers.ChoiceField(choices=Opportunity.Stage.values,default='conversacion')
    attribution=serializers.ChoiceField(choices=Opportunity.Attribution.values,default='desconocido')
    need=serializers.CharField(required=False,allow_blank=True)
    budget=serializers.CharField(required=False,allow_blank=True,max_length=200)
    dedication=serializers.CharField(required=False,allow_blank=True,max_length=200)
    next_action=serializers.CharField(required=False,allow_blank=True,max_length=300)
    next_action_at=serializers.DateTimeField(required=False,allow_null=True)
    notes=serializers.CharField(required=False,allow_blank=True)

class OpportunityPatch(OpportunityInput):
    modality=serializers.ChoiceField(choices=Opportunity.Modality.values,required=False)
    channel=serializers.ChoiceField(choices=Opportunity.Channel.values,required=False)
    stage=serializers.ChoiceField(choices=Opportunity.Stage.values,required=False)
    attribution=serializers.ChoiceField(choices=Opportunity.Attribution.values,required=False)

# --------------------------------------------------------------------------- Tu turno

PRIORITY_ORDER={'urgente':0,'importante':1,'cuando_puedas':2}
PRIORITY_TONE={'urgente':'bad','importante':'warn','cuando_puedas':'info'}

def _card(id,kind,title,body,actions,critical=False,tone=None,agent='operador_cuenta',deadline=None,created_at=None,priority=None,**extra):
    """A Tu turno card. priority: urgente (something breaks without Gustavo) | importante | cuando_puedas (rev 18)."""
    priority=priority or ('urgente' if critical else 'importante')
    return dict({'id':id,'type':kind,'priority':priority,'critical':priority=='urgente','tone':tone or PRIORITY_TONE[priority],'agent':agent,
                 'agent_label':'Operador de cuenta' if agent=='operador_cuenta' else preguntas.agent_label(agent),
                 'title':title,'body':body,'deadline':deadline,'actions':actions,'created_at':created_at,'state':'nueva'},**extra)

def alerts(now=None):
    """Tu turno → Avisos: only what breaks without Gustavo, each with its action (DISENO-VISTAS, sección 2.A).
    Informative states (invitations limited, a blocked piece, the budget) live in Personas, Calendario and Ajustes."""
    from . import connectors_linkedin as li
    now=now or timezone.now();out=[]
    status=li.status_payload()
    # status_payload reports `connected` only while the token is valid: an expired one has `expired` alone.
    if status.get('expired'):
        out.append(_card('linkedin_expired','aviso','Reconecta LinkedIn','El acceso caducó y la publicación diaria está en pausa.',
                         [{'label':'Reconectar LinkedIn','href':'/api/v1/linkedin/oauth/start','primary':True}],critical=True,tone='bad',
                         expires_at=status.get('expires_at')))
    elif status.get('connected') and status.get('expiring_soon'):
        days=status.get('days_left')
        out.append(_card('linkedin_expiring','aviso','Reconecta LinkedIn',
                         f'El permiso para publicar caduca el {status.get("expires_at")} (quedan {status.get("days_left")} días). LinkedIn no deja renovarlo solo.',
                         [{'label':'Reconectar LinkedIn','href':'/api/v1/linkedin/oauth/start','primary':True}],deadline=status.get('expires_at'),
                         priority='importante' if days is not None and days<=3 else 'cuando_puedas',
                         expires_at=status.get('expires_at'),days_left=days))
    for p in ActionProposal.objects.select_related('post','contact','execution','comment__piece').filter(state='uncertain').order_by('created_at'):
        execution=getattr(p,'execution',None) if hasattr(p,'execution') else None
        target=_target(p)
        out.append(_card(f'uncertain:{p.id}','aviso','¿Salió o no?','El proveedor no confirmó si se aplicó. Comprueba en LinkedIn.',
            [{'label':'Sí, se aplicó','endpoint':f'/api/v1/operador/actions/{p.id}/resolve','body':{'outcome':'confirmed'},'note_required':True,'primary':True},
             {'label':'No se aplicó','endpoint':f'/api/v1/operador/actions/{p.id}/resolve','body':{'outcome':'failed'},'note_required':True}],
            critical=True,tone='bad',created_at=execution.started_at if execution else p.created_at,proposal_id=str(p.id),
            attempt={'capability':p.capability,'label':LABELS.get(p.capability,p.capability),'text':p.payload.get('text'),
                     'reaction':p.payload.get('reaction'),'target':target,'at':execution.started_at if execution else None,
                     'url':(execution.external_url if execution and execution.external_url else target['url'])}))
    # A stop set on the server cannot be solved from the app: it is a Notificación (notificaciones.upcoming), not a card.
    if not operador.env_paused():
        control=OperatorControl.objects.filter(pk=1,paused=True).first()
        if control:
            out.append(_card('machine_paused','aviso','Reanuda la máquina',control.reason or 'Sin motivo registrado.',
                [{'label':'Reanudar','endpoint':'/api/v1/operador/control','body':{'paused':False},'note_required':False,'primary':True}],
                critical=True,tone='bad',created_at=control.updated_at,stopped_by=control.updated_by.get_username() if control.updated_by else None))
    for account in ConnectorAccount.objects.filter(paused=True):
        # Paused only because the token expired: «Reconecta LinkedIn» above is the card; resuming would not help.
        if status.get('expired') and (account.paused_reason or '').startswith(li.TOKEN_PAUSE):continue
        out.append(_card(f'account_paused:{account.id}','aviso','Reanuda la cuenta de LinkedIn',f'{account.label}: {account.paused_reason or "sin motivo registrado"}',
            [{'label':'Reanudar la cuenta','endpoint':f'/api/v1/operador/accounts/{account.id}/pause','body':{'paused':False},'primary':True}],
            priority='importante'))
    return out

def _conversation_card(conversation,now):
    """C2 «Conversación que te toca» (DISENO-VISTAS 2.C2): who wrote, the team's read, the latest message and the links.
    Gustavo answers on LinkedIn himself; «Marcar como oportunidad» opens the opportunity form, prefilled."""
    from . import conversaciones
    contact=conversation.contact;inbound=conversaciones.latest_inbound(conversation)
    name=conversation.attendee_name or (contact.display_name if contact else 'Alguien')
    close=f'/api/v1/conversaciones/{conversation.id}/cerrar'
    actions=[{'label':'Abrir en LinkedIn','href':conversaciones.chat_url(conversation.provider_chat_id),'primary':True},
             {'label':'Hecho, respondí','endpoint':close,'body':{'how':'respondi'}}]
    if contact and not contact.opportunities.exclude(stage__in=oportunidades.CLOSED).exists():
        actions.append({'label':'Marcar como oportunidad','opportunity':{'contact':str(contact.id),'display_name':contact.display_name,
                        'headline':contact.headline,'modality':(conversation.assessment or {}).get('modality'),'channel':'linkedin',
                        'notes':'Detectada por el equipo en una conversación de LinkedIn.'}})
    actions.append({'label':'No responder','endpoint':close,'body':{'how':'no_responder'},'note_optional':True})
    person={'id':str(contact.id),'display_name':contact.display_name,'headline':contact.headline,'profile_url':contact.profile_url,
            'role':(contact.classification or {}).get('role'),'modality':(contact.classification or {}).get('modality')} if contact else None
    return _card(conversaciones.card_id(conversation),'conversacion',f'{name} te escribió',conversaciones.why(conversation),actions,
                 agent='conversaciones_inbox',priority='importante',created_at=conversaciones._at(inbound.get('at')) if inbound else conversation.last_message_at,
                 conversation=dict(conversaciones.payload(conversation,now),person=person))

def _summary_card(summary):
    """«El analista propone una orientación» (cuando puedas): only while the latest weekly summary's proposal waits for
    Gustavo. He decides in Resultados, where «Usar como orientación» can be undone; here he can only open it or discard it."""
    from . import resumen_semanal
    analysis=summary.analysis or {}
    return _card(f'weekly_summary:{summary.id}','resumen','El analista propone una orientación',analysis.get('orientacion_propuesta') or '',
                 [{'label':'Ver el resumen','href':'/resultados#resumen','primary':True},
                  {'label':'Descartar','endpoint':f'/api/v1/resultados/resumen-semanal/{summary.id}/descartar'}],
                 agent=resumen_semanal.ROLE,priority='cuando_puedas',created_at=summary.created_at,
                 summary={'id':str(summary.id),'week_start':summary.week_start,'label':resumen_semanal.payload(summary)['label'],
                          'titular':analysis.get('titular')})

APPROVAL_TITLE={'RED-01':'¿Apruebas seguir a {name}?','RED-02':'¿Apruebas invitar a {name}?','RED-04':'¿Apruebas aceptar la invitación de {name}?',
                'INT-03':'¿Apruebas el comentario en el post de {name}?','INT-02':'¿Apruebas la reacción al post de {name}?',
                'INT-04':'¿Apruebas la respuesta a {name} en tu post?','INT-02:comment':'¿Apruebas la reacción al comentario de {name}?'}
APPROVAL_SENTENCE={'RED-01':'Seguir a {name}','RED-02':'Invitar a {name} (sin nota)','RED-04':'Aceptar la invitación de {name}',
                   'INT-03':'Comentario en el post de {name}','INT-02':'Reacción al post de {name}',
                   'INT-04':'Respuesta a {name} en tu post','INT-02:comment':'Reacción al comentario de {name} en tu post'}

def approval_key(p):
    """A reaction to a comment on his own post reads differently from a reaction to someone else's post."""
    return f'{p.capability}:comment' if p.comment_id and p.capability=='INT-02' else p.capability

def awaiting_approval():
    """Proposals that wait for Gustavo: still `proposed`, never executed, of a capability in `approval` mode (the policy
    leaves them alone, autopiloto.policy_review). Each is a Tu turno card and a row of the calendar's «En cola»."""
    rows=ActionProposal.objects.select_related('post','piece','contact','comment__piece').filter(state='proposed',execution__isnull=True).order_by('created_at')
    return [p for p in rows if autopiloto.autonomy(p.capability)=='approval']

def approval_expiry(p):
    """When it stops waiting: an own piece at its hour; anything else when the autopilot lets it expire (TTL)."""
    if p.piece_id:return p.piece.scheduled_for
    return p.created_at+timedelta(hours=int(os.environ.get('OPERATOR_PROPOSAL_TTL_HOURS','48')))

def approval_sentence(p):
    if p.capability=='CONT-09':return f'La pieza del {p.piece.slot_date:%d/%m}' if p.piece_id else 'Una publicación'
    return APPROVAL_SENTENCE.get(approval_key(p),LABELS.get(p.capability,p.capability)+' · {name}').format(name=_target(p)['name'] or 'una persona')

def _approval_card(p):
    """«¿Apruebas seguir a Laura Gómez?» (importante): Aprobar sends the exact version (`expected_hash`); Vetar asks for
    a note and, on a network action, discards the person for good. A piece links to its detail, a person to her card."""
    target=_target(p)
    title=(f'¿Apruebas la pieza del {p.piece.slot_date:%d/%m}?' if p.piece_id else '¿Apruebas la publicación?') if p.capability=='CONT-09' else \
        APPROVAL_TITLE.get(approval_key(p),'¿Apruebas esta acción?').format(name=target['name'] or 'esta persona')
    actions=[{'label':'Aprobar','endpoint':f'/api/v1/operador/actions/{p.id}/approve','body':{'expected_hash':p.payload_hash},'primary':True},
             {'label':'Vetar','endpoint':f'/api/v1/operador/actions/{p.id}/reject','note_required':True}]
    if p.piece_id:actions.append({'label':'Ver la pieza','href':f'/calendario/pieza/{p.piece_id}'})
    elif target.get('contact_id'):actions.append({'label':'Ver ficha','href':f'/personas/{target["contact_id"]}'})
    expires=approval_expiry(p)
    return _card(f'approval:{p.id}','aprobacion',title,p.rationale or 'El equipo lo propone y espera tu aprobación.',actions,
                 agent=ACTOR.get(p.capability,'operador_cuenta'),priority='importante',deadline=expires,created_at=p.created_at,
                 approval={'proposal_id':str(p.id),'capability':p.capability,'label':LABELS.get(p.capability,p.capability),'text':p.payload.get('text'),
                           'reaction':p.payload.get('reaction'),'target':target,'piece_id':str(p.piece_id) if p.piece_id else None,
                           'network':p.capability.startswith('RED-'),'expires_at':expires})

def _question_priority(q,now):
    """Rises to Importante when less than 48 h remain before its deadline (rev 18 «Escalada»)."""
    return 'importante' if q.deadline and now<=q.deadline<=now+timedelta(hours=48) else 'cuando_puedas'

def _question_card(q,now=None):
    now=now or timezone.now()
    data=QuestionOutput(q).data
    state=('caducada' if data['expired'] else 'pospuesta' if q.postponed_until and q.postponed_until>now else 'nueva')
    return _card(f'question:{q.id}','pregunta',q.question,q.purpose,[
        {'label':'Responder','endpoint':f'/api/v1/preguntas/{q.id}/responder','primary':True},
        {'label':'Más tarde','endpoint':f'/api/v1/preguntas/{q.id}/mas-tarde'},
        {'label':'No quiero compartir esto','endpoint':f'/api/v1/preguntas/{q.id}/no-compartir'}],
        tone=None if data['pending'] else 'muted',priority=_question_priority(q,now),agent=q.agent,deadline=q.deadline,created_at=q.created_at,
        question=data,state_override=state)

def _today_summary(now):
    day,_=operador.period_starts(now);done={}
    for capability,key in list(COUNT_KEYS.items())+[('CONT-09','posts')]:
        n=ActionProposal.objects.filter(capability=capability,state='confirmed',execution__finished_at__gte=day).count()
        if n:done[key]=n
    upcoming=EditorialPiece.objects.filter(state='ready',scheduled_for__gt=now).order_by('scheduled_for').first()
    return {'done_today':done,'next_piece':{'id':str(upcoming.id),'scheduled_for':upcoming.scheduled_for} if upcoming else None}

def _with_state(cards,seen):
    for card in cards:
        override=card.pop('state_override',None)
        card['state']=override if override in ('pospuesta','caducada') else ('vista' if card['id'] in seen else 'nueva')
    return cards

def _ordered(cards):
    """Priority first; inside each group, what has a deadline (nearest first), then the most recent."""
    far=datetime.max.replace(tzinfo=dt_timezone.utc)
    def deadline(c):
        d=c.get('deadline')
        if isinstance(d,str):
            try:d=datetime.fromisoformat(d.replace('Z','+00:00'))
            except ValueError:d=None
        return d or far
    def recent(c):
        d=c.get('created_at')
        return -(d.timestamp() if hasattr(d,'timestamp') else 0)
    return sorted(cards,key=lambda c:(PRIORITY_ORDER[c['priority']],deadline(c),recent(c)))

class TuTurno(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        from . import notificaciones
        from .models import InboxSeen
        preguntas.sync_memory_proposals()
        now=timezone.now();warnings=alerts(now)
        from .orquestacion import attention_cards
        warnings+=attention_cards(request.user,_card)
        open_questions=list(TeamQuestion.objects.filter(state='open').order_by('deadline','created_at'))
        pending=[q for q in open_questions if preguntas.is_pending(q,now)]
        later_q=[q for q in open_questions if not preguntas.is_pending(q,now)]
        from . import conversaciones
        conversation_cards=[_conversation_card(c,now) for c in conversaciones.needing_gustavo(now)]
        from . import resumen_semanal
        summary_cards=[_summary_card(s) for s in [resumen_semanal.pending_proposal()] if s]
        from .perfil import cards as profile_cards
        from .referentes_views import cards as referent_cards
        profile=profile_cards(request.user,_card)
        monthly_cards=referent_cards(request.user,_card,now)
        monthly_later=[c for c in monthly_cards if c.get('state_override')=='pospuesta']
        monthly_cards=[c for c in monthly_cards if c.get('state_override')!='pospuesta']
        from . import respuestas, urgente
        message_cards=respuestas.cards(_card,now)
        day_cards=urgente.cards(_card,now)
        tasks={'perfil':profile,'conversaciones':conversation_cards,'mensajes':message_cards,'fechas':day_cards,'resumen':summary_cards,
               'referentes':monthly_cards}
        approval_cards=[_approval_card(p) for p in awaiting_approval()]
        question_cards=[_question_card(q,now) for q in pending]
        later=[_question_card(q,now) for q in later_q]+profile_cards(request.user,_card,postponed=True)+monthly_later
        cards=warnings+question_cards+conversation_cards+message_cards+day_cards+summary_cards+approval_cards+profile+monthly_cards
        seen=set(InboxSeen.objects.filter(item_id__in=[c['id'] for c in cards]).values_list('item_id',flat=True))
        items=_ordered(_with_state(cards,seen));_with_state(later,seen)
        active=[c for c in items if c['state'] in ('nueva','vista')]
        return Response({'count':len(active),'critical':any(c['priority']=='urgente' for c in active),
                         'urgent_count':sum(1 for c in active if c['priority']=='urgente'),
                         'counts':{'avisos':len(warnings),'preguntas':len(pending),'tareas':sum(len(v) for v in tasks.values()),
                                   'aprobaciones':len(approval_cards)},
                         'top':items[0] if items else None,'items':items,
                         'alerts':[c for c in items if c['type']=='aviso'],'questions':[c for c in items if c['type']=='pregunta'],'later':later,
                         'tasks':tasks,'recent':preguntas.recently_resolved()+_resolved_alerts()+conversaciones.recently_resolved()+respuestas.recently_resolved()
                                   +urgente.recently_resolved(),
                         'notifications_unread':notificaciones.unread(),'summary':_today_summary(now)})

class TuTurnoSeen(APIView):
    """POST /api/v1/tu-turno/vistos {ids}: cards Gustavo opened go from Nueva to Vista."""
    def post(self,request):
        human_session(request);require(request.user,'operate_linkedin')
        from .models import InboxSeen
        ids=request.data.get('ids') if isinstance(request.data,dict) else None
        if not isinstance(ids,list) or not all(isinstance(i,str) and 0<len(i)<=120 for i in ids) or len(ids)>200:
            raise ValidationError('ids debe ser una lista de identificadores de tarjetas')
        for item in set(ids):InboxSeen.objects.get_or_create(item_id=item)
        return Response({'seen':len(set(ids))})

class ConversationClose(APIView):
    """POST /api/v1/conversaciones/<id>/cerrar {how: respondi | no_responder, note?}: Gustavo closes the card."""
    def post(self,request,cid):
        human_session(request)
        from . import conversaciones
        from .models import Conversation
        data=request.data if isinstance(request.data,dict) else {}
        note=data.get('note') or ''
        if data.get('how') not in conversaciones.CLOSE_HOW or not isinstance(note,str) or len(note)>1000:
            raise ValidationError('how debe ser respondi o no_responder; note, un texto de hasta 1000 caracteres')
        get_or_404(Conversation,id=cid)
        conversation=conversaciones.close(request.user,cid,data['how'],note)
        return Response(conversaciones.payload(conversation))

class SuggestedMessageClose(APIView):
    """POST /api/v1/respuestas/<id>/mensaje {how: enviado | no, note?}: Gustavo closes the «Mensaje sugerido» card. The team
    never sends it (INB-08): he sends it himself from LinkedIn and says so here."""
    def post(self,request,cid):
        human_session(request)
        from . import respuestas
        from .models import PostComment
        data=request.data if isinstance(request.data,dict) else {}
        note=data.get('note') or ''
        if data.get('how') not in respuestas.CLOSE_HOW or not isinstance(note,str) or len(note)>1000:
            raise ValidationError('how debe ser enviado o no; note, un texto de hasta 1000 caracteres')
        get_or_404(PostComment,id=cid)
        row=respuestas.close_dm(request.user,cid,data['how'],note)
        return Response({'id':str(row.id),'closed':row.decision.get('dm_closed')})

class Notifications(APIView):
    """GET /api/v1/notificaciones?filtro=todas|sin_leer: what is coming or happened, 7 days, with its read state."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        from . import notificaciones
        from .models import Notification
        notificaciones.purge()
        qs=Notification.objects.filter(created_at__gte=timezone.now()-notificaciones.RETENTION)
        if request.query_params.get('filtro')=='sin_leer':qs=qs.filter(read_at__isnull=True)
        items=[{'id':str(n.id),'kind':n.kind,'layer':n.layer,'title':n.title,'detail':n.detail,'link':n.link,'at':n.created_at,
                'read':n.read_at is not None} for n in qs.order_by('-created_at')[:200]]
        return Response({'upcoming':notificaciones.upcoming(),'items':items,'unread':notificaciones.unread()})

class NotificationsRead(APIView):
    """POST /api/v1/notificaciones/leer {ids} or {todas: true}."""
    def post(self,request):
        human_session(request);require(request.user,'operate_linkedin')
        from . import notificaciones
        from .models import Notification
        data=request.data if isinstance(request.data,dict) else {}
        qs=Notification.objects.filter(read_at__isnull=True)
        if data.get('todas') is True:pass
        elif isinstance(data.get('ids'),list) and data['ids']:qs=qs.filter(id__in=[i for i in data['ids'] if isinstance(i,str)][:200])
        else:raise ValidationError('Envía ids o todas: true')
        qs.update(read_at=timezone.now())
        return Response({'unread':notificaciones.unread()})

def _resolved_alerts(days=7):
    since=timezone.now()-timedelta(days=days);out=[]
    for event in AuditEvent.objects.filter(created_at__gte=since,action__in=['operator.execution_confirmed','operator.execution_failed','linkedin.connected',
                                                                        'operator.machine_resumed','operator.approved']).order_by('-created_at')[:50]:
        if event.action=='operator.approved':
            proposal=ActionProposal.objects.select_related('post','piece','contact','comment__piece').filter(id=event.target).first()
            if proposal:out.append({'kind':'alert','id':f'approval:{event.target}','title':approval_sentence(proposal),'at':event.created_at,'how':'Aprobada'})
        elif event.action.startswith('operator.execution_'):
            execution=ActionExecution.objects.filter(proposal_id=event.target,note__startswith='Resolución humana').first()
            if not execution:continue
            out.append({'kind':'alert','id':f'uncertain:{event.target}','title':'¿Salió o no?','at':event.created_at,
                        'how':'Confirmaste que se aplicó' if event.action.endswith('confirmed') else 'Confirmaste que no se aplicó'})
        elif event.action=='linkedin.connected':
            out.append({'kind':'alert','id':'linkedin','title':'Reconecta LinkedIn','at':event.created_at,'how':'Reconectado'})
        else:out.append({'kind':'alert','id':'machine','title':'Reanuda la máquina','at':event.created_at,'how':'Reanudada'})
    return out

# --------------------------------------------------------------------------- questions and memory

class Questions(ListAPIView):
    serializer_class=QuestionOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=TeamQuestion.objects.all();state=self.request.query_params.get('state')
        return qs.filter(state=state) if state else qs

def _question_action(func):
    class View(APIView):
        def post(self,request,qid):
            human_session(request);get_or_404(TeamQuestion,id=qid)
            return Response(QuestionOutput(func(request)(qid)).data)
    return View

class QuestionAnswer(APIView):
    def post(self,request,qid):
        human_session(request);data=valid(AnswerInput,request);get_or_404(TeamQuestion,id=qid)
        item=preguntas.answer(request.user,qid,data.get('text',''),data.get('public_use'),data.get('accept',False),data.get('value'))
        return Response(QuestionOutput(item).data)

QuestionUndo=_question_action(lambda request:lambda qid:preguntas.undo(request.user,qid))
QuestionPostpone=_question_action(lambda request:lambda qid:preguntas.postpone(request.user,qid))
QuestionDecline=_question_action(lambda request:lambda qid:preguntas.decline(request.user,qid))

class Facts(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(preguntas.facts())
    def post(self,request):
        human_session(request);data=valid(AddFactInput,request)
        preguntas.add_fact(request.user,data['text'],data['public_use'],data.get('topic',''))
        return Response(preguntas.facts(),status=201)

class FactCorrect(APIView):
    def post(self,request,key):
        human_session(request);data=valid(FactInput,request)
        preguntas.correct(request.user,key,data['text'],data['public_use'])
        return Response(preguntas.facts())

class FactRetire(APIView):
    def post(self,request,key):
        human_session(request);data=valid(RetireInput,request)
        preguntas.retire(request.user,key,data.get('reason',''))
        return Response(preguntas.facts())

# --------------------------------------------------------------------------- orientation

def _orientation_payload():
    from .models import Orientation
    current=Orientation.current()
    return {'text':current.text,'updated_at':current.updated_at,'updated_by':current.updated_by.get_username() if current.updated_by else None}

class OrientationView(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(_orientation_payload())
    def put(self,request):
        human_session(request);data=valid(OrientationInput,request)
        orientacion.update(request.user,data['text'])
        return Response(_orientation_payload())

# --------------------------------------------------------------------------- opportunities

class Opportunities(ListAPIView):
    serializer_class=OpportunityOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=Opportunity.objects.select_related('contact')
        for field in ('stage','modality'):
            value=self.request.query_params.get(field)
            if value:qs=qs.filter(**{field:value})
        contact=self.request.query_params.get('contact')
        return qs.filter(contact_id=contact) if contact else qs
    def post(self,request):
        human_session(request);data=valid(OpportunityInput,request)
        return Response(OpportunityOutput(oportunidades.create(request.user,data)).data,status=201)

class OpportunityDetail(APIView):
    def get(self,request,oid):
        require(request.user,'operate_linkedin')
        return Response(OpportunityOutput(get_or_404(Opportunity,id=oid)).data)
    def patch(self,request,oid):
        human_session(request);data=valid(OpportunityPatch,request);get_or_404(Opportunity,id=oid)
        return Response(OpportunityOutput(oportunidades.update(request.user,oid,data)).data)
    def delete(self,request,oid):
        human_session(request);get_or_404(Opportunity,id=oid)
        oportunidades.delete(request.user,oid)
        return Response(status=204)

# --------------------------------------------------------------------------- calendar and list view

def _target(p):
    if p.contact_id:
        c=p.contact
        return {'kind':'person','name':c.display_name,'headline':c.headline,'url':c.profile_url,'contact_id':str(c.id),
                'role':(c.classification or {}).get('role')}
    if p.post_id:
        return {'kind':'post','name':p.post.author_name,'headline':'','url':p.post.share_url,'post_excerpt':(p.post.text or '')[:280]}
    if p.comment_id:
        from .respuestas import share_url
        c=p.comment
        return {'kind':'comment','name':c.author_name,'headline':'','url':share_url(c.piece),'comment_excerpt':(c.text or '')[:280],
                'contact_id':str(c.contact_id) if c.contact_id else None,'piece_id':str(c.piece_id)}
    return {'kind':'own','name':'Tu perfil','headline':'','url':''}

def _decided_by(p):
    if p.decided_by_id:return 'gustavo'
    if (p.review or {}).get('decision') in ('approve','discard'):return 'lider'
    return 'politica' if p.decided_at else None

def item(p):
    """A timeline element (Calendario → Lista, panel del día y «Ver todo lo del día»)."""
    execution=getattr(p,'execution',None) if hasattr(p,'execution') else None
    target=_target(p)
    at=(execution.finished_at or execution.started_at) if execution else (p.decided_at or p.created_at)
    return {'id':str(p.id),'capability':p.capability,'label':LABELS.get(p.capability,p.capability),'agent':ACTOR.get(p.capability),
            'state':p.state,'state_label':STATE_LABELS.get(p.state),'important':p.capability in ('CONT-09','RED-04') or p.state in ('uncertain','failed'),
            'at':at,'date':local_day(at),'text':p.payload.get('text'),'reaction':p.payload.get('reaction'),'target':target,
            'url':(execution.external_url if execution and execution.external_url else target['url']),'rationale':p.rationale,
            'decided_by':_decided_by(p),'decision_note':p.decision_note,'execution_note':execution.note if execution else '',
            'review':{k:v for k,v in (p.review or {}).items() if k in ('decision','answers','reasons','model')},
            'piece_id':str(p.piece_id) if p.piece_id else None}

def next_execution_time(now=None):
    """When a queued action may leave: the window and the common spacing (an estimate; caps may delay it more)."""
    now=now or timezone.now();tz=operador.local_tz()
    start,_,end=os.environ.get('OPERATOR_WINDOW','07:00-21:00').partition('-')
    def at(day,value):
        h,_,m=value.strip().partition(':');return datetime.combine(day,time(int(h)%24,int(m or 0)),tzinfo=tz)
    last=ActionExecution.objects.filter(wrote=True).order_by('-started_at').values_list('started_at',flat=True).first()
    candidate=max(now,last+operador.min_spacing()) if last else now
    if not operador.within_window(candidate):
        local=candidate.astimezone(tz);opening=at(local.date(),start)
        candidate=opening if local<opening else at(local.date()+timedelta(days=1),start)
    return candidate

def _piece_card(piece):
    action=editorial.latest_action(piece);status=editorial.status(piece,action);brief=piece.brief or {}
    return {'piece_id':str(piece.id),'slot_date':piece.slot_date,'scheduled_for':piece.scheduled_for,'status':status,'stage':piece.stage,
            'thesis':brief.get('thesis'),'excerpt':'\n'.join((piece.final_text or '').splitlines()[:3]),'pillar':brief.get('pillar'),
            'modality':brief.get('modality'),'primary_reader':brief.get('primary_reader'),
            'action':{'id':str(action.id),'state':action.state} if action else None,
            'vetoable':bool(action and action.state in ('proposed','approved')),'impressions':(piece.metrics or {}).get('impressions'),
            'skip_reason':brief.get('skip_reason') if piece.state=='skipped' else None,'note':piece.note}

def upcoming(now=None):
    now=now or timezone.now()
    pieces=[_piece_card(p) for p in EditorialPiece.objects.filter(state__in=['preparing','ready'],scheduled_for__gt=now-timedelta(hours=1))
            .order_by('scheduled_for')[:5] if not (p.state=='ready' and editorial.status(p,editorial.latest_action(p)) in ('published','failed','uncertain'))]
    expected=next_execution_time(now)
    # What waits for Gustavo's approval comes first, with the exact version to approve and when it stops waiting.
    waiting=[dict(item(p),expected_at=None,awaiting_approval=True,payload_hash=p.payload_hash,expires_at=approval_expiry(p))
             for p in awaiting_approval() if not p.piece_id][:50]
    queued=[dict(item(p),expected_at=expected,awaiting_approval=False) for p in ActionProposal.objects.select_related('post','piece','contact','comment__piece')
            .filter(state='approved',execution__isnull=True,piece__isnull=True).order_by('created_at')[:50]]
    return {'pieces':pieces,'queued':waiting+queued}

class Activity(APIView):
    """Calendario → vista Lista: «Próximo» and every day with everything that happened, newest first."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        qs=ActionProposal.objects.select_related('post','piece','contact','execution','comment__piece')
        kind=request.query_params.get('tipo')
        if kind and kind!='todo':
            if kind not in TYPES:raise NotFound('Tipo desconocido')
            qs=qs.filter(capability__in=TYPES[kind])
        states=['confirmed','sent','executing','uncertain','failed']
        if request.query_params.get('no_salio') in ('1','true'):states+=list(NOT_DONE)
        qs=qs.filter(state__in=states)
        if request.query_params.get('desde') or request.query_params.get('hasta'):
            start,end,_=parse_range(request.query_params)
            qs=qs.filter(created_at__gte=day_bounds(start)[0]-timedelta(days=2),created_at__lt=day_bounds(end)[1])
        try:
            limit=max(1,min(100,int(request.query_params.get('limit','50'))));offset=max(0,int(request.query_params.get('offset','0')))
        except ValueError:raise ValidationError('limit y offset deben ser números') from None
        rows=[item(p) for p in qs.order_by('-created_at')]
        if request.query_params.get('desde') or request.query_params.get('hasta'):
            rows=[r for r in rows if r['date'] and start<=r['date']<=end]
        rows.sort(key=lambda r:r['at'] or timezone.now(),reverse=True)
        page=rows[offset:offset+limit]
        return Response({'upcoming':upcoming(),'items':page,'next_offset':offset+limit if len(rows)>offset+limit else None})

class Calendar(APIView):
    """GET /api/v1/calendario?desde=&hasta=: per local day, the counts and the important events by layer."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        start,end,today=parse_range(request.query_params)
        days={start+timedelta(days=i):{'counts':{'comments':0,'replies':0,'reactions':0,'follows':0,'invites':0,'accepts':0,'connections_fit':0},'events':[]}
              for i in range((end-start).days+1)}
        lo,hi=day_bounds(start)[0],day_bounds(end)[1]
        def add(day,layer,kind,title,at=None,state=None,important=True,link=None,**extra):
            if day in days:days[day]['events'].append(dict({'id':f'{kind}:{extra.get("ref",title)}:{day}','layer':layer,'kind':kind,'at':at,
                                                            'title':title,'state':state,'important':important,'link':link},**extra))
        # Publicaciones
        rows={}
        for piece in EditorialPiece.objects.filter(slot_date__gte=start,slot_date__lte=end).order_by('created_at'):
            card=_piece_card(piece);rows.setdefault(piece.slot_date,[]).append((piece,card['status'],(piece,card)))
        for piece,card in [shown for day_rows in rows.values() for shown in editorial.calendar_rows(day_rows,today)]:
            status=card['status']
            kind={'published':'piece_published','scheduled':'piece_scheduled','preparing':'piece_preparing','skipped':'piece_skipped',
                  'blocked':'piece_blocked','failed':'piece_failed','uncertain':'piece_uncertain','vetoed':'piece_vetoed',
                  'discarded':'piece_discarded','publishing':'piece_publishing','awaiting_approval':'piece_awaiting_approval'}.get(status,f'piece_{status}')
            add(piece.slot_date,'publicaciones',kind,card['thesis'] or 'Publicación del día',at=piece.scheduled_for,state=status,
                link=f'/calendario/pieza/{piece.id}',ref=str(piece.id),impressions=card['impressions'],skip_reason=card['skip_reason'])
        # Executed actions: counts, plus the important ones (accepts, uncertain or failed)
        for p in ActionProposal.objects.select_related('post','contact','execution','comment__piece').filter(execution__started_at__gte=lo,execution__started_at__lt=hi):
            day=local_day(p.execution.finished_at or p.execution.started_at)
            if p.state=='confirmed' and p.capability in COUNT_KEYS and day in days:days[day]['counts'][COUNT_KEYS[p.capability]]+=1
            if p.state in ('uncertain','failed'):
                add(day,'sistema','action_'+p.state,f'{LABELS.get(p.capability,p.capability)} {STATE_LABELS[p.state].lower()}',
                    at=p.execution.started_at,state=p.state,link='/tu-turno' if p.state=='uncertain' else None,ref=str(p.id))
            elif p.capability=='RED-04' and p.state=='confirmed':
                add(day,'red','invitation_accepted',f'Aceptaste la invitación de {p.contact.display_name}',at=p.execution.finished_at,
                    link=f'/personas/{p.contact_id}',ref=str(p.id))
        # Red: new connections that fit (grouped), invitations received, invitations expected after the warm-up
        connections={}
        for c in Contact.objects.filter(connected_at__gte=lo,connected_at__lt=hi,classification__fit=True):
            connections.setdefault(local_day(c.connected_at),[]).append({'id':str(c.id),'name':c.display_name,'role':c.classification.get('role')})
        for day,people in connections.items():
            if day in days:days[day]['counts']['connections_fit']=len(people)
            add(day,'red','connection_fit',f'{len(people)} conexiones nuevas' if len(people)>1 else f'{people[0]["name"]} aceptó tu invitación',
                people=people,link='/personas',ref='connections')  # Personas › Conexiones
        for c in Contact.objects.filter(source='incoming',discovered_at__gte=lo,discovered_at__lt=hi):
            add(local_day(c.discovered_at),'red','invitation_received',f'{c.display_name} te invitó',at=c.discovered_at,link=f'/personas/{c.id}',ref=str(c.id))
        expected={}
        # An invitation already proposed, approved or on its way is no longer a forecast (backlog #8).
        invited=ActionProposal.objects.filter(capability='RED-02',state__in=OPEN_ACTION_STATES).values('contact_id')
        for c in Contact.objects.filter(stage='followed',followed_at__isnull=False).exclude(id__in=invited):
            due=max(local_day(c.followed_at+red.invite_after()),today)
            expected.setdefault(due,[]).append({'id':str(c.id),'name':c.display_name})
        for day,people in expected.items():
            add(day,'red','invite_expected',f'{len(people)} invitaciones previstas',important=False,estimate=True,people=people,ref='expected')
        # Tuyo: question deadlines, opportunity next actions, LinkedIn expiry, what Gustavo resolved
        for q in TeamQuestion.objects.filter(state='open',deadline__gte=lo,deadline__lt=hi):
            add(local_day(q.deadline),'tuyo','deadline',f'Responde: {q.question}',at=q.deadline,link='/tu-turno',ref=str(q.id),agent=q.agent)
        for o in Opportunity.objects.select_related('contact').filter(next_action_at__gte=lo,next_action_at__lt=hi).exclude(stage__in=oportunidades.CLOSED):
            name=o.contact.display_name if o.contact else o.person_name
            add(local_day(o.next_action_at),'tuyo','meeting' if o.stage=='reunion' else 'opportunity_next',f'{o.next_action or "Siguiente paso"} · {name}',
                at=o.next_action_at,link=f'/personas/{o.contact_id}' if o.contact_id else '/personas?pestana=oportunidades',ref=str(o.id))
        for q in TeamQuestion.objects.filter(state__in=['answered','declined'],answered_at__gte=lo,answered_at__lt=hi):
            add(local_day(q.answered_at),'tuyo','resolved',q.question,at=q.answered_at,state=q.state,important=False,link='/tu-turno/sabe',ref=str(q.id))
        from . import connectors_linkedin as li
        status=li.status_payload()
        if status.get('expires_at'):
            expiry=datetime.fromisoformat(str(status['expires_at']))
            if lo<=expiry<hi:
                add(local_day(expiry),'tuyo' if expiry>timezone.now() else 'sistema','linkedin_expiry' if expiry>timezone.now() else 'linkedin_expired',
                    'Caduca el permiso de LinkedIn' if expiry>timezone.now() else 'LinkedIn caducó',at=expiry,link='/tu-turno',ref='linkedin')
        # Conversaciones: opportunities created or moved (the inbox comes later)
        for o in Opportunity.objects.select_related('contact').filter(updated_at__gte=lo):
            name=o.contact.display_name if o.contact else o.person_name
            for event in o.history:
                at=datetime.fromisoformat(event['at'])
                if lo<=at<hi:add(local_day(at),'conversaciones','opportunity',f'Oportunidad con {name}: {o.get_stage_display()}' if event['event']=='created'
                                 else f'Oportunidad con {name}: {event["detail"]}',at=at,link=f'/personas/{o.contact_id}' if o.contact_id else None,ref=f'{o.id}:{event["at"]}')
        # Sistema: total stop, resume and account pauses
        for event in AuditEvent.objects.filter(created_at__gte=lo,created_at__lt=hi,action__in=['operator.machine_paused','operator.machine_resumed','operator.account_paused']):
            title={'operator.machine_paused':'Detuviste la máquina','operator.machine_resumed':'Se reanudó la máquina',
                   'operator.account_paused':'La cuenta de LinkedIn entró en pausa'}[event.action]
            add(local_day(event.created_at),'sistema',event.action.split('.')[1],title,at=event.created_at,
                detail=(event.metadata or {}).get('reason',''),link='/ajustes#maquina',ref=str(event.id))
        priority={'tuyo':0,'sistema':1,'publicaciones':2,'conversaciones':3,'red':4}
        for value in days.values():
            value['events'].sort(key=lambda e:(priority[e['layer']],str(e['at'] or '')))
        return Response({'timezone':str(operador.local_tz()),'today':today,'lead_hours':editorial.lead_time().total_seconds()/3600,
                         'days':[{'date':day,**value} for day,value in sorted(days.items())],
                         'layers':{'tuyo':True,'publicaciones':True,'red':True,'conversaciones':'parcial','sistema':True}})

# --------------------------------------------------------------------------- settings

def _spend(purpose_like,since=None,provider='anthropic'):
    with db.connect() as c:
        row=c.execute('''SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain')
            THEN reserved_usd ELSE 0 END),0) AS spent FROM usage_ledger WHERE provider=%s AND purpose LIKE %s AND created_at>=%s''',
            (provider,purpose_like,since or datetime(2000,1,1,tzinfo=dt_timezone.utc))).fetchone()
    return float(Decimal(row['spent']))

class Settings(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        from knowledge import presupuesto
        now=timezone.now();day,_=operador.period_starts(now);budget=presupuesto.status(now)
        month=now.astimezone(operador.local_tz()).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        start,_,end=os.environ.get('OPERATOR_WINDOW','07:00-21:00').partition('-')
        return Response({'autonomy':{c:autopiloto.autonomy(c) for c in sorted(operador.limits())},
                         'lead':{'enabled':lider.enabled(),'capabilities':lider.capabilities(),'model':os.environ.get('TYPESAFE_MODEL','jev-1.14.0')},
                         'limits':{c:{'daily':d,'weekly':w} for c,(d,w) in operador.limits().items()},
                         'window':{'start':start,'end':end,'timezone':str(operador.local_tz()),'open_now':operador.within_window(now),
                                   'min_spacing_seconds':int(operador.min_spacing().total_seconds())},
                         # One budget for the whole team (knowledge.presupuesto): the month line carries the limit, the
                         # first line today the daily safety fuse; the areas show what each spent, without a cap of their own.
                         'ai_spend':{'today':[
                             {'budget':'equipo','label':'Todo el equipo hoy (tope de seguridad)','spent_usd':float(budget['today_usd']),'limit_usd':float(budget['daily_fuse_usd'])},
                             {'budget':'general','label':'General (comentarios)','spent_usd':_spend('propose-comment',day),'limit_usd':0},
                             {'budget':'editorial','label':'Editorial (incluye imágenes e investigación de piezas)','spent_usd':float(editorial.spent_today(now)),'limit_usd':0},
                             {'budget':'imagenes','label':'Imágenes','spent_usd':float(imagenes.spent_today(now)),'limit_usd':0},
                             {'budget':'red','label':'Red','spent_usd':_spend('network-%',day),'limit_usd':0}],
                             'month_usd':float(budget['month_usd']),'total_usd':_spend('%'),'limit_usd':float(budget['monthly_limit_usd']),
                             'lead_month_usd':_spend('%',month,provider='typesafe'),
                             'transcription_month_usd':_spend('%',month,provider='assemblyai')},
                         'facts_count':len(preguntas.facts()),'push_types':notificaciones.push_types(),
                         'orientation':_orientation_payload(),
                         # «Dispositivos con la app» (docs/app-movil-backend.md).
                         'devices':devices_payload(request),'expo_push':expo.status(request.user)})
