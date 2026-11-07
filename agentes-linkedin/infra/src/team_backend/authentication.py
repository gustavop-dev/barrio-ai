import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication,get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiCredential, DeviceToken

# Device tokens of the mobile app carry this prefix, so they are never mistaken for a service ApiCredential.
DEVICE_PREFIX='0ff1ce_dt_'
TOUCH_EVERY=timedelta(minutes=5)  # last_used_at is written at most this often

class CredentialAuthentication(BaseAuthentication):
    def authenticate(self,request):
        header=get_authorization_header(request).split()
        if not header:return None
        if len(header)!=2 or header[0].lower()!=b'bearer':raise AuthenticationFailed('Credencial inválida')
        hashed=hashlib.sha256(header[1]).hexdigest()
        credential=ApiCredential.objects.select_related('user').filter(digest=hashed,revoked=False).first()
        if not credential or not credential.user.is_active or (credential.expires_at and credential.expires_at<=timezone.now()):
            raise AuthenticationFailed('Credencial inválida o revocada')
        return credential.user,credential
    def authenticate_header(self,request):return 'Bearer'

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

def new_device_token():
    return DEVICE_PREFIX+secrets.token_urlsafe(32)

def device_bearer(request):
    """The plain token of `Authorization: Bearer 0ff1ce_dt_…`, or None (no header, another scheme, a service token).
    Works on DRF and plain Django requests (GET /auth/session is a plain view)."""
    header=get_authorization_header(request).split()
    if len(header)!=2 or header[0].lower()!=b'bearer' or not header[1].startswith(DEVICE_PREFIX.encode()):return None
    try:return header[1].decode('ascii')
    except UnicodeDecodeError:return None

def device_for(token):
    """The live DeviceToken of a plain token (not revoked, active user), or None."""
    device=DeviceToken.objects.select_related('user').filter(digest=digest(token),revoked_at__isnull=True).first()
    if not device or not device.user.is_active:return None
    now=timezone.now()
    if not device.last_used_at or now-device.last_used_at>=TOUCH_EVERY:
        DeviceToken.objects.filter(pk=device.pk).update(last_used_at=now);device.last_used_at=now
    return device

class DeviceTokenAuthentication(BaseAuthentication):
    """Human session of the mobile app (docs/app-movil-backend.md). First in DEFAULT_AUTHENTICATION_CLASSES but it only
    claims tokens with DEVICE_PREFIX: any other Bearer goes on to CredentialAuthentication untouched. An unknown or
    revoked device token falls through too, and CredentialAuthentication refuses it with 401."""
    def authenticate(self,request):
        token=device_bearer(request)
        device=device_for(token) if token else None
        return (device.user,device) if device else None
    def authenticate_header(self,request):return 'Bearer'
