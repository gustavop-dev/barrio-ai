"""API of the 0ff1ce mobile app (docs/app-movil-backend.md): device-token login and Expo push registration.
A device token is Gustavo himself on his phone: a human session without cookies or CSRF. Every other endpoint is the
PWA's own (oficina/CONTRATO-API.md) and accepts the device token unchanged."""
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from . import expo
from .authentication import digest, new_device_token
from .jobs import audit
from .models import DeviceToken, ExpoPushToken
from .oficina_views import _user_payload, check_login
from .operador_views import human_session, valid

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
