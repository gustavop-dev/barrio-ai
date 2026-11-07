"""API for the redesigned office (oficina/PLAN-REDISENO.md): Tu turno, team questions, what the team knows,
orientation, opportunities, the unified activity timeline and settings. Decisions need a human session."""
import os
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from knowledge import db
from . import autopiloto, lider, operador, oportunidades, orientacion, preguntas, red
from .models import ActionProposal, ConnectorAccount, EditorialPiece, Opportunity, TeamQuestion
from .operador_views import get_or_404, human_session, valid
from .permissions import require

LABELS={'INT-03':'Comentario','INT-02':'Reacción','CONT-09':'Publicación propia','RED-01':'Seguimiento',
        'RED-02':'Invitación sin nota','RED-04':'Invitación aceptada'}
TYPES={'comentarios':'INT-03','reacciones':'INT-02','publicaciones':'CONT-09','seguimientos':'RED-01',
       'invitaciones':'RED-02','aceptaciones':'RED-04'}

# --------------------------------------------------------------------------- serializers

class QuestionOutput(serializers.ModelSerializer):
    class Meta:
        model=TeamQuestion
        fields=['id','kind','agent','question','purpose','memory_key','proposed_value','suggested_public','origin','state',
                'answer','public_use','answered_at','created_at']

class AnswerInput(serializers.Serializer):
    text=serializers.CharField(required=False,allow_blank=True,max_length=preguntas.MAX_ANSWER)
    public_use=serializers.BooleanField(required=False,allow_null=True,default=None)
    accept=serializers.BooleanField(required=False,default=False)

class FactInput(serializers.Serializer):
    text=serializers.CharField(max_length=preguntas.MAX_ANSWER)
    public_use=serializers.BooleanField(default=False)

class RetireInput(serializers.Serializer):
    reason=serializers.CharField(required=False,allow_blank=True,max_length=500)

class OrientationInput(serializers.Serializer):
    text=serializers.CharField(allow_blank=True,max_length=orientacion.MAX_CHARS)

class OpportunityOutput(serializers.ModelSerializer):
    contact=serializers.SerializerMethodField()
    def get_contact(self,obj):
        c=obj.contact
        return {'id':str(c.id),'display_name':c.display_name,'headline':c.headline,'profile_url':c.profile_url,'stage':c.stage} if c else None
    class Meta:
        model=Opportunity
        fields=['id','title','modality','stage','origin','notes','contact','history','created_at','updated_at','closed_at']

class OpportunityInput(serializers.Serializer):
    title=serializers.CharField(max_length=200)
    modality=serializers.ChoiceField(choices=Opportunity.Modality.values)
    origin=serializers.ChoiceField(choices=Opportunity.Origin.values,default='outbound')
    stage=serializers.ChoiceField(choices=Opportunity.Stage.values,default='conversacion')
    contact=serializers.UUIDField(required=False,allow_null=True)
    notes=serializers.CharField(required=False,allow_blank=True,default='')

class OpportunityPatch(serializers.Serializer):
    title=serializers.CharField(required=False,max_length=200)
    modality=serializers.ChoiceField(required=False,choices=Opportunity.Modality.values)
    origin=serializers.ChoiceField(required=False,choices=Opportunity.Origin.values)
    stage=serializers.ChoiceField(required=False,choices=Opportunity.Stage.values)
    notes=serializers.CharField(required=False,allow_blank=True)

# --------------------------------------------------------------------------- Tu turno

def _anthropic_month():
    start=timezone.now().astimezone(operador.local_tz()).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    with db.connect() as c:
        row=c.execute('''SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd WHEN status IN ('reserved','uncertain')
            THEN reserved_usd ELSE 0 END),0) AS month,(SELECT coalesce(sum(CASE WHEN status='complete' THEN actual_usd
            WHEN status IN ('reserved','uncertain') THEN reserved_usd ELSE 0 END),0) FROM usage_ledger WHERE provider='anthropic') AS total
            FROM usage_ledger WHERE provider='anthropic' AND created_at>=%s''',(start,)).fetchone()
    return Decimal(row['month']),Decimal(row['total']),Decimal(os.environ.get('ANTHROPIC_LIMIT_USD','1'))

def alerts(now=None):
    """What breaks without Gustavo: each alert carries its action."""
    from . import connectors_linkedin as li
    from .models import OperatorControl
    now=now or timezone.now();out=[]
    status=li.status_payload()
    if status.get('connected') and (status.get('expired') or status.get('expiring_soon')):
        out.append({'id':'linkedin_token','severity':'alta',
                    'title':'LinkedIn caducó' if status.get('expired') else f'LinkedIn caduca en {status.get("days_left")} días',
                    'detail':'Sin reconectar, la publicación diaria se detiene.','action':{'label':'Reconectar','href':'/api/v1/linkedin/oauth/start'}})
    for p in ActionProposal.objects.select_related('post','contact').filter(state='uncertain').order_by('created_at'):
        target=p.contact.display_name if p.contact_id else (p.post.author_name if p.post_id else 'tu perfil')
        out.append({'id':f'uncertain:{p.id}','severity':'alta','title':'¿Salió o no?',
                    'detail':f'{LABELS.get(p.capability,p.capability)} para {target}: LinkedIn no confirmó el resultado y no se repite solo.',
                    'action':{'label':'Resolver','endpoint':f'/api/v1/operador/actions/{p.id}/resolve','proposal_id':str(p.id)}})
    if operador.globally_paused():
        reason='fijada en el servidor (OPERATOR_PAUSED)' if operador.env_paused() else (OperatorControl.current().reason or 'sin motivo')
        out.append({'id':'machine_paused','severity':'alta','title':'La máquina está detenida','detail':f'Parada total: {reason}.',
                    'action':{'label':'Reanudar','endpoint':'/api/v1/operador/control'}})
    for account in ConnectorAccount.objects.filter(paused=True):
        out.append({'id':f'account_paused:{account.id}','severity':'alta','title':f'{account.label} está en pausa',
                    'detail':account.paused_reason or 'Sin motivo registrado.','action':{'label':'Revisar y reanudar','endpoint':f'/api/v1/operador/accounts/{account.id}/pause'}})
    blocked,reason=red.invites_blocked(now)
    if blocked:out.append({'id':'invites_blocked','severity':'media','title':'LinkedIn limitó las invitaciones','detail':reason,'action':None})
    month,total,limit=_anthropic_month()
    if limit>0 and total>=limit*Decimal('0.8'):
        out.append({'id':'ai_budget','severity':'media','title':f'Presupuesto de IA al {int(total*100/limit)} %',
                    'detail':f'Gastados {total:.2f} de {limit:.2f} USD. Al llegar al tope, los agentes dejan de redactar.','action':None})
    return out

class TuTurno(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        preguntas.sync_memory_proposals()
        questions=TeamQuestion.objects.filter(state='open').order_by('created_at')
        items=alerts();now=timezone.now();day,_=operador.period_starts(now)
        done={}
        for capability in LABELS:
            n=ActionProposal.objects.filter(capability=capability,state='confirmed',execution__finished_at__gte=day).count()
            if n:done[capability]=n
        upcoming=EditorialPiece.objects.filter(state='ready',scheduled_for__gt=now).order_by('scheduled_for').first()
        return Response({'count':questions.count()+len(items),
                         'questions':QuestionOutput(questions,many=True).data,
                         'tasks':{'perfil':[],'conversaciones':[]},  # profile cycle and inbox: later phases of the plan
                         'alerts':items,
                         'summary':{'done_today':done,'next_piece':{'id':str(upcoming.id),'scheduled_for':upcoming.scheduled_for} if upcoming else None}})

# --------------------------------------------------------------------------- questions and memory

class Questions(ListAPIView):
    serializer_class=QuestionOutput
    def get_queryset(self):
        require(self.request.user,'operate_linkedin')
        qs=TeamQuestion.objects.all();state=self.request.query_params.get('state')
        return qs.filter(state=state) if state else qs

class QuestionAnswer(APIView):
    def post(self,request,qid):
        human_session(request);data=valid(AnswerInput,request);get_or_404(TeamQuestion,id=qid)
        return Response(QuestionOutput(preguntas.answer(request.user,qid,data.get('text',''),data.get('public_use'),data.get('accept',False))).data)

class QuestionDecline(APIView):
    def post(self,request,qid):
        human_session(request);get_or_404(TeamQuestion,id=qid)
        return Response(QuestionOutput(preguntas.decline(request.user,qid)).data)

class Facts(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response(preguntas.facts())

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
        item=oportunidades.create(request.user,data['title'],data['modality'],data['origin'],data.get('contact'),data.get('notes',''),data['stage'])
        return Response(OpportunityOutput(item).data,status=201)

class OpportunityDetail(APIView):
    def get(self,request,oid):
        require(request.user,'operate_linkedin')
        return Response(OpportunityOutput(get_or_404(Opportunity,id=oid)).data)
    def patch(self,request,oid):
        human_session(request);data=valid(OpportunityPatch,request);get_or_404(Opportunity,id=oid)
        return Response(OpportunityOutput(oportunidades.update(request.user,oid,**data)).data)

# --------------------------------------------------------------------------- activity

def _decided_by(p):
    if p.decided_by_id:return 'gustavo'
    if (p.review or {}).get('decision') in ('approve','discard'):return 'lider'
    return 'politica' if p.decided_at else None

def _item(p):
    execution=getattr(p,'execution',None) if hasattr(p,'execution') else None
    if p.contact_id:
        target={'kind':'person','name':p.contact.display_name,'headline':p.contact.headline,'url':p.contact.profile_url}
    elif p.post_id:
        target={'kind':'post','name':p.post.author_name,'headline':'','url':p.post.share_url}
    else:target={'kind':'own','name':'Tu perfil','headline':'','url':''}
    return {'id':str(p.id),'capability':p.capability,'label':LABELS.get(p.capability,p.capability),'state':p.state,
            'at':(execution.finished_at or execution.started_at) if execution else p.decided_at or p.created_at,
            'text':p.payload.get('text') if isinstance(p.payload,dict) else None,'target':target,
            'url':(execution.external_url if execution and execution.external_url else target['url']),
            'rationale':p.rationale,'decided_by':_decided_by(p),'decision_note':p.decision_note,
            'review':{k:v for k,v in (p.review or {}).items() if k in ('decision','answers','reasons','model')},
            'piece_id':str(p.piece_id) if p.piece_id else None}

class Activity(APIView):
    """One timeline: upcoming (own pieces and approved actions waiting their slot), done, and optionally what the
    agente líder or the policy discarded."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        now=timezone.now();qs=ActionProposal.objects.select_related('post','piece','contact','execution')
        kind=request.query_params.get('tipo')
        if kind:
            if kind not in TYPES:raise NotFound('Tipo desconocido')
            qs=qs.filter(capability=TYPES[kind])
        try:limit=max(1,min(100,int(request.query_params.get('limit','50'))))
        except ValueError:limit=50
        pieces=[]
        for piece in EditorialPiece.objects.filter(state='ready',scheduled_for__gt=now).order_by('scheduled_for')[:5]:
            action=piece.proposals.order_by('-created_at').first()
            pieces.append({'piece_id':str(piece.id),'scheduled_for':piece.scheduled_for,'text':piece.final_text,
                           'action':{'id':str(action.id),'state':action.state} if action else None,
                           'vetoable':bool(action and action.state in ('proposed','approved'))})
        queued=qs.filter(state='approved',execution__isnull=True,piece__isnull=True).order_by('created_at')[:limit]
        done=qs.filter(state__in=['confirmed','sent']).order_by('-execution__started_at')[:limit]
        payload={'upcoming':{'pieces':pieces,'queued':[_item(p) for p in queued]},'done':[_item(p) for p in done]}
        if request.query_params.get('descartadas') in ('1','true'):
            payload['discarded']=[_item(p) for p in qs.filter(state='discarded').order_by('-decided_at','-created_at')[:limit]]
        return Response(payload)

# --------------------------------------------------------------------------- settings

class Settings(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        month,total,limit=_anthropic_month()
        caps=sorted(operador.limits())
        start,_,end=os.environ.get('OPERATOR_WINDOW','07:00-21:00').partition('-')
        return Response({'autonomy':{c:autopiloto.autonomy(c) for c in caps},
                         'lead':{'enabled':lider.enabled(),'capabilities':lider.capabilities(),
                                 'model':os.environ.get('TYPESAFE_MODEL','jev-1.14.0')},
                         'limits':{c:{'daily':d,'weekly':w} for c,(d,w) in operador.limits().items()},
                         'window':{'start':start,'end':end,'timezone':os.environ.get('OPERATOR_TIMEZONE','America/Bogota')},
                         'ai_spend':{'anthropic_month_usd':float(month),'anthropic_total_usd':float(total),'anthropic_limit_usd':float(limit)},
                         'orientation':_orientation_payload()})
