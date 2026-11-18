"""API of the self-hosted office PWA (see oficina/CONTRATO-API.md).
Same origin as the PWA: Django session + CSRF. Human decisions never accept a service Bearer token; the mobile app's
device token is a human session too (movil_views.py, docs/app-movil-backend.md)."""
import json
import os
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from . import alcance, autopiloto, editorial, expo, miembros, operador, push
from .authentication import device_bearer, device_for
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

def check_login(request,username,password):
    """Shared by the session login and the mobile app's device-token login: one lockout counter per client and
    username. Returns (user, None) or (None, (status, detail))."""
    client=request.META.get('REMOTE_ADDR','')
    key=f'login-attempts:{client}:{username.lower()}'
    if cache.get(key,0)>=LOGIN_ATTEMPTS:return None,(429,'Demasiados intentos; espera unos minutos.')
    user=authenticate(request,username=username,password=password)
    if not user or not user.is_active:
        cache.set(key,cache.get(key,0)+1,LOGIN_WINDOW)
        return None,(400,'Usuario o contraseña incorrectos.')
    cache.delete(key)
    return user,None

@require_GET
@ensure_csrf_cookie
def session_view(request):
    user=request.user
    token=device_bearer(request)
    if token:  # the mobile app: a device token instead of the session cookie
        device=device_for(token);user=device.user if device else AnonymousUser()
    return JsonResponse({'authenticated':user.is_authenticated,'user':_user_payload(user) if user.is_authenticated else None})

@require_POST
@csrf_protect
def login_view(request):
    try:data=json.loads(request.body or b'{}')
    except json.JSONDecodeError:return JsonResponse({'detail':'JSON inválido'},status=400)
    username=str(data.get('username',''))[:150];password=str(data.get('password',''))[:256]
    user,error=check_login(request,username,password)
    if error:return JsonResponse({'detail':error[1]},status=error[0])
    login(request,user)
    AuditEvent.objects.create(actor=user,action='auth.login',target='office',metadata={})
    return JsonResponse({'user':_user_payload(user)})

@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)

class Yo(APIView):
    """GET /api/v1/yo, «quién soy» (organizaciones, phase 5): the user's member, role and organization, whether she is its
    admin and whether the team writes with her provisional voice. The apps name people with it, never with a fixed name.
    A user who is not a member (a service, the robot) gets member null; so does every user without members."""
    def get(self,request):
        user=request.user
        member=miembros.member_of_user(user)
        organization=member.organization if member is not None else None
        voice=None
        if member is not None and member.active:
            from . import voz
            voice=voz.current(member)
        return Response({
            'username':user.get_username(),
            'member':{'id':str(member.pk),'display_name':member.display_name,'role':member.role,'active':member.active,
                      'is_admin':member.is_admin,'first':miembros.is_first(member)} if member is not None else None,
            'organization':{'id':str(organization.pk),'name':organization.name,'slug':organization.slug} if organization else None,
            'is_admin':miembros.is_admin(user),
            'provisional_voice':bool(voice is not None and voice.provisional),
            'members':miembros._models()[1].objects.filter(active=True).count() if member is not None else 0})

# --------------------------------------------------------------------------- machine

def _control_payload():
    control=OperatorControl.current()
    if operador.env_paused():
        return {'paused':True,'reason':'Parada fijada en el servidor (OPERATOR_PAUSED).','source':'env','updated_at':None,'updated_by':None}
    return {'paused':control.paused,'reason':control.reason,'source':'db' if control.paused else 'none',
            'updated_at':control.updated_at,'updated_by':control.updated_by.get_username() if control.updated_by else None}

def _capacity(account,now):
    """The caps of the account's member and what every connector of hers wrote today and this week (organizaciones,
    phase 2). None for an account of nobody among several members: no rhythm applies to it."""
    try:member=operador.member_of(account=account)
    except miembros.MiembroRequerido:return None
    day,week=operador.period_starts(now);result={}
    for capability,(daily,weekly) in operador.limits(member=member).items():
        done=operador.writes(account,capability,member)
        daily_used=done.filter(started_at__gte=day).count();weekly_used=done.filter(started_at__gte=week).count()
        result[capability]={'daily':daily,'weekly':weekly,'daily_used':daily_used,'weekly_used':weekly_used,
                            'left':max(0,min(daily-daily_used,weekly-weekly_used))}
    return result

class Overview(APIView):
    def get(self,request):
        from knowledge import presupuesto
        require(request.user,'operate_linkedin')
        now=timezone.now();day,_=operador.period_starts(now)
        start,_,end=os.environ.get('OPERATOR_WINDOW','07:00-21:00').partition('-')
        # Hers (organizaciones, phase 5): her accounts, her proposals, posts and uncertain actions; the total stop, the
        # AI budget and the referents are the organization's.
        member=alcance.miembro(request);mine=alcance.de(ActionProposal.objects.all(),member)
        proposals={state:mine.filter(created_at__gte=day,state=state).count() for state in ActionProposal.State.values}
        accounts=[dict(AccountOutput(a).data,capacity=_capacity(a,now)) for a in alcance.accounts(member).order_by('created_at')]
        return Response({
            'autopilot':{'enabled':autopiloto.enabled(),'policy_version':autopiloto.POLICY_VERSION},
            'control':_control_payload(),
            'window':{'start':start.strip(),'end':end.strip(),'timezone':str(operador.local_tz()),'open_now':operador.within_window(now),
                      'min_spacing_seconds':int(operador.min_spacing().total_seconds())},
            'accounts':accounts,
            'today':{'proposals':proposals,'llm_spent_usd':str(autopiloto.llm_spent_today(now)),
                     'llm_daily_cap_usd':str(presupuesto.daily_fuse()),  # the team's daily safety fuse; no per-area caps
                     'drafts':mine.filter(source='agent',created_at__gte=day).count(),
                     'drafts_daily_cap':autopiloto.daily_proposals(),
                     'editorial_llm_spent_usd':str(editorial.spent_today(now)),'editorial_llm_daily_cap_usd':str(presupuesto.daily_fuse())},
            'counts':{'referents':Referent.objects.filter(active=True).count(),'posts':alcance.de(ObservedPost.objects.all(),member).count(),
                      'uncertain':alcance.de(ActionExecution.objects.all(),member).filter(state='uncertain').count()}})

class ControlInput(serializers.Serializer):
    paused=serializers.BooleanField()
    reason=serializers.CharField(max_length=500,required=False,allow_blank=True,default='')

class Control(APIView):
    def post(self,request):
        human_session(request);data=valid(ControlInput,request)
        operador.set_global_pause(request.user,data['paused'],data['reason'])
        return Response(_control_payload())

def _her_events(request):
    """The operator feed's events that are hers: what she did, what happened to her proposals, accounts and jobs, and the
    organization's total stop. Another member's events are not in her feed (organizaciones, phase 5)."""
    from django.db.models import CharField
    from django.db.models.functions import Cast
    member=alcance.miembro(request)
    if member is None:return Q()
    def ids(rows):return rows.annotate(target_text=Cast('pk',CharField())).values('target_text')
    return (Q(actor=request.user)|Q(target='machine')|Q(target__in=ids(alcance.de(ActionProposal.objects.all(),member)))
            |Q(target__in=ids(alcance.accounts(member)))|Q(target__in=ids(alcance.trabajos(request))))

class Feed(APIView):
    def get(self,request):
        require(request.user,'operate_linkedin')
        try:limit=max(1,min(200,int(request.query_params.get('limit','50'))))
        except ValueError:limit=50
        events=(AuditEvent.objects.select_related('actor').filter(action__regex=r'^(operator|job)\.')
                .filter(_her_events(request)).order_by('-created_at')[:limit])
        return Response([{'id':e.id,'action':e.action,'target':e.target,'created_at':e.created_at,
                          'actor':e.actor.get_username() if e.actor else None,'metadata':e.metadata} for e in events])

# --------------------------------------------------------------------------- office scene

ROLES=['posicionamiento','perfil','investigador_referentes','investigador_lider','analista_barrio_resultados','director_editorial','copywriter_a',
       'copywriter_b','editor_visual','lector_comprador','lector_recomendador','lector_divulgador','lector_lider','lector_par',
       'editor_verificador','relaciones_comunidad','conversaciones_inbox','operador_cuenta']
# Real work behind each implemented role. Roles without work here are contracts in design.
JOB_ROLES={'prepare_profile_assets':'perfil','prepare_profile':'perfil','review_referents':'investigador_lider','advance_experiments':'investigador_lider','observe':'investigador_referentes','propose_comment':'relaciones_comunidad',
           'read_own_comments':'relaciones_comunidad','propose_reply':'relaciones_comunidad','prepare_buyer_draft':'relaciones_comunidad',
           'execute_action':'operador_cuenta','reconcile_action':'operador_cuenta',
           'discover_network':'investigador_referentes','classify_contacts':'investigador_referentes',
           'plan_network':'relaciones_comunidad','sync_network':'relaciones_comunidad',
           'collect_metrics':'analista_barrio_resultados','import_analytics':'analista_barrio_resultados','check_linkedin':'operador_cuenta',
           'collect_outcomes':'analista_barrio_resultados',
           'process_capture':'operador_cuenta',
           'weekly_summary':'analista_barrio_resultados','read_inbox':'conversaciones_inbox',
           'community_study':'analista_barrio_resultados','plan_week':'director_editorial',
           'monthly_review':'analista_barrio_resultados'}
DESCRIPTIONS={'prepare_profile_assets':'Preparando tus fotos y banner','prepare_profile':'Preparando tu propuesta de perfil','review_referents':'Revisando referentes del mes','advance_experiments':'Midiendo el experimento de referentes','observe':'Leyendo publicaciones de referentes','propose_comment':'Redactando un comentario',
              'read_own_comments':'Leyendo los comentarios de tus posts','propose_reply':'Redactando una respuesta en tu post',
              'prepare_buyer_draft':'Preparando un primer mensaje o una nota para un posible cliente',
              'execute_action':'Ejecutando una acción aprobada','reconcile_action':'Conciliando una acción',
              'agent_run':'Preparando una propuesta','prepare_piece':'Preparando la pieza del día',
              'discover_network':'Buscando personas para el barrio','classify_contacts':'Clasificando personas del barrio',
              'plan_network':'Preparando seguimientos e invitaciones','sync_network':'Revisando invitaciones y conexiones',
              'collect_metrics':'Midiendo los posts y la audiencia','import_analytics':'Trayendo la analítica de LinkedIn',
              'collect_outcomes':'Mirando qué pasó después de comentar y conectar',
              'check_linkedin':'Probando que LinkedIn responde como siempre',
              'process_capture':'Leyendo lo que enviaste al equipo',
              'weekly_summary':'Escribiendo el resumen de la semana','read_inbox':'Leyendo el inbox de LinkedIn',
              'community_study':'Estudiando la comunidad con evidencia pública','plan_week':'Planeando la semana de posts',
              'monthly_review':'Revisando el mes y proponiendo cambios'}
STAGE_DESCRIPTIONS={'director':'Eligiendo la idea y el brief del día','redactor':'Redactando dos variantes en inglés',
                    'lectores':'Leyendo las variantes desde su perspectiva','seleccion':'Eligiendo y editando la versión final',
                    'verificador':'Verificando afirmaciones, voz y privacidad',
                    'reparacion':'Corrigiendo la versión final con los hallazgos',
                    'retoque':'Aplicando tu comentario a la pieza lista',
                    'visual':'Preparando foto, infografía o carrusel para la pieza'}

def _roles(job,visual_jobs=None):
    """A running job shows its stage; finished visual work needs persisted evidence."""
    if job.kind=='prepare_piece':
        if job.state==Job.State.QUEUED:return editorial.EDITORIAL_ROLES
        if job.state!=Job.State.RUNNING:
            roles=[r for r in editorial.EDITORIAL_ROLES if r!='editor_visual']
            worked=(str(job.id) in visual_jobs) if visual_jobs is not None else EditorialPiece.objects.filter(
                Q(stage='visual')|Q(usage__contains=[{'stage':'visual'}]),origin_job=str(job.id)).exists()
            if worked:
                roles.append('editor_visual')
            return roles
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
    """The office scene: the team's roles at work (the organization's team). A piece is named only to its member."""
    def get(self,request):
        member=alcance.miembro(request)
        hers=lambda piece:piece is not None and alcance.is_hers(piece,member)
        implemented={'posicionamiento','perfil',*JOB_ROLES.values(),*editorial.EDITORIAL_ROLES}
        roles={r:{'status':'en_espera' if r in implemented else 'diseno','detail':'' if r in implemented else 'Contrato diseñado; aún sin implementar','since':None}
               for r in ROLES}
        for job in Job.objects.filter(state__in=[Job.State.QUEUED,Job.State.RUNNING]).order_by('created_at'):
            for role in _roles(job):
                if role not in roles:continue
                if job.state==Job.State.RUNNING:
                    roles[role]={'status':'trabajando','detail':_describe(job),'since':job.started_at}
                    if role=='editor_visual':
                        piece=EditorialPiece.objects.filter(origin_job=str(job.id)).first()
                        if hers(piece):roles[role].update(piece_id=str(piece.id),detail=f'{STAGE_DESCRIPTIONS["visual"]} del {piece.slot_date:%d/%m}')
                elif roles[role]['status']!='trabajando':
                    roles[role]['detail']='Trabajo en cola'
        finished=list(Job.objects.filter(state__in=[Job.State.COMPLETE,Job.State.FAILED]).order_by('-finished_at')[:200])
        visual_pieces={p.origin_job:p for p in EditorialPiece.objects.filter(
            Q(stage='visual')|Q(usage__contains=[{'stage':'visual'}]),origin_job__in=[str(j.id) for j in finished])}
        for role in implemented:
            if roles[role]['status']=='en_espera' and not roles[role]['detail']:
                last=next((j for j in finished if role in _roles(j,visual_pieces)),None)
                if last:roles[role].update(detail=f'Último: {DESCRIPTIONS.get(last.kind,last.kind).lower()} ({last.result_status or last.state})',since=last.finished_at)
                if last and role=='editor_visual' and last.kind=='prepare_piece' and hers(visual_pieces[str(last.id)]):
                    piece=visual_pieces[str(last.id)]
                    roles[role].update(piece_id=str(piece.id),detail=f'Último: medios de la pieza del {piece.slot_date:%d/%m} ({piece.get_state_display()})')
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
    """«Probar notificación»: the user's PWA subscriptions (Web Push) and phones with the app (Expo)."""
    def post(self,request):
        human_session(request)
        if not push.configured() and not expo.targets([request.user]).exists():
            raise PermissionDenied('Notificaciones no configuradas en el servidor (VAPID).')
        title,body='Barrio AI','Notificación de prueba: las alertas llegarán aquí.'
        sent=push.broadcast(title,body,url='/ajustes',tag='barrio-prueba',users=[request.user])
        sent+=expo.broadcast(title,body,url='/ajustes',tag='barrio-prueba',users=[request.user],urgent=True)
        return Response({'sent':sent},status=202)


class Eventos(APIView):
    """GET /api/v1/oficina/eventos?desde=<iso>: real events that move the scene's characters, oldest first."""
    def get(self,request):
        require(request.user,'operate_linkedin')
        from datetime import datetime
        from . import oficina_eventos
        raw=request.query_params.get('desde')
        try:moment=datetime.fromisoformat(raw.replace('Z','+00:00')) if raw else None
        except ValueError:return Response({'detail':'desde debe ser una fecha ISO'},status=400)
        return Response({'events':oficina_eventos.since(moment),'now':timezone.now()})
