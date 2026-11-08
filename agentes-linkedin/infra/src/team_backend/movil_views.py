"""API of the 0ff1ce mobile app (docs/app-movil-backend.md): device-token login and Expo push registration.
A device token is Gustavo himself on his phone: a human session without cookies or CSRF. Every other endpoint is the
PWA's own (oficina/CONTRATO-API.md) and accepts the device token unchanged."""
import json
import logging
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from . import expo
from .authentication import digest, new_device_token
from .jobs import audit
from .models import AppClientError, DeviceToken, ExpoPushToken
from .oficina_views import _user_payload, check_login
from .operador_views import human_session, valid
from .permissions import require

logger=logging.getLogger('team_backend.app')

def _device_name(value,fallback='App móvil'):
    return (str(value or '').strip() or fallback)[:120]

def revoke(actor,device):
    """Log a device out: its token stops working at once and its Expo tokens stop receiving push."""
    now=timezone.now()
    DeviceToken.objects.filter(pk=device.pk,revoked_at__isnull=True).update(revoked_at=now)
    ExpoPushToken.objects.filter(device=device,active=True).update(active=False,last_error='device_revoked',updated_at=now)
    audit(actor,'auth.device_revoked',device.id,name=device.name)

def devices_payload(request):
    """The user's live device logins, newest first; `current` marks the one making the request."""
    current=request.auth.pk if isinstance(request.auth,DeviceToken) else None
    pushing=set(expo.targets([request.user]).exclude(device__isnull=True).values_list('device_id',flat=True))
    return [{'id':str(d.id),'name':d.name,'created_at':d.created_at,'last_used_at':d.last_used_at,
             'current':d.pk==current,'push':d.pk in pushing}
            for d in DeviceToken.objects.filter(user=request.user,revoked_at__isnull=True)]

class TokenIssue(APIView):
    """POST /api/v1/auth/token: log in on a device. Same credentials and lockout counter as /auth/login; no CSRF."""
    authentication_classes=[];permission_classes=[AllowAny]
    def post(self,request):
        data=request.data if isinstance(request.data,dict) else {}
        user,error=check_login(request,str(data.get('username',''))[:150],str(data.get('password',''))[:256])
        if error:return Response({'detail':error[1]},status=error[0])
        token=new_device_token()  # shown once: only its digest is stored
        device=DeviceToken.objects.create(user=user,name=_device_name(data.get('device_name')),digest=digest(token))
        audit(user,'auth.device_token',device.id,request.request_id,name=device.name)
        response=Response({'token':token,'user':_user_payload(user),
                           'device':{'id':str(device.id),'name':device.name,'created_at':device.created_at}},status=201)
        response['Cache-Control']='no-store'
        return response

class TokenRevoke(APIView):
    """POST /api/v1/auth/token/revocar: log out on this device (the token of the request)."""
    permission_classes=[IsAuthenticated]
    def post(self,request):
        if not isinstance(request.auth,DeviceToken):
            return Response({'detail':'Solo se revoca un token de dispositivo; la sesión de la oficina se cierra con /auth/logout.'},status=400)
        revoke(request.user,request.auth)
        return Response(status=204)

class Devices(APIView):
    """GET /api/v1/auth/dispositivos: «Dispositivos con la app»."""
    permission_classes=[IsAuthenticated]
    def get(self,request):
        return Response(devices_payload(request))

class DeviceDetail(APIView):
    """DELETE /api/v1/auth/dispositivos/<id>: log out a lost or old phone."""
    permission_classes=[IsAuthenticated]
    def delete(self,request,did):
        human_session(request)
        device=DeviceToken.objects.filter(id=did,user=request.user,revoked_at__isnull=True).first()
        if not device:raise NotFound()
        revoke(request.user,device)
        return Response(status=204)

class ExpoTokenInput(serializers.Serializer):
    token=serializers.CharField(max_length=200)
    device_name=serializers.CharField(max_length=120,required=False,allow_blank=True,default='')
    def validate_token(self,value):
        if not expo.valid_token(value):raise serializers.ValidationError('Token de Expo inválido: se espera ExponentPushToken[…].')
        return value

class ExpoPush(APIView):
    """POST /api/v1/push/expo registers an Expo push token (again: updates it); DELETE with {token} unregisters it."""
    def post(self,request):
        human_session(request);data=valid(ExpoTokenInput,request)
        device=request.auth if isinstance(request.auth,DeviceToken) else None
        name=_device_name(data['device_name'],device.name if device else 'App móvil')
        token,_=ExpoPushToken.objects.update_or_create(token=data['token'],defaults={
            'user':request.user,'device':device,'device_name':name,'active':True,'last_error':'','updated_at':timezone.now()})
        return Response({'id':str(token.id)},status=201)
    def delete(self,request):
        token=(request.data.get('token') if isinstance(request.data,dict) else None) or request.query_params.get('token','')
        ExpoPushToken.objects.filter(user=request.user,token=str(token).strip()).delete()
        return Response(status=204)

# --------------------------------------------------------------------------- client error reports

CLIENT_ERRORS_KEPT=200  # newest reports kept; older ones are deleted on each new report
CLIENT_ERROR_MAX_BYTES=8*1024
CLIENT_ERROR_MAX_PARTS=12
CLIENT_ERROR_FIELDS=('kind','name','message','status','detail','platform','os_version','app_version')

class ReportTooLarge(APIException):
    status_code=413
    default_detail='El informe de error es demasiado grande.'

class ClientErrorThrottle(UserRateThrottle):
    """Reports are cheap but must never flood the log: 30 an hour per user, on top of the usual API rate."""
    scope='app_errores'
    rate='30/hour'

class ReportedPartInput(serializers.Serializer):
    field=serializers.CharField(max_length=20)
    type=serializers.CharField(max_length=80,allow_blank=True)
    scheme=serializers.CharField(max_length=16,allow_blank=True)
    size=serializers.IntegerField(min_value=0,allow_null=True,required=False,default=None)

class ClientErrorInput(serializers.Serializer):
    kind=serializers.RegexField(r'^[a-z0-9_.-]{1,40}$',max_length=40,error_messages={'invalid':'Usa minúsculas, cifras, _ . o -.'})
    name=serializers.CharField(max_length=80,allow_blank=True,default='')
    message=serializers.CharField(max_length=500,allow_blank=True,default='')
    status=serializers.IntegerField(min_value=0,max_value=599,allow_null=True,default=None)
    detail=serializers.CharField(max_length=500,allow_blank=True,default='')
    parts=ReportedPartInput(many=True,required=False)
    platform=serializers.CharField(max_length=20,allow_blank=True,default='')
    os_version=serializers.CharField(max_length=40,allow_blank=True,default='')
    app_version=serializers.CharField(max_length=40,allow_blank=True,default='')
    def validate_parts(self,value):
        if len(value)>CLIENT_ERROR_MAX_PARTS:raise serializers.ValidationError(f'Como mucho {CLIENT_ERROR_MAX_PARTS} partes.')
        return value

def _report_too_large(request):
    try:length=int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:length=0
    return length>CLIENT_ERROR_MAX_BYTES or len(request.body)>CLIENT_ERROR_MAX_BYTES

def client_error_payload(report):
    return {'id':str(report.id),'created_at':report.created_at,'device':report.device.name if report.device else None,
            'parts':report.parts,**{field:getattr(report,field) for field in CLIENT_ERROR_FIELDS}}

class ClientErrors(APIView):
    """POST /api/v1/app/errores: a failure the app reports (metadata only: never the audio, the photos, the note or a
    token). It is logged to the app log and kept with the newest CLIENT_ERRORS_KEPT. GET: the newest 50, for diagnosis."""
    def get_throttles(self):
        if self.request.method=='POST':return [*super().get_throttles(),ClientErrorThrottle()]
        return super().get_throttles()
    def get(self,request):
        require(request.user,'operate_linkedin')
        return Response([client_error_payload(r) for r in AppClientError.objects.select_related('device')[:50]])
    def post(self,request):
        human_session(request)
        if _report_too_large(request):raise ReportTooLarge()
        data=valid(ClientErrorInput,request)
        device=request.auth if isinstance(request.auth,DeviceToken) else None
        fields={field:data[field] for field in CLIENT_ERROR_FIELDS}
        parts=[dict(part) for part in data.get('parts') or []]
        report=AppClientError.objects.create(user=request.user,device=device,parts=parts,**fields)
        logger.warning('app_client_error %s',json.dumps({'id':str(report.id),'user':request.user.get_username(),
                       'device':device.name if device else None,'parts':parts,**fields},ensure_ascii=False,sort_keys=True))
        stale=list(AppClientError.objects.order_by('-created_at').values_list('id',flat=True)[CLIENT_ERRORS_KEPT:])
        if stale:AppClientError.objects.filter(id__in=stale).delete()
        return Response({'id':str(report.id)},status=201)
