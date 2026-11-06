"""API of the self-hosted office PWA (see oficina/CONTRATO-API.md).
Same origin as the PWA: Django session + CSRF. Human decisions never accept a Bearer token."""
import json
import os
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from . import autopiloto, editorial, operador, push
from .models import (ActionExecution, ActionProposal, AuditEvent, ConnectorAccount, EditorialPiece, Job, ObservedPost, OperatorControl,
                     PushSubscription, Referent)
from .operador_views import human_session, valid
from .permissions import require
from .serializers import AccountOutput

# --------------------------------------------------------------------------- session

LOGIN_ATTEMPTS=10
LOGIN_WINDOW=15*60

def _user_payload(user):
    perms=sorted(p.split('.',1)[1] for p in user.get_all_permissions() if p.startswith('team_backend.'))
    return {'username':user.get_username(),'is_superuser':user.is_superuser,'permissions':perms}

@require_GET
@ensure_csrf_cookie
def session_view(request):
    user=request.user
    return JsonResponse({'authenticated':user.is_authenticated,'user':_user_payload(user) if user.is_authenticated else None})

@require_POST
@csrf_protect
def login_view(request):
    try:data=json.loads(request.body or b'{}')
    except json.JSONDecodeError:return JsonResponse({'detail':'JSON inválido'},status=400)
    username=str(data.get('username',''))[:150];password=str(data.get('password',''))[:256]
    client=request.META.get('REMOTE_ADDR','')
    key=f'login-attempts:{client}:{username.lower()}'
    if cache.get(key,0)>=LOGIN_ATTEMPTS:return JsonResponse({'detail':'Demasiados intentos; espera unos minutos.'},status=429)
    user=authenticate(request,username=username,password=password)
    if not user or not user.is_active:
        cache.set(key,cache.get(key,0)+1,LOGIN_WINDOW)
        return JsonResponse({'detail':'Usuario o contraseña incorrectos.'},status=400)
    cache.delete(key);login(request,user)
    AuditEvent.objects.create(actor=user,action='auth.login',target='office',metadata={})
    return JsonResponse({'user':_user_payload(user)})

@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)

# --------------------------------------------------------------------------- machine

def _control_payload():
    control=OperatorControl.current()
    if operador.env_paused():
        return {'paused':True,'reason':'Parada fijada en el servidor (OPERATOR_PAUSED).','source':'env','updated_at':None,'updated_by':None}
    return {'paused':control.paused,'reason':control.reason,'source':'db' if control.paused else 'none',
            'updated_at':control.updated_at,'updated_by':control.updated_by.get_username() if control.updated_by else None}

def _capacity(account,now):
    day,week=operador.period_starts(now);result={}
    for capability,(daily,weekly) in operador.limits().items():
        done=ActionExecution.objects.filter(proposal__account=account,proposal__capability=capability)
        daily_used=done.filter(started_at__gte=day).count();weekly_used=done.filter(started_at__gte=week).count()
        result[capability]={'daily':daily,'weekly':weekly,'daily_used':daily_used,'weekly_used':weekly_used,
                            'left':max(0,min(daily-daily_used,weekly-weekly_used))}
    return result

class Overview(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        now=timezone.now();day,_=operador.period_starts(now)
        start,_,end=os.environ.get('OPERATOR_WINDOW','07:00-21:00').partition('-')
        proposals={state:ActionProposal.objects.filter(created_at__gte=day,state=state).count() for state in ActionProposal.State.values}
        accounts=[dict(AccountOutput(a).data,capacity=_capacity(a,now)) for a in ConnectorAccount.objects.order_by('created_at')]
        return Response({
            'autopilot':{'enabled':autopiloto.enabled(),'policy_version':autopiloto.POLICY_VERSION},
            'control':_control_payload(),
            'window':{'start':start.strip(),'end':end.strip(),'timezone':str(operador.local_tz()),'open_now':operador.within_window(now),
                      'min_spacing_seconds':int(operador.min_spacing().total_seconds())},
            'accounts':accounts,
            'today':{'proposals':proposals,'llm_spent_usd':str(autopiloto.llm_spent_today(now)),
                     'llm_daily_cap_usd':str(Decimal(os.environ.get('OPERATOR_DAILY_LLM_USD','1'))),
                     'drafts':ActionProposal.objects.filter(source='agent',created_at__gte=day).count(),
                     'drafts_daily_cap':int(os.environ.get('OPERATOR_DAILY_PROPOSALS','6')),
                     'editorial_llm_spent_usd':str(editorial.spent_today(now)),'editorial_llm_daily_cap_usd':str(editorial.daily_budget())},
            'counts':{'referents':Referent.objects.filter(active=True).count(),'posts':ObservedPost.objects.count(),
                      'uncertain':ActionExecution.objects.filter(state='uncertain').count()}})

class ControlInput(serializers.Serializer):
    paused=serializers.BooleanField()
    reason=serializers.CharField(max_length=500,required=False,allow_blank=True,default='')

class Control(APIView):
    def post(self,request):
        human_session(request);data=valid(ControlInput,request)
        operador.set_global_pause(request.user,data['paused'],data['reason'])
        return Response(_control_payload())

class Feed(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        try:limit=max(1,min(200,int(request.query_params.get('limit','50'))))
        except ValueError:limit=50
        events=(AuditEvent.objects.select_related('actor').filter(action__regex=r'^(operator|job)\.').order_by('-created_at')[:limit])
        return Response([{'id':e.id,'action':e.action,'target':e.target,'created_at':e.created_at,
                          'actor':e.actor.get_username() if e.actor else None,'metadata':e.metadata} for e in events])

# --------------------------------------------------------------------------- office scene

ROLES=['posicionamiento','perfil','investigador_referentes','analista_barrio_resultados','director_editorial','copywriter_a',
       'copywriter_b','lector_comprador','lector_recomendador','lector_divulgador','lector_lider','lector_par',
       'editor_verificador','relaciones_comunidad','conversaciones_inbox','operador_cuenta']
# Real work behind each implemented role. Roles without work here are contracts in design.
JOB_ROLES={'observe':'investigador_referentes','propose_comment':'relaciones_comunidad',
           'execute_action':'operador_cuenta','reconcile_action':'operador_cuenta'}
DESCRIPTIONS={'observe':'Leyendo publicaciones de referentes','propose_comment':'Redactando un comentario',
              'execute_action':'Ejecutando una acción aprobada','reconcile_action':'Conciliando una acción',
              'agent_run':'Preparando una propuesta','prepare_piece':'Preparando la pieza del día'}
STAGE_DESCRIPTIONS={'director':'Eligiendo la idea y el brief del día','redactor':'Redactando dos variantes en inglés',
                    'lectores':'Leyendo las variantes desde su perspectiva','seleccion':'Eligiendo y editando la versión final',
                    'verificador':'Verificando afirmaciones, voz y privacidad'}

def _roles(job):
    """Roles doing the job. A running editorial job shows only the stage's roles (no query for finished jobs)."""
    if job.kind=='prepare_piece':
        if job.state!=Job.State.RUNNING:return editorial.EDITORIAL_ROLES
        stage=EditorialPiece.objects.filter(origin_job=str(job.id)).values_list('stage',flat=True).first() or 'director'
        return editorial.STAGE_ROLES.get(stage,['director_editorial'])
    role=job.agent if job.kind=='agent_run' else JOB_ROLES.get(job.kind)
    return [role] if role else []

def _describe(job):
    if job.kind=='prepare_piece' and job.state==Job.State.RUNNING:
        stage=EditorialPiece.objects.filter(origin_job=str(job.id)).values_list('stage',flat=True).first() or 'director'
        return STAGE_DESCRIPTIONS.get(stage,DESCRIPTIONS['prepare_piece'])
    return DESCRIPTIONS.get(job.kind,'')

class Actividad(APIView):
    def get(self,request):
        implemented={'posicionamiento','perfil',*JOB_ROLES.values(),*editorial.EDITORIAL_ROLES}
        roles={r:{'status':'en_espera' if r in implemented else 'diseno','detail':'' if r in implemented else 'Contrato diseñado; aún sin implementar','since':None}
               for r in ROLES}
        for job in Job.objects.filter(state__in=[Job.State.QUEUED,Job.State.RUNNING]).order_by('created_at'):
            for role in _roles(job):
                if role not in roles:continue
                if job.state==Job.State.RUNNING:
                    roles[role]={'status':'trabajando','detail':_describe(job),'since':job.started_at}
                elif roles[role]['status']!='trabajando':
                    roles[role]['detail']='Trabajo en cola'
        for role in implemented:
            if roles[role]['status']=='en_espera' and not roles[role]['detail']:
                last=next((j for j in Job.objects.filter(state__in=[Job.State.COMPLETE,Job.State.FAILED]).order_by('-finished_at')[:200] if role in _roles(j)),None)
                if last:roles[role].update(detail=f'Último: {DESCRIPTIONS.get(last.kind,last.kind).lower()} ({last.result_status or last.state})',since=last.finished_at)
        if operador.globally_paused():
            for role in implemented:
                if roles[role]['status']!='trabajando':roles[role]['detail']='Máquina en pausa'
        return Response({'updated_at':timezone.now(),'roles':roles})

# --------------------------------------------------------------------------- web push

class SubscriptionInput(serializers.Serializer):
    endpoint=serializers.URLField(max_length=1000)
    keys=serializers.DictField(child=serializers.CharField(max_length=200))
    def validate_endpoint(self,value):
        if not value.startswith('https://'):raise serializers.ValidationError('El endpoint debe usar HTTPS')
        return value
    def validate_keys(self,value):
        if not value.get('p256dh') or not value.get('auth'):raise serializers.ValidationError('Faltan claves p256dh/auth')
        return value

class PushKey(APIView):
    def get(self,request):
        if not push.configured():return Response({'detail':'Notificaciones no configuradas en el servidor (VAPID).'},status=503)
        return Response({'public_key':push.public_key()})

class PushSubscriptions(APIView):
    def post(self,request):
        human_session(request);data=valid(SubscriptionInput,request)
        subscription,created=PushSubscription.objects.update_or_create(endpoint=data['endpoint'],defaults={
            'user':request.user,'p256dh':data['keys']['p256dh'],'auth':data['keys']['auth'],'failures':0,
            'user_agent':request.META.get('HTTP_USER_AGENT','')[:300]})
        return Response({'id':subscription.id},status=201 if created else 200)

class PushUnsubscribe(APIView):
    def post(self,request):
        endpoint=str(request.data.get('endpoint',''))
        PushSubscription.objects.filter(user=request.user,endpoint=endpoint).delete()
        return Response(status=204)

class PushTest(APIView):
    def post(self,request):
        human_session(request)
        if not push.configured():raise PermissionDenied('Notificaciones no configuradas en el servidor (VAPID).')
        sent=push.broadcast('Barrio AI','Notificación de prueba: las alertas llegarán aquí.',url='/ajustes',tag='barrio-prueba',users=[request.user])
        return Response({'sent':sent},status=202)
