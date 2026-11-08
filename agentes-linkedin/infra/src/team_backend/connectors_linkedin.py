"""Official LinkedIn API for own publications (CONT-09): 3-legged OAuth and the Posts API.

Contract verified on Microsoft Learn on 2026-11-06:
- 3-legged OAuth (authorization/accessToken endpoints, `state` against CSRF, tokens issued for 60 days,
  programmatic refresh only for selected partners):
  https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
- Sign In with LinkedIn using OpenID Connect (scopes openid/profile, GET /v2/userinfo returns `sub`):
  https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2
- Share on LinkedIn (w_member_social; the person URN comes from OpenID Connect):
  https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin
- Posts API (POST /rest/posts, text-only body, 201 with the URN in `x-restli-id`; reading a member's
  posts needs the restricted r_member_social, so w_member_social cannot read back):
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
- `little` text format of `commentary` (reserved characters escaped with a backslash):
  https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/little-text-format
- Versioning (latest 202610, each version supported at least one year; 202511 sunsets 2026-11-16):
  https://learn.microsoft.com/en-us/linkedin/marketing/versioning

Same error semantics as connectors.py: ConnectorError = definite (not applied), kind='not_sent' when the
request never left; ConnectorUncertain = may have been published. A publication is never retried.
"""
import os
import re
import hashlib
import time
from datetime import timedelta
from urllib.parse import quote, urlencode
import httpx
from django.db import transaction
from django.utils import timezone
from .connectors import ConnectorError, ConnectorUncertain

AUTH_URL='https://www.linkedin.com/oauth/v2/authorization'
TOKEN_URL='https://www.linkedin.com/oauth/v2/accessToken'
USERINFO_URL='https://api.linkedin.com/v2/userinfo'
POSTS_URL='https://api.linkedin.com/rest/posts'
SCOPES=('openid','profile','w_member_social')
DEFAULT_API_VERSION='202610'
EXPIRY_ALERT=timedelta(days=7)
TOKEN_PAUSE='Token de LinkedIn caducado'
URN=re.compile(r'urn:li:(?:share|ugcPost):\d+')
# Reserved characters of the little format; '#word' stays a hashtag element.
LITTLE_RESERVED=re.compile(r'[|{}@\[\]()<>\\*_~]|#(?!\w)')
TRANSPORT=None  # tests inject an httpx.MockTransport; production uses the default transport

def live():
    return os.environ.get('LIVE_LINKEDIN_OFFICIAL','false').lower()=='true'

def api_version():
    version=os.environ.get('LINKEDIN_API_VERSION',DEFAULT_API_VERSION).strip()
    if not re.fullmatch(r'20\d{4}',version):raise ConnectorError('LINKEDIN_API_VERSION debe tener formato AAAAMM.',kind='config')
    return version

def oauth_settings():
    cid=os.environ.get('LINKEDIN_CLIENT_ID','').strip();secret=os.environ.get('LINKEDIN_CLIENT_SECRET','').strip()
    redirect=os.environ.get('LINKEDIN_REDIRECT_URI','').strip()
    if not (cid and secret and redirect):
        raise ConnectorError('Faltan LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET o LINKEDIN_REDIRECT_URI.',kind='config')
    if not (redirect.startswith('https://') or redirect.startswith('http://localhost')):
        raise ConnectorError('LINKEDIN_REDIRECT_URI debe usar HTTPS.',kind='config')
    return cid,secret,redirect

def oauth_configured():
    try:oauth_settings();return True
    except ConnectorError:return False

def _keys():
    from cryptography.fernet import Fernet, MultiFernet
    keys=[k.strip() for k in os.environ.get('FIELD_ENCRYPTION_KEY','').split(',') if k.strip()]
    if not keys:raise ConnectorError('Falta FIELD_ENCRYPTION_KEY para cifrar el token de LinkedIn.',kind='config')
    try:return MultiFernet([Fernet(k.encode()) for k in keys])  # first key encrypts; all decrypt (rotation)
    except (ValueError,TypeError):raise ConnectorError('FIELD_ENCRYPTION_KEY inválida (clave Fernet).',kind='config') from None

def encrypt(token):return _keys().encrypt(token.encode()).decode()

def decrypt(blob):
    from cryptography.fernet import InvalidToken
    try:return _keys().decrypt(blob.encode()).decode()
    except InvalidToken:raise ConnectorError('No se pudo descifrar el token de LinkedIn; reconecta la cuenta.',kind='config',pause=True) from None

def little_text(text):
    return LITTLE_RESERVED.sub(lambda m:'\\'+m.group(0),text)

def post_url(urn):
    return f'https://www.linkedin.com/feed/update/{urn}/'

def _http():
    return httpx.Client(transport=TRANSPORT,timeout=httpx.Timeout(30.0,connect=10.0))

# --------------------------------------------------------------------------- OAuth (human session only)

def authorization_url(state):
    cid,_,redirect=oauth_settings()
    query={'response_type':'code','client_id':cid,'redirect_uri':redirect,'state':state,'scope':' '.join(SCOPES)}
    return AUTH_URL+'?'+urlencode(query,quote_via=quote)

def exchange_code(code):
    cid,secret,redirect=oauth_settings()
    try:
        with _http() as http:
            response=http.post(TOKEN_URL,data={'grant_type':'authorization_code','code':code,'client_id':cid,
                                               'client_secret':secret,'redirect_uri':redirect})
    except httpx.HTTPError as exc:raise ConnectorError(f'LinkedIn OAuth no respondió: {type(exc).__name__}.',kind='network') from None
    if response.status_code>=400:raise ConnectorError(f'LinkedIn OAuth: HTTP {response.status_code}.',status=response.status_code,kind='oauth')
    try:
        data=response.json();token=data['access_token'];expires=int(data['expires_in'])
        if not isinstance(token,str) or not token or expires<=0:raise ValueError
    except (ValueError,KeyError,TypeError):raise ConnectorError('LinkedIn OAuth: respuesta sin token válido.',kind='oauth') from None
    return {'access_token':token,'expires_in':expires,'scope':str(data.get('scope',''))}

def userinfo(token):
    try:
        with _http() as http:response=http.get(USERINFO_URL,headers={'Authorization':'Bearer '+token})
    except httpx.HTTPError as exc:raise ConnectorError(f'LinkedIn userinfo no respondió: {type(exc).__name__}.',kind='network') from None
    if response.status_code>=400:raise ConnectorError(f'LinkedIn userinfo: HTTP {response.status_code}.',status=response.status_code,kind='oauth')
    try:data=response.json();sub=str(data['sub'])
    except (ValueError,KeyError,TypeError):raise ConnectorError('LinkedIn userinfo: respuesta sin sub.',kind='oauth') from None
    if not re.fullmatch(r'[A-Za-z0-9_\-]{1,100}',sub):raise ConnectorError('LinkedIn userinfo: identificador inválido.',kind='oauth')
    return {'sub':sub,'name':str(data.get('name') or '')[:200]}

def connect_member(user,token,profile):
    """Store the member's token encrypted and (re)activate the official publishing account."""
    from .models import ConnectorAccount, LinkedInCredential
    from .jobs import audit
    granted=set(token['scope'].replace(',',' ').split())
    if 'w_member_social' not in granted:
        raise ConnectorError('LinkedIn no concedió w_member_social: revisa el producto Share on LinkedIn de la app.',kind='scope')
    urn='urn:li:person:'+profile['sub'];now=timezone.now()
    with transaction.atomic():
        account,_=ConnectorAccount.objects.get_or_create(provider='linkedin',external_account_id=urn,
            defaults={'label':'LinkedIn · API oficial'+(f' ({profile["name"]})' if profile['name'] else '')})
        credential,created=LinkedInCredential.objects.update_or_create(account=account,defaults={
            'member_urn':urn,'member_name':profile['name'],'scopes':' '.join(sorted(granted)),'token_encrypted':encrypt(token['access_token']),
            'expires_at':now+timedelta(seconds=token['expires_in']),'connected_by':user,'connected_at':now,'expiry_alerted_at':None})
        account.status='running';account.is_locked=False;account.last_checked_at=now
        fields=['status','is_locked','last_checked_at']
        if account.paused and account.paused_reason.startswith(TOKEN_PAUSE):
            # A pause caused only by the expired token is lifted by Gustavo reconnecting.
            account.paused=False;account.paused_reason='';fields+=['paused','paused_reason']
            audit(user,'operator.account_resumed',account.id,reason='Token de LinkedIn renovado')
        account.save(update_fields=fields)
        audit(user,'linkedin.connected',account.id,member=urn,scopes=credential.scopes,expires_at=credential.expires_at.isoformat(),created=created)
    return credential

# --------------------------------------------------------------------------- publishing

def post_body(author,text,media=None):
    body={'author':author,'commentary':little_text(text),'visibility':'PUBLIC',
            'distribution':{'feedDistribution':'MAIN_FEED','targetEntities':[],'thirdPartyDistributionChannels':[]},
            'lifecycleState':'PUBLISHED','isReshareDisabledByAuthor':False}
    if media:
        if len(media)==1:
            item=media[0]
            body['content']={'media':{'id':item['id'],'title':item.get('title') or 'Gustavo'}}
            if not item['id'].startswith('urn:li:document:'):body['content']['media']['altText']=item['alt']
        else:body['content']={'multiImage':{'images':[{'id':item['id'],'altText':item['alt']} for item in media]}}
    return body

class LinkedInOfficialConnector:
    """Writes only. w_member_social cannot read posts back; confirmation comes from the 201 response
    or from reading the member's own posts through Unipile (operador._find_own_post)."""
    provider='linkedin'

    def __init__(self,account):
        from .models import LinkedInCredential
        if not live():raise ConnectorError('API oficial de LinkedIn desactivada: configurar LIVE_LINKEDIN_OFFICIAL=true.',kind='disabled')
        self.credential=LinkedInCredential.objects.filter(account=account).first()
        if not self.credential:raise ConnectorError('LinkedIn no está conectado: autoriza la cuenta desde Ajustes.',kind='not_connected',pause=True)
        self.account=account;self.version=api_version()

    def expired(self):return self.credential.expires_at<=timezone.now()

    def account_status(self):
        return {'status':'token_expired' if self.expired() else 'running','is_locked':False}

    def upload_media(self,raw,mime,alt,title=''):
        """Initialize, PUT bytes, wait for AVAILABLE. Every failure is before post creation and definite.
        Official shapes: /rest/images and /rest/documents?action=initializeUpload.
        Document alt text lives in the tagged PDF; Posts API has no per-page altText field.
        """
        if self.expired():raise ConnectorError(TOKEN_PAUSE,kind='token_expired',pause=True)
        document=mime=='application/pdf';resource='documents' if document else 'images';key='document' if document else 'image'
        endpoint='https://api.linkedin.com/rest/'+resource
        headers={'Authorization':'Bearer '+decrypt(self.credential.token_encrypted),'LinkedIn-Version':self.version,
                 'X-Restli-Protocol-Version':'2.0.0'}
        def checked(response):
            if response.status_code>=400:
                raise ConnectorError(f'LinkedIn: subida HTTP {response.status_code}; no se creó el post.',status=response.status_code,
                    kind='upload',pause=response.status_code in (401,403,429))
            return response
        try:
            with _http() as http:
                response=checked(http.post(endpoint+'?action=initializeUpload',headers=headers,
                    json={'initializeUploadRequest':{'owner':self.credential.member_urn}}))
                value=response.json()['value'];url=value['uploadUrl'];urn=value[key]
                # Do not leak the bearer token to a redirected or unrelated upload host.
                from urllib.parse import urlparse
                parsed=urlparse(url);host=parsed.hostname or ''
                if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443) or not (host.endswith('.linkedin.com') or host.endswith('.licdn.com')):raise ValueError('Host de subida inválido')
                if not urn.startswith('urn:li:'+key+':'):raise ValueError('URN de subida inválido')
                checked(http.put(url,content=raw,headers={'Authorization':headers['Authorization'],'Content-Type':mime}))
                for attempt in range(8):
                    state=checked(http.get(endpoint+'/'+quote(urn,safe=''),headers=headers)).json().get('status')
                    if state=='AVAILABLE':return {'id':urn,'alt':alt,'title':title}
                    if state not in ('PROCESSING','WAITING_UPLOAD'):break
                    if attempt<7:time.sleep(1)
                raise ValueError('El archivo no quedó disponible')
        except (httpx.HTTPError,ValueError,KeyError,TypeError):
            raise ConnectorError('LinkedIn: no terminó la subida; no se creó el post.',kind='upload') from None

    def create_post(self,text,media=None):
        if self.expired():raise ConnectorError(TOKEN_PAUSE+'; reconecta LinkedIn.',kind='token_expired',pause=True)
        headers={'Authorization':'Bearer '+decrypt(self.credential.token_encrypted),'LinkedIn-Version':self.version,
                 'X-Restli-Protocol-Version':'2.0.0','Content-Type':'application/json'}
        try:
            with _http() as http:response=http.post(POSTS_URL,json=post_body(self.credential.member_urn,text,media),headers=headers)
        except (httpx.ConnectError,httpx.ConnectTimeout):
            raise ConnectorError('LinkedIn: no fue posible conectar; la publicación no se envió.',kind='not_sent') from None
        except httpx.HTTPError as exc:
            raise ConnectorUncertain(f'LinkedIn: respuesta incierta ({type(exc).__name__}).') from None
        status=response.status_code
        if status>=500:raise ConnectorUncertain(f'LinkedIn: HTTP {status}; resultado incierto.')
        if status>=400:
            # 401 invalid token, 403 permission/restriction and 429 rate limit stop the account.
            raise ConnectorError(f'LinkedIn Posts API: HTTP {status}.',status=status,kind=f'http_{status}',pause=status in (401,403,429))
        urn=response.headers.get('x-restli-id','')
        if status!=201 or not URN.fullmatch(urn):raise ConnectorUncertain(f'LinkedIn: HTTP {status} sin URN reconocible; resultado incierto.')
        return {'id':urn,'url':post_url(urn)}


class FakeLinkedInOfficial:
    """In-memory Posts API for tests and rehearsals; `fail_next` as in FakeConnector."""
    provider='linkedin_fake'
    store={}

    def __init__(self,account):
        if os.environ.get('OPERATOR_ALLOW_FAKE','false').lower()!='true':
            raise ConnectorError('Conector simulado desactivado (OPERATOR_ALLOW_FAKE).',kind='disabled')
        self.account=account
        self.state=self.store.setdefault(account.external_account_id,{'posts':[],'uploads':[],'fail_next':None,'writes':0,'expired':False})

    @classmethod
    def reset(cls):cls.store.clear()

    def account_status(self):return {'status':'token_expired' if self.state['expired'] else 'running','is_locked':False}

    def upload_media(self,raw,mime,alt,title=''):
        mode=self.state['fail_next']
        if mode in ('upload_error','upload_rate_limit','upload_auth'):
            self.state['fail_next']=None
            status=429 if mode=='upload_rate_limit' else 401 if mode=='upload_auth' else 422
            raise ConnectorError('Simulado: subida fallida.',status=status,kind='upload',pause=status in (401,429))
        kind='document' if mime=='application/pdf' else 'image'
        urn=f'urn:li:{kind}:fake{len(self.state["uploads"])+1}'
        self.state['uploads'].append({'id':urn,'bytes':raw,'mime':mime,'sha256':hashlib.sha256(raw).hexdigest(),'alt':alt,'title':title})
        return {'id':urn,'alt':alt,'title':title}

    def create_post(self,text,media=None):
        mode=self.state['fail_next'];self.state['fail_next']=None
        if self.state['expired']:raise ConnectorError(TOKEN_PAUSE+' (simulado).',kind='token_expired',pause=True)
        if mode=='reject':raise ConnectorError('Simulado: HTTP 422.',status=422,kind='http_422')
        if mode=='rate_limit':raise ConnectorError('Simulado: HTTP 429.',status=429,kind='http_429',pause=True)
        if mode=='not_sent':raise ConnectorError('Simulado: sin conexión.',kind='not_sent')
        urn=f'urn:li:share:{7400000000000000000+len(self.state["posts"])+1}'
        if mode!='uncertain_not_applied':
            self.state['posts'].append({'id':urn,'text':text,'body':post_body(self.account.external_account_id,text,media)});self.state['writes']+=1
        if mode in ('uncertain_applied','uncertain_not_applied'):raise ConnectorUncertain('Simulado: timeout tras publicar.')
        return {'id':urn,'url':post_url(urn)}


def connector_for(account):
    if account.provider=='linkedin':return LinkedInOfficialConnector(account)
    return FakeLinkedInOfficial(account)

# --------------------------------------------------------------------------- supervision

def status_payload(now=None):
    from .models import LinkedInCredential
    now=now or timezone.now()
    try:version=api_version()
    except ConnectorError:version=None
    data={'configured':oauth_configured(),'live':live(),'api_version':version,'scopes_required':list(SCOPES),'connected':False,
          'member_urn':None,'member_name':None,'scopes':[],'expires_at':None,'days_left':None,'expired':False,
          'expiring_soon':False,'account':None}
    credential=LinkedInCredential.objects.select_related('account').order_by('-connected_at').first()
    if credential:
        left=credential.expires_at-now;account=credential.account
        data.update(connected=left>timedelta(0),member_urn=credential.member_urn,member_name=credential.member_name,
                    scopes=credential.scopes.split(),expires_at=credential.expires_at,days_left=max(0,left.days),
                    expired=left<=timedelta(0),expiring_soon=timedelta(0)<left<=EXPIRY_ALERT,
                    account={'id':str(account.id),'paused':account.paused,'paused_reason':account.paused_reason},
                    connected_at=credential.connected_at)
    return data

def check_tokens(now=None):
    """Autopilot: push an alert 7 days before expiry; once the token expired, pause publishing and push «LinkedIn caducado»."""
    from .models import LinkedInCredential
    from .operador import local_tz, set_account_pause
    now=now or timezone.now();events=0
    for credential in LinkedInCredential.objects.select_related('account'):
        left=credential.expires_at-now;account=credential.account
        if left<=timedelta(0):
            if not account.paused:
                set_account_pause(account,TOKEN_PAUSE+': reconecta LinkedIn en Ajustes para reanudar la publicación diaria.',notify=False)
                from .notificaciones import avisar
                avisar('linkedin_expired','LinkedIn caducado','El acceso caducó y la publicación diaria está en pausa. Reconéctalo desde Tu turno.')
                events+=1
        elif left<=EXPIRY_ALERT and credential.expiry_alerted_at is None:
            when=credential.expires_at.astimezone(local_tz()).strftime('%d/%m %H:%M')
            from .notificaciones import avisar
            avisar('linkedin_expiring','LinkedIn caduca pronto',f'El permiso de publicación caduca el {when}. Reconéctalo desde Tu turno '
                   'para que la publicación diaria no se pause.')
            type(credential).objects.filter(pk=credential.pk).update(expiry_alerted_at=now);events+=1
    return events
