import hashlib
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication,get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from .models import ApiCredential

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
